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
from src.utils import load_funds_from_db  # <-- ¡SIMPLIFICADO!
from src.data_manager import request_new_fund
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX
from src.auth import page_init_and_auth, logout_user
from src.db_connector import get_db_connection

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

col1, col2 = st.columns([4, 1])
with col1:
    st.write("Aquí puedes ver, filtrar y solicitar nuevos fondos para el catálogo.")
with col2:
    if st.button("🔄 Recargar Catálogo", help="Vuelve a leer la base de datos"):
        st.cache_data.clear()
        st.toast("Catálogo recargado desde la base de datos.")
        st.rerun()

with st.expander("➕ Solicitar nuevo fondo por ISIN"):
    with st.form("form_add_fund_explorer"):
        new_isin = st.text_input("Introduce un ISIN para solicitarlo", placeholder="Ej: IE00B4L5Y983").strip().upper()
        submitted = st.form_submit_button("Enviar Solicitud")
        if submitted and new_isin:
            user_id = st.session_state.user_info['uid']
            if request_new_fund(new_isin, user_id):
                st.rerun()

# --- CARGA DE DATOS Y FILTROS ---
st.sidebar.header("Filtros del Explorador")
horizonte = st.sidebar.selectbox(
    "Horizonte temporal para métricas",
    HORIZONTE_OPCIONES,
    index=HORIZONTE_DEFAULT_INDEX,
    key="horizonte_fondos"
)

@st.cache_data
def load_data_with_metrics(selected_horizon: str):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT
                f.*, 
                m.annualized_return_pct, m.cumulative_return_pct,
                m.volatility_pct, m.sharpe_ratio,
                m.sortino_ratio, m.max_drawdown_pct
            FROM funds f
            LEFT JOIN fund_metrics m ON f.isin = m.isin AND m.horizon = %(horizon)s
        """
        df = pd.read_sql(query, conn, params={"horizon": selected_horizon})
        return df
    finally:
        if conn: conn.close()

df_display = load_data_with_metrics(horizonte)

if df_display.empty:
    st.warning("Aún no hay fondos en el catálogo o el worker de métricas no se ha ejecutado.")
    st.stop()

df_display['ter'] = pd.to_numeric(df_display['ter'], errors='coerce')

# (Filtros no cambian, solo los nombres de las columnas)
if 'gestora' in df_display.columns:
    gestoras = sorted(df_display["gestora"].dropna().unique())
    selected_gestoras = st.sidebar.multiselect("Filtrar por Gestora", gestoras, default=[])
else:
    selected_gestoras = []

search_term = st.sidebar.text_input("Buscar por nombre")

# --- FILTRADO DE DATOS ---
df_filtered = df_display.copy()
if search_term:
    df_filtered = df_filtered[df_filtered["name"].str.contains(search_term, case=False)]

st.markdown("---")
st.subheader("Lista de Fondos")
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df_display)}** fondos.")

# --- CONTROLES DE ORDENACIÓN (NOMBRES DE COLUMNA ACTUALIZADOS) ---
sort_options = {
    "Rentabilidad Anual": "annualized_return_pct",
    "Ratio Sharpe": "sharpe_ratio",
    "Ratio Sortino": "sortino_ratio",
    "Volatilidad": "volatility_pct",
    "TER": "ter",
    "Nombre": "name",
}

col1_sort, col2_sort = st.columns(2)
with col1_sort:
    sort_by_name = st.selectbox("Ordenar por", options=list(sort_options.keys()), index=0)
    sort_by_col = sort_options[sort_by_name]
with col2_sort:
    sort_order_name = st.selectbox("Orden", options=["Descendente", "Ascendente"])
    sort_ascending = (sort_order_name == "Ascendente")
df_sorted = df_filtered.sort_values(by=sort_by_col, ascending=sort_ascending, na_position='last')

# --- CABECERA (NOMBRES DE COLUMNA ACTUALIZADOS) ---
header_cols = st.columns((3, 1.5, 1, 1, 1, 1, 1, 1, 1, 1.5, 1.5))
header_cols[0].markdown("**Nombre**")
header_cols[1].markdown("**ISIN**")
header_cols[2].markdown(f"**Rent. (%)**")
header_cols[3].markdown(f"**Vol. (%)**")
header_cols[4].markdown("**Sharpe**")
header_cols[5].markdown("**Sortino**")
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

# --- BUCLE DE VISUALIZACIÓN (NOMBRES DE COLUMNA ACTUALIZADOS) ---
for index, row in df_sorted.iterrows():
    cols = st.columns((3, 1.5, 1, 1, 1, 1, 1, 1, 1, 1.5, 1.5))
    isin_actual = row.get('isin')

    with cols[0]: st.markdown(f"**{row.get('name', 'N/A')}**")
    with cols[1]: st.code(isin_actual)
    with cols[2]: st.write(f"{row.get('annualized_return_pct', 0):.2f}" if pd.notna(row.get('annualized_return_pct')) else "N/A")
    with cols[3]: st.write(f"{row.get('volatility_pct', 0):.2f}" if pd.notna(row.get('volatility_pct')) else "N/A")
    with cols[4]: st.write(f"{row.get('sharpe_ratio', 0):.2f}" if pd.notna(row.get('sharpe_ratio')) else "N/A")
    with cols[5]: st.write(f"{row.get('sortino_ratio', 0):.2f}" if pd.notna(row.get('sortino_ratio')) else "N/A")
    with cols[6]: st.write(f"{row.get('ter', 0):.2f}" if pd.notna(row.get('ter')) else "N/A")
    with cols[7]: st.write(row.get('gestora', 'N/A'))
    with cols[8]: st.write(f"{row.get('srri', 'N/A')}")
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