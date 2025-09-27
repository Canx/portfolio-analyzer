import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import json

# --- CONFIGURACIÓN DE PÁGINA (Debe ser lo primero) ---
st.set_page_config(
    page_title="Explorador de Fondos",
    page_icon="🔎",
    layout="wide"
)

# Importaciones de funciones compartidas
from src.utils import load_funds_from_db
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
st.title("🔎 Explorador de Fondos del Catálogo")

col1, col2 = st.columns([4, 1])
with col1:
    st.write("Aquí puedes buscar, filtrar y analizar el catálogo completo de fondos.")
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

# --- CARGA DE DATOS ---
@st.cache_data
def load_data_with_metrics(selected_horizon: str):
    conn = get_db_connection()
    if not conn: return pd.DataFrame()
    try:
        query = """
            SELECT
                f.isin, f.name, f.ter, f.gestora, f.domicilio, f.srri, f.morningstar_category,
                m.annualized_return_pct, m.volatility_pct, m.sharpe_ratio
            FROM funds f
            LEFT JOIN fund_metrics m ON f.isin = m.isin AND m.horizon = %(horizon)s
        """
        df = pd.read_sql(query, conn, params={"horizon": selected_horizon})
        # Limpieza de datos
        df['ter'] = pd.to_numeric(df['ter'], errors='coerce')
        df['srri'] = pd.to_numeric(df['srri'], errors='coerce')
        return df
    finally:
        if conn: conn.close()

# --- FILTROS EN LA SIDEBAR ---
st.sidebar.header("Filtros del Explorador")
horizonte = st.sidebar.selectbox(
    "Horizonte temporal para métricas",
    HORIZONTE_OPCIONES,
    index=HORIZONTE_DEFAULT_INDEX,
    key="horizonte_fondos"
)

df_display = load_data_with_metrics(horizonte)

if df_display.empty:
    st.warning("Aún no hay fondos en el catálogo o el worker de métricas no se ha ejecutado.")
    st.stop()

# --- FILTROS AVANZADOS ---
df_filtered = df_display.copy()

# Filtros de texto
gestoras = sorted(df_filtered["gestora"].dropna().unique())
selected_gestoras = st.sidebar.multiselect("Gestora", gestoras)
if selected_gestoras:
    df_filtered = df_filtered[df_filtered["gestora"].isin(selected_gestoras)]

domicilios = sorted(df_filtered["domicilio"].dropna().unique())
selected_domicilios = st.sidebar.multiselect("Domicilio", domicilios)
if selected_domicilios:
    df_filtered = df_filtered[df_filtered["domicilio"].isin(selected_domicilios)]

categorias = sorted(df_filtered["morningstar_category"].dropna().unique())
selected_categorias = st.sidebar.multiselect("Categoría Morningstar", categorias)
if selected_categorias:
    df_filtered = df_filtered[df_filtered["morningstar_category"].isin(selected_categorias)]

# Filtros numéricos con sliders
min_srri, max_srri = st.sidebar.slider(
    'Rango de SRRI',
    min_value=int(df_filtered['srri'].min()),
    max_value=int(df_filtered['srri'].max()),
    value=(int(df_filtered['srri'].min()), int(df_filtered['srri'].max()))
)
df_filtered = df_filtered[df_filtered['srri'].between(min_srri, max_srri)]

max_ter = st.sidebar.slider('TER máximo (%)', 0.0, 5.0, 5.0, 0.01)
df_filtered = df_filtered[df_filtered['ter'] <= max_ter]

min_rentabilidad, max_rentabilidad = st.sidebar.slider(
    'Rentabilidad Anual (%)', -50.0, 100.0, (-50.0, 100.0), 0.5
)
df_filtered = df_filtered[df_filtered['annualized_return_pct'].between(min_rentabilidad, max_rentabilidad)]

max_volatilidad = st.sidebar.slider('Volatilidad máxima (%)', 0.0, 100.0, 100.0, 0.5)
df_filtered = df_filtered[df_filtered['volatility_pct'] <= max_volatilidad]

# --- BÚSQUEDA RÁPIDA (TEXTO) ---
st.markdown("---")
search_term = st.text_input("🔎 Búsqueda rápida por Nombre o ISIN", placeholder="Escribe para filtrar...")
if search_term:
    df_filtered = df_filtered[
        df_filtered["name"].str.contains(search_term, case=False, na=False) |
        df_filtered["isin"].str.contains(search_term, case=False, na=False)
    ]

# --- VISUALIZACIÓN DE LA TABLA ---
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df_display)}** fondos.")

# --- LÓGICA DE SELECCIÓN Y ACCIONES ---
df_filtered['seleccionar'] = False
df_editable = st.data_editor(
    df_filtered,
    column_config={
        "seleccionar": st.column_config.CheckboxColumn(required=True),
        "name": st.column_config.TextColumn("Nombre", width="large"),
        "ter": st.column_config.NumberColumn("TER (%)", format="%.2f%%"),
        "annualized_return_pct": st.column_config.NumberColumn(f"Rent. {horizonte} (%)", format="%.2f%%"),
        "volatility_pct": st.column_config.NumberColumn(f"Vol. {horizonte} (%)", format="%.2f%%"),
        "sharpe_ratio": st.column_config.NumberColumn(f"Sharpe {horizonte}", format="%.2f"),
    },
    use_container_width=True,
    hide_index=True,
    key="df_editor"
)

selected_rows = df_editable[df_editable['seleccionar']]
selected_isins = selected_rows['isin'].tolist()

if selected_isins:
    st.info(f"Has seleccionado {len(selected_isins)} fondo(s).")
    active_portfolio_name = st.session_state.get("cartera_activa")
    
    col_acc1, col_acc2, _ = st.columns([2, 2, 4])
    with col_acc1:
        if st.button("➕ Añadir a Cartera Activa", disabled=not active_portfolio_name):
            if active_portfolio_name:
                for isin in selected_isins:
                    if isin not in st.session_state.carteras[active_portfolio_name]['pesos']:
                         st.session_state.carteras[active_portfolio_name]['pesos'][isin] = 0
                st.toast(f"{len(selected_isins)} fondo(s) añadidos a '{active_portfolio_name}'")
                st.rerun()
            else:
                st.warning("Crea o selecciona una cartera primero.")
    
    with col_acc2:
        if st.button("⚖️ Añadir al Comparador"):
            # Lógica para añadir al comparador (requiere LocalStorage o una gestión de estado similar)
            st.info("Funcionalidad para añadir al comparador pendiente de implementar.")