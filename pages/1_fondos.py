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
        localS = LocalStorage()
        logout_user(localS)
        st.rerun()

# --- LÓGICA DE LA PÁGINA ---
localS = LocalStorage()
st.title("🔎 Explorador de Fondos del Catálogo")


col1, col2 = st.columns([4, 1])
with col1:
    st.write("Aquí puedes buscar, filtrar y analizar el catálogo completo de fondos.")
with col2:
    if st.button("🔄 Recargar Catálogo", help="Vuelve a leer la base de datos"):
        st.cache_data.clear()
        st.toast("Catálogo recargado desde la base de datos.")
        st.rerun()

user_plan = st.session_state.user_info.get("subscription_plan", "free")

with st.expander("➕ Solicitar nuevo fondo por ISIN"):
    if user_plan == "free":
        st.info("La solicitud de nuevos fondos para añadir al catálogo es una funcionalidad Premium.")
        if st.button("✨ Mejorar a Premium para solicitar fondos"):
            st.switch_page("pages/4_cuenta.py")
    else: # Premium user
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
                f.isin, f.name, f.ter, f.gestora, f.domicilio, f.srri, f.morningstar_category, f.currency, f.performance_id,
                m.annualized_return_pct, m.volatility_pct, m.sharpe_ratio, m.sortino_ratio, m.calmar_ratio
            FROM funds f
            LEFT JOIN fund_metrics m ON f.isin = m.isin AND m.horizon = %(horizon)s
        """
        df = pd.read_sql(query, conn, params={"horizon": selected_horizon})
        # Limpieza de datos
        for col in ['ter', 'srri', 'annualized_return_pct', 'volatility_pct', 'sharpe_ratio']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
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

# --- Crear enlace a Morningstar ---
df_display['morningstar_url'] = df_display['performance_id'].apply(
    lambda pid: f"https://global.morningstar.com/es/inversiones/fondos/{pid}/cotizacion" if pd.notna(pid) else None
)

# --- FILTROS AVANZADOS ---
df_filtered = df_display.copy()

# Filtros de texto
for col_name in ['gestora', 'domicilio', 'morningstar_category', 'currency']:
    if col_name in df_filtered.columns:
        options = sorted(df_filtered[col_name].dropna().unique())
        if options:
            selected = st.sidebar.multiselect(col_name.replace('_', ' ').capitalize(), options)
            if selected:
                df_filtered = df_filtered[df_filtered[col_name].isin(selected)]

# --- LÓGICA DE SLIDERS DINÁMICOS Y ROBUSTOS ---
def create_dynamic_slider(df, column_name, label, min_val=None, max_val=None, step=None, format_str=None):
    # Crear una copia para evitar SettingWithCopyWarning
    df_result = df.copy()
    
    # Trabajar solo con los valores no nulos para definir los límites del slider
    df_col = df_result[column_name].dropna()
    if df_col.empty:
        return df_result # No mostrar el slider si no hay datos

    # Usar los valores del dataframe si no se especifican límites
    actual_min = min_val if min_val is not None else float(df_col.min())
    actual_max = max_val if max_val is not None else float(df_col.max())
    
    # Asegurarnos de que min < max para evitar el error de Streamlit
    if actual_min >= actual_max:
        return df_result[df_result[column_name] == actual_min]

    # Convertir a int si son números enteros
    if df_col.dtype == 'int64' or all(df_col == df_col.astype(int)):
        actual_min, actual_max = int(actual_min), int(actual_max)
        step = 1 if step is None else int(step)

    selected_range = st.sidebar.slider(
        label,
        min_value=actual_min,
        max_value=actual_max,
        value=(actual_min, actual_max),
        step=step,
        format=format_str
    )
    
    # CORRECCIÓN CLAVE: Al filtrar, mantener los que están en el rango Y también los que son nulos (NaN)
    condition = df_result[column_name].between(selected_range[0], selected_range[1])
    nan_condition = df_result[column_name].isna()
    return df_result[condition | nan_condition]

df_filtered = create_dynamic_slider(df_filtered, 'srri', 'Rango de SRRI')
df_filtered = create_dynamic_slider(df_filtered, 'ter', 'Rango de TER (%)', step=0.01)
df_filtered = create_dynamic_slider(df_filtered, 'annualized_return_pct', 'Rentabilidad Anualizada (%)', step=0.5)
df_filtered = create_dynamic_slider(df_filtered, 'volatility_pct', 'Volatilidad (%)', step=0.5)
df_filtered = create_dynamic_slider(df_filtered, 'sharpe_ratio', 'Rango de Ratio de Sharpe', step=0.1)
df_filtered = create_dynamic_slider(df_filtered, 'sortino_ratio', 'Rango de Ratio de Sortino', step=0.1)
df_filtered = create_dynamic_slider(df_filtered, 'calmar_ratio', 'Rango de Ratio de Calmar', step=0.1)

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
    column_order=("seleccionar", "name", "morningstar_url", "ter", "annualized_return_pct", "volatility_pct", "sharpe_ratio", "sortino_ratio", "calmar_ratio"),
    column_config={
        "seleccionar": st.column_config.CheckboxColumn(required=True),
        "name": st.column_config.TextColumn("Nombre", width="large"),
        "morningstar_url": st.column_config.LinkColumn("Enlace Morningstar", width="small"),
        "ter": st.column_config.NumberColumn("TER (%)", format="%.2f%%"),
        "annualized_return_pct": st.column_config.NumberColumn(f"Rent. Anual {horizonte} (%)", format="%.2f%%"),
        "volatility_pct": st.column_config.NumberColumn(f"Vol. {horizonte} (%)", format="%.2f%%"),
        "sharpe_ratio": st.column_config.NumberColumn(f"Sharpe {horizonte}", format="%.2f"),
        "sortino_ratio": st.column_config.NumberColumn(f"Sortino {horizonte}", format="%.2f"),
        "calmar_ratio": st.column_config.NumberColumn(f"Calmar {horizonte}", format="%.2f"),
        "currency": "Moneda",
        "performance_id": None # Ocultar esta columna
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
            # Leer la comparación actual del LocalStorage
            saved_comp_json = localS.getItem('saved_comparison')
            current_comp = {"carteras": [], "fondos": []}
            if saved_comp_json:
                try:
                    current_comp = json.loads(saved_comp_json)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Añadir los ISINs seleccionados (sin duplicados)
            fondos_en_comparador = set(current_comp.get('fondos', []))
            fondos_anadidos = 0
            for isin in selected_isins:
                if isin not in fondos_en_comparador:
                    fondos_en_comparador.add(isin)
                    fondos_anadidos += 1

            # Guardar la nueva comparación
            current_comp['fondos'] = list(fondos_en_comparador)
            localS.setItem('saved_comparison', json.dumps(current_comp))
            
            if fondos_anadidos > 0:
                st.toast(f"¡{fondos_anadidos} fondo(s) añadidos al comparador!", icon="⚖️")
            else:
                st.toast("Los fondos seleccionados ya estaban en el comparador.", icon="✔️")