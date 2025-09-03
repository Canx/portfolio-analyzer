import streamlit as st
import pandas as pd
import numpy as np

# Importamos las funciones compartidas desde sus módulos correctos
from src.utils import load_config
from src.state import initialize_session_state
from src.data_manager import find_and_add_fund_by_isin, update_fund_details_in_config

st.set_page_config(
    page_title="Explorador de Fondos",
    page_icon="🔎",
    layout="wide"
)

# Inicializamos el estado al principio de la página para asegurar que exista
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
                st.cache_data.clear() # Limpiamos caché para recargar el JSON
                st.rerun()

fondos_config = load_config()

if not fondos_config:
    st.warning("Aún no has añadido ningún fondo a tu catálogo.")
    st.stop()

df = pd.DataFrame(fondos_config)
df['ter'] = pd.to_numeric(df['ter'], errors='coerce')

# --- Controles de Filtro en la Barra Lateral ---
st.sidebar.header("Filtros del Explorador")
gestoras = sorted(df["gestora"].dropna().unique())
selected_gestoras = st.sidebar.multiselect("Filtrar por Gestora", gestoras, default=[])

domicilios = sorted(df["domicilio"].dropna().unique())
selected_domicilios = st.sidebar.multiselect("Filtrar por Domicilio", domicilios, default=[])

max_ter_value = df['ter'].max() if not df['ter'].dropna().empty else 10.0
selected_max_ter = st.sidebar.slider(
    "TER Máximo (%)", 0.0, float(np.ceil(max_ter_value)),
    value=float(np.ceil(max_ter_value)), step=0.1
)
search_term = st.sidebar.text_input("Buscar por nombre")

# --- Lógica de Filtrado ---
df_filtered = df
if selected_gestoras:
    df_filtered = df_filtered[df_filtered["gestora"].isin(selected_gestoras)]
if selected_domicilios:
    df_filtered = df_filtered[df_filtered["domicilio"].isin(selected_domicilios)]
df_filtered = df_filtered[(df_filtered["ter"] <= selected_max_ter) | (df_filtered["ter"].isna())]
if search_term:
    df_filtered = df_filtered[df_filtered["nombre"].str.contains(search_term, case=False)]

st.markdown("---")

# --- Visualización de la Lista Dinámica ---
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df)}** fondos.")

header_cols = st.columns((3, 2, 1, 1, 2, 1, 2, 2))
header_cols[0].markdown("**Nombre**")
header_cols[1].markdown("**ISIN**")
header_cols[2].markdown("**TER (%)**")
header_cols[3].markdown("**SRRI**")
header_cols[4].markdown("**Gestora**")
header_cols[5].markdown("**Domicilio**")
header_cols[6].markdown("**Refrescar Datos**")
header_cols[7].markdown("**Añadir a Cartera**")

# --- LÓGICA CORREGIDA ---
# Obtenemos los ISINs de la cartera activa ANTES del bucle
active_portfolio_name = st.session_state.get("cartera_activa")
isins_in_active_portfolio = []
if active_portfolio_name:
    isins_in_active_portfolio = st.session_state.carteras.get(active_portfolio_name, {}).get("pesos", {}).keys()

for index, row in df_filtered.iterrows():
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns((3, 2, 1, 1, 2, 1, 2, 2))
    # ... (columnas 1 a 6 no cambian)
    with col1:
        st.markdown(f"**{row.get('nombre', 'N/A')}**")
        st.caption(f"{row.get('nombre_legal', '')}")
    with col2:
        st.code(row.get('isin', 'N/A'))
    with col3:
        ter_value = row.get('ter')
        st.write(f"{ter_value:.2f}" if pd.notna(ter_value) else "N/A")
    with col4:
        st.write(f"{row.get('srri', 'N/A')}")
    with col5:
        st.write(row.get('gestora', 'N/A'))
    with col6:
        st.write(row.get('domicilio', 'N/A'))
    
    with col7:
        if st.button("🔄 Refrescar", key=f"update_explorer_{row['isin']}"):
            update_fund_details_in_config(row['isin'])
            st.session_state.force_update_isin = row['isin']
            st.cache_data.clear()
            st.rerun()
    
    with col8:
        # Usamos la nueva variable para la comprobación
        if row['isin'] in isins_in_active_portfolio:
            st.success("En cartera ✔️")
        else:
            if st.button("➕ Añadir", key=f"add_explorer_{row['isin']}"):
                if active_portfolio_name:
                    st.session_state.carteras[active_portfolio_name]['pesos'][row['isin']] = 0
                    
                    # Rebalanceamos los pesos
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