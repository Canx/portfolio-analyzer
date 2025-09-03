import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path

# Importaciones de funciones compartidas
from src.utils import load_config, load_all_navs
from src.state import initialize_session_state
from src.data_manager import find_and_add_fund_by_isin, update_fund_details_in_config, DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades

st.set_page_config(
    page_title="Explorador de Fondos",
    page_icon="🔎",
    layout="wide"
)

initialize_session_state()

# --- Lógica de la Página ---
st.title("🔎 Explorador de Fondos del Catálogo")
st.write("Aquí puedes ver, filtrar, actualizar, añadir nuevos fondos al catálogo y asignarlos a tu cartera activa.")

with st.expander("➕ Añadir nuevo fondo al catálogo por ISIN"):
    with st.form("form_add_fund_explorer"):
        new_isin = st.text_input("Introduce un ISIN para buscarlo", placeholder="Ej: IE00B4L5Y983").strip().upper()
        submitted = st.form_submit_button("Buscar y Añadir")

        if submitted and new_isin:
            if find_and_add_fund_by_isin(new_isin):
                st.cache_data.clear()
                st.rerun()

# --- Carga de Datos y Cálculos Iniciales ---
fondos_config = load_config()

if not fondos_config:
    st.warning("Aún no has añadido ningún fondo a tu catálogo.")
    st.stop()

df_catalogo = pd.DataFrame(fondos_config)
df_catalogo['ter'] = pd.to_numeric(df_catalogo['ter'], errors='coerce')

# --- Controles de Filtro en la Barra Lateral ---
st.sidebar.header("Filtros del Explorador")
horizonte = st.sidebar.selectbox(
    "Horizonte temporal para el análisis",
    ["1m", "3m", "6m", "YTD", "1y", "3y", "5y", "max"],
    key="explorer_horizonte"
)

if 'gestora' in df_catalogo.columns:
    gestoras = sorted(df_catalogo["gestora"].dropna().unique())
    selected_gestoras = st.sidebar.multiselect("Filtrar por Gestora", gestoras, default=[])
else:
    selected_gestoras = []

if 'domicilio' in df_catalogo.columns:
    domicilios = sorted(df_catalogo["domicilio"].dropna().unique())
    selected_domicilios = st.sidebar.multiselect("Filtrar por Domicilio", domicilios, default=[])
else:
    selected_domicilios = []

if 'ter' in df_catalogo.columns:
    max_ter_value = df_catalogo['ter'].max() if not df_catalogo['ter'].dropna().empty else 10.0
    selected_max_ter = st.sidebar.slider(
        "TER Máximo (%)", 0.0, float(np.ceil(max_ter_value)),
        value=float(np.ceil(max_ter_value)), step=0.1
    )
else:
    selected_max_ter = 10.0

search_term = st.sidebar.text_input("Buscar por nombre")

# --- CÁLCULO DE MÉTRICAS ---
data_manager = DataManager()
isines_catalogo = tuple(df_catalogo['isin'].unique())
all_navs_df = load_all_navs(data_manager, isines_catalogo)

df_metrics_calculadas = pd.DataFrame()
if not all_navs_df.empty:
    filtered_navs_for_metrics = filtrar_por_horizonte(all_navs_df, horizonte)
    daily_returns = filtered_navs_for_metrics.pct_change()
    
    metricas_lista = []
    for isin in daily_returns.columns:
        returns_sin_na = daily_returns[isin].dropna()
        if not returns_sin_na.empty and len(returns_sin_na) > 2:
            m = calcular_metricas_desde_rentabilidades(returns_sin_na)
            m['isin'] = isin
            metricas_lista.append(m)
    
    if metricas_lista:
        df_metrics_calculadas = pd.DataFrame(metricas_lista)

# --- FUSIÓN Y FILTRADO FINAL ---
df_display = pd.merge(df_catalogo, df_metrics_calculadas, on='isin', how='left')
df_filtered = df_display.copy()

if selected_gestoras: df_filtered = df_filtered[df_filtered["gestora"].isin(selected_gestoras)]
if selected_domicilios: df_filtered = df_filtered[df_filtered["domicilio"].isin(selected_domicilios)]
if 'ter' in df_filtered.columns and 'max_ter_value' in locals():
    if selected_max_ter < max_ter_value:
        df_filtered = df_filtered[df_filtered["ter"] <= selected_max_ter]
if search_term:
    df_filtered = df_filtered[df_filtered["nombre"].str.contains(search_term, case=False)]

st.markdown("---")

# --- Visualización de la Lista Dinámica ---
st.subheader("Lista de Fondos")
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df_catalogo)}** fondos.")

# --- NUEVO: CONTROLES DE ORDENACIÓN ---
sort_options = {
    "Rentabilidad Anual": "annualized_return_%",
    "Ratio Sharpe": "sharpe_ann",
    "Volatilidad": "volatility_ann_%",
    "TER": "ter",
    "Nombre": "nombre",
}

col1_sort, col2_sort = st.columns(2)
with col1_sort:
    sort_by_name = st.selectbox("Ordenar por", options=list(sort_options.keys()), index=0)
    sort_by_col = sort_options[sort_by_name]
with col2_sort:
    sort_order_name = st.selectbox("Orden", options=["Descendente", "Ascendente"])
    sort_ascending = (sort_order_name == "Ascendente")

# Aplicamos la ordenación, poniendo los valores nulos al final
df_sorted = df_filtered.sort_values(by=sort_by_col, ascending=sort_ascending, na_position='last')


# --- CABECERA ACTUALIZADA ---
header_cols = st.columns((3, 1.5, 1, 1, 1, 1, 1.5, 1, 1.5, 1.5))
header_cols[0].markdown("**Nombre**")
header_cols[1].markdown("**ISIN**")
header_cols[2].markdown(f"**Rent. (%)**")
header_cols[3].markdown(f"**Vol. (%)**")
header_cols[4].markdown("**Sharpe**")
header_cols[5].markdown("**TER (%)**")
header_cols[6].markdown("**Gestora**")
header_cols[7].markdown("**SRRI**")
header_cols[8].markdown("**Refrescar**")
header_cols[9].markdown("**Añadir**")

active_portfolio_name = st.session_state.get("cartera_activa")
isins_in_active_portfolio = []
if active_portfolio_name:
    isins_in_active_portfolio = st.session_state.carteras.get(active_portfolio_name, {}).get("pesos", {}).keys()

# Iteramos sobre el DataFrame YA ORDENADO
for index, row in df_sorted.iterrows():
    cols = st.columns((3, 1.5, 1, 1, 1, 1, 1.5, 1, 1.5, 1.5))
    with cols[0]:
        st.markdown(f"**{row.get('nombre', 'N/A')}**"); st.caption(f"{row.get('nombre_legal', '')}")
    with cols[1]:
        st.code(row.get('isin', 'N/A'))
    with cols[2]:
        rent_anual = row.get('annualized_return_%'); st.write(f"{rent_anual:.2f}" if pd.notna(rent_anual) else "N/A")
    with cols[3]:
        volatilidad = row.get('volatility_ann_%'); st.write(f"{volatilidad:.2f}" if pd.notna(volatilidad) else "N/A")
    with cols[4]:
        # --- NUEVA COLUMNA SHARPE ---
        sharpe = row.get('sharpe_ann'); st.write(f"{sharpe:.2f}" if pd.notna(sharpe) else "N/A")
    with cols[5]:
        ter_value = row.get('ter'); st.write(f"{ter_value:.2f}" if pd.notna(ter_value) else "N/A")
    with cols[6]:
        st.write(row.get('gestora', 'N/A'))
    with cols[7]:
        st.write(f"{row.get('srri', 'N/A')}")
    with cols[8]:
        if st.button("🔄", key=f"update_explorer_{row['isin']}", help="Refrescar datos descriptivos y de precios"):
            update_fund_details_in_config(row['isin']); st.session_state.force_update_isin = row['isin']
            st.cache_data.clear(); st.rerun()
    with cols[9]:
        if row['isin'] in isins_in_active_portfolio:
            st.success("✔️")
        else:
            if st.button("➕", key=f"add_explorer_{row['isin']}", help=f"Añadir a la cartera '{active_portfolio_name}'"):
                if active_portfolio_name:
                    st.session_state.carteras[active_portfolio_name]['pesos'][row['isin']] = 0
                    pesos_actuales = st.session_state.carteras[active_portfolio_name]['pesos']
                    num_fondos = len(pesos_actuales)
                    peso_base = 100 // num_fondos
                    st.session_state.carteras[active_portfolio_name]['pesos'] = {isin: peso_base for isin in pesos_actuales.keys()}
                    resto = 100 - sum(st.session_state.carteras[active_portfolio_name]['pesos'].values())
                    if num_fondos > 0:
                        primer_isin = list(pesos_actuales.keys())[0]
                        st.session_state.carteras[active_portfolio_name]['pesos'][primer_isin] += resto
                    st.toast(f"'{row['nombre']}' añadido a '{active_portfolio_name}'!")
                    st.rerun()
                else:
                    st.warning("Ve a 'Análisis de Cartera' para crear o seleccionar una cartera primero.")

# --- Gráfico de Riesgo vs. Retorno ---
st.markdown("---")
st.subheader("🎯 Gráfico de Riesgo vs. Retorno")
if not df_metrics_calculadas.empty:
    df_grafico = pd.merge(df_metrics_calculadas, df_catalogo[['isin', 'nombre']], on='isin', how='left')
    
    # --- GRÁFICO SIMPLIFICADO ---
    fig_risk = px.scatter(
        df_grafico,
        x="volatility_ann_%",
        y="annualized_return_%",
        hover_name="nombre",
        title=f"Eficiencia de los Fondos del Catálogo ({horizonte})",
        # Hemos eliminado el parámetro 'size'
        # Ahora Plotly asignará un color diferente a cada fondo para distinguirlos
    )
    fig_risk.update_layout(xaxis_title="Volatilidad Anualizada (%)", yaxis_title="Rentabilidad Anualizada (%)")
    st.plotly_chart(fig_risk, use_container_width=True)
else:
    st.warning("No hay suficientes datos históricos en el periodo seleccionado para generar el gráfico de riesgo.")

        