import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import json
from streamlit_local_storage import LocalStorage

# --- CONFIGURACIÓN DE PÁGINA (Debe ser lo primero) ---
st.set_page_config(
    page_title="Explorador de Fondos",
    page_icon="🔎",
    layout="wide"
)

# Importaciones de funciones compartidas
from src.data_manager import DataManager, filtrar_por_horizonte, request_new_fund
from src.metrics import calcular_metricas_desde_rentabilidades
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX
from src.auth import page_init_and_auth, logout_user
from src.utils import load_funds_from_db, load_all_navs

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

# --- BOTÓN DE LOGOUT EN LA SIDEBAR ---
with st.sidebar:
    st.write(f"Usuario: {st.session_state.user_info.get('email')}")
    if st.button("Cerrar Sesión"):
        logout_user()
        st.rerun()

# --- LÓGICA DE LA PÁGINA ---
localS = LocalStorage()
st.title("🔎 Explorador de Fondos del Catálogo")
st.write("Aquí puedes ver, filtrar, añadir nuevos fondos al catálogo y asignarlos a tu cartera activa.")

with st.expander("➕ Añadir nuevo fondo al catálogo por ISIN"):
    with st.form("form_add_fund_explorer"):
        new_isin = st.text_input("Introduce un ISIN para buscarlo", placeholder="Ej: IE00B4L5Y983").strip().upper()
        submitted = st.form_submit_button("Buscar y Añadir")

        if submitted and new_isin:
            user_id = st.session_state.user_info['uid']
            # Llamamos a la nueva función
            if request_new_fund(new_isin, user_id):
                st.rerun()

df_catalogo = load_funds_from_db()

if df_catalogo.empty:
    st.warning("Aún no has añadido ningún fondo a tu catálogo.")
    st.stop()

df_catalogo['ter'] = pd.to_numeric(df_catalogo['ter'], errors='coerce')
st.sidebar.header("Filtros del Explorador")
horizonte = st.sidebar.selectbox(
            "Horizonte temporal",
            HORIZONTE_OPCIONES,
            index=HORIZONTE_DEFAULT_INDEX,
            key="horizonte")
if 'gestora' in df_catalogo.columns:
    gestoras = sorted(df_catalogo["gestora"].dropna().unique())
    selected_gestoras = st.sidebar.multiselect("Filtrar por Gestora", gestoras, default=[])
else:
    selected_gestoras = []
# (Resto de filtros no cambian)
if 'domicilio' in df_catalogo.columns:
    domicilios = sorted(df_catalogo["domicilio"].dropna().unique())
    selected_domicilios = st.sidebar.multiselect("Filtrar por Domicilio", domicilios, default=[])
else:
    selected_domicilios = []
if 'ter' in df_catalogo.columns:
    ter_values = pd.to_numeric(df_catalogo['ter'], errors='coerce').dropna()
    
    max_ter_value = ter_values.max() if not ter_values.empty else 0.0

    # --- CÓDIGO CORREGIDO ---
    # Aseguramos que el valor máximo del slider sea siempre mayor que el mínimo (0.0)
    slider_max_val = float(np.ceil(max_ter_value))
    if slider_max_val <= 0.0:
        slider_max_val = 5.0  # Establecemos un máximo por defecto si no hay TERs > 0

    selected_max_ter = st.sidebar.slider(
        "TER Máximo (%)", 
        min_value=0.0, 
        max_value=slider_max_val, # Usamos el valor máximo seguro
        value=slider_max_val, 
        step=0.1
    )
else:
    selected_max_ter = 5.0 # Valor por defecto si la columna TER no existe

search_term = st.sidebar.text_input("Buscar por nombre")


# --- CÁLCULO DE MÉTRICAS (BLOQUE CORREGIDO) ---
data_manager = DataManager()
isines_catalogo = tuple(df_catalogo['isin'].unique())
with st.spinner(f"Cargando datos de precios para {len(isines_catalogo)} fondos..."):
    all_navs_df = load_all_navs(data_manager, isines_catalogo)

metricas_lista = []
if not all_navs_df.empty:
    filtered_navs_for_metrics = filtrar_por_horizonte(all_navs_df, horizonte)
    daily_returns = filtered_navs_for_metrics.pct_change()
    
    for isin in daily_returns.columns:
        returns_sin_na = daily_returns[isin].dropna()
        if not returns_sin_na.empty and len(returns_sin_na) > 2:
            m = calcular_metricas_desde_rentabilidades(returns_sin_na)
            m['isin'] = isin
            metricas_lista.append(m)

if metricas_lista:
    df_metrics_calculadas = pd.DataFrame(metricas_lista)
else:
    # --- SOLUCIÓN CLAVE ---
    # Si no se calculó ninguna métrica (ej. solo hay fondos nuevos sin CSV),
    # creamos un DataFrame vacío pero con TODAS las columnas que se esperan más adelante.
    # Esto evita el KeyError en el pd.merge.
    df_metrics_calculadas = pd.DataFrame(columns=[
        'isin', 'annualized_return_%', 'cumulative_return_%', 
        'volatility_ann_%', 'sharpe_ann', 'max_drawdown_%', 'sortino_ann'
    ])

# --- FUSIÓN, FILTRADO Y ORDENACIÓN (sin cambios) ---
df_display = pd.merge(df_catalogo, df_metrics_calculadas, on='isin', how='left')
df_filtered = df_display.copy()
if selected_gestoras: df_filtered = df_filtered[df_filtered["gestora"].isin(selected_gestoras)]
if selected_domicilios: df_filtered = df_filtered[df_filtered["domicilio"].isin(selected_domicilios)]
if 'ter' in df_filtered.columns and 'max_ter_value' in locals():
    if selected_max_ter < max_ter_value:
        df_filtered = df_filtered[df_filtered["ter"] <= selected_max_ter]
if search_term:
    df_filtered = df_filtered[df_filtered["name"].str.contains(search_term, case=False)]
st.markdown("---")
st.subheader("Lista de Fondos")
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df_catalogo)}** fondos.")

# --- CONTROLES DE ORDENACIÓN MODIFICADOS ---
sort_options = {
    "Rentabilidad Anual": "annualized_return_%",
    "Ratio Sharpe": "sharpe_ann",
    "Ratio Sortino": "sortino_ann", # <-- AÑADIDO
    "Volatilidad": "volatility_ann_%",
    "TER": "ter",
    "Nombre": "name"
}
col1_sort, col2_sort = st.columns(2)
with col1_sort:
    sort_by_name = st.selectbox("Ordenar por", options=list(sort_options.keys()), index=0)
    sort_by_col = sort_options[sort_by_name]
with col2_sort:
    sort_order_name = st.selectbox("Orden", options=["Descendente", "Ascendente"])
    sort_ascending = (sort_order_name == "Ascendente")
df_sorted = df_filtered.sort_values(by=sort_by_col, ascending=sort_ascending, na_position='last')

# --- CABECERA ACTUALIZADA ---
header_cols = st.columns((3, 1.5, 1, 1, 1, 1, 1, 1.5, 1, 1.5, 1.5))
header_cols[0].markdown("**Nombre**")
header_cols[1].markdown("**ISIN**")
header_cols[2].markdown(f"**Rent. (%)**")
header_cols[3].markdown(f"**Vol. (%)**")
header_cols[4].markdown("**Sharpe**")
header_cols[5].markdown("**Sortino**") # <-- AÑADIDO
header_cols[6].markdown("**TER (%)**")
header_cols[7].markdown("**Gestora**")
header_cols[8].markdown("**SRRI**")
header_cols[9].markdown("**Añadir Cartera**")
header_cols[10].markdown("**Comparar**")

# Lógica para leer la comparación
saved_comp_json = localS.getItem('saved_comparison')
fondos_en_comparador = []
if saved_comp_json:
    try:
        fondos_en_comparador = json.loads(saved_comp_json).get('fondos', [])
    except (json.JSONDecodeError, TypeError):
        pass

active_portfolio_name = st.session_state.get("cartera_activa")
isins_in_active_portfolio = []
if active_portfolio_name:
    isins_in_active_portfolio = st.session_state.carteras.get(active_portfolio_name, {}).get("pesos", {}).keys()

# --- BUCLE DE VISUALIZACIÓN MODIFICADO ---
for index, row in df_sorted.iterrows():
    cols = st.columns((3, 1.5, 1, 1, 1, 1, 1, 1.5, 1, 1.5, 1.5))
    isin_actual = row.get('isin')

    with cols[0]:
        st.markdown(f"**{row.get('name', 'N/A')}**"); st.caption(f"{row.get('nombre_legal', '')}")
    with cols[1]:
        st.code(isin_actual)
    with cols[2]:
        st.write(f"{row.get('annualized_return_%', 0):.2f}" if pd.notna(row.get('annualized_return_%')) else "N/A")
    with cols[3]:
        st.write(f"{row.get('volatility_ann_%', 0):.2f}" if pd.notna(row.get('volatility_ann_%')) else "N/A")
    with cols[4]:
        st.write(f"{row.get('sharpe_ann', 0):.2f}" if pd.notna(row.get('sharpe_ann')) else "N/A")
    
    with cols[5]: # <-- NUEVA COLUMNA SORTINO
        sortino = row.get('sortino_ann')
        st.write(f"{sortino:.2f}" if pd.notna(sortino) else "N/A")
        
    with cols[6]:
        st.write(f"{row.get('ter', 0):.2f}" if pd.notna(row.get('ter')) else "N/A")
    with cols[7]:
        st.write(row.get('gestora', 'N/A'))
    with cols[8]:
        st.write(f"{row.get('srri', 'N/A')}")

    with cols[9]:
        if isin_actual in isins_in_active_portfolio:
            st.success("✔️")
        else:
            if st.button("➕", key=f"add_explorer_{isin_actual}", help=f"Añadir a '{active_portfolio_name}'"):
                if active_portfolio_name:
                    st.session_state.carteras[active_portfolio_name]['pesos'][isin_actual] = 0
                    st.rerun()
                else:
                    st.warning("Crea o selecciona una cartera primero.")

    with cols[10]:
        if isin_actual in fondos_en_comparador:
            st.success("✔️ añadido")
        else:
            if st.button("⚖️", key=f"compare_{isin_actual}", help="Añadir al comparador"):
                if isin_actual not in fondos_en_comparador:
                    fondos_en_comparador.append(isin_actual)
                    current_comp = {"carteras": [], "fondos": fondos_en_comparador}
                    localS.setItem('saved_comparison', json.dumps(current_comp))
                    st.toast(f"'{row.get('name')}' añadido al comparador.")
                    st.rerun()

# --- Gráfico de Riesgo vs. Retorno ---
st.markdown("---")
st.subheader("🎯 Gráfico de Riesgo vs. Retorno")
if not df_metrics_calculadas.empty:
    df_grafico = pd.merge(df_metrics_calculadas, df_catalogo[['isin', 'name']], on='isin', how='left')
    fig_risk = px.scatter(
        df_grafico, x="volatility_ann_%", y="annualized_return_%",
        hover_name="name", title=f"Eficiencia de los Fondos del Catálogo ({horizonte})"
    )
    fig_risk.update_layout(xaxis_title="Volatilidad Anualizada (%)", yaxis_title="Rentabilidad Anualizada (%)")
    st.plotly_chart(fig_risk, use_container_width=True)
else:
    st.warning("No hay suficientes datos históricos para generar el gráfico.")