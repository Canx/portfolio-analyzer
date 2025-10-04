# pages/2_detalle_cartera.py

import streamlit as st
import pandas as pd

# Configurar el layout de la página para que sea ancho
st.set_page_config(layout="wide")

from src.auth import page_init_and_auth
from src.database import save_user_data
from src.utils import load_funds_from_db, load_all_navs
from src.portfolio import Portfolio
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import optimize_portfolio
from src.components.detalle_cartera_view import (
    render_analysis_sidebar,
    render_portfolio_summary,
    render_composition_controls,
    render_funds_analysis
)

# --- LÓGICA DE NEGOCIO ENCAPSULADA ---

def handle_optimization(run_optimization, daily_returns, modelo_seleccionado, cartera_activa_nombre):
    if not run_optimization or daily_returns.empty:
        return

    st.info(f"Ejecutando optimización con el modelo: {modelo_seleccionado}...")
    pesos_opt = optimize_portfolio(daily_returns, model=modelo_seleccionado)
    
    if pesos_opt is not None:
        pesos_opt_dict = {isin: int(round(p * 100)) for isin, p in pesos_opt.items()}
        resto = 100 - sum(pesos_opt_dict.values())
        if resto != 0 and not pesos_opt.empty:
            pesos_opt_dict[pesos_opt.idxmax()] += resto
        st.session_state.carteras[cartera_activa_nombre]["pesos"] = pesos_opt_dict
        st.success(f"Cartera '{cartera_activa_nombre}' optimizada con {modelo_seleccionado} ✅")
        st.rerun()
    else:
        st.error("No se pudo optimizar la cartera con los parámetros seleccionados.")

def calculate_page_metrics(daily_returns, filtered_navs, pesos_cartera_activa, df_catalogo):
    # Cálculo del TER ponderado
    ter_ponderado = 0
    if pesos_cartera_activa:
        ter_map = pd.Series(df_catalogo['ter'].values, index=df_catalogo['isin']).to_dict()
        for isin, peso in pesos_cartera_activa.items():
            ter_fondo = pd.to_numeric(ter_map.get(isin, 0), errors='coerce')
            ter_ponderado += (peso / 100) * (0 if pd.isna(ter_fondo) else ter_fondo)

    # Cálculo de métricas de fondos individuales
    mapa_datos_fondos = df_catalogo.set_index('isin').to_dict('index')
    metricas_fondos = []
    for isin in daily_returns.columns:
        m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
        m.update(mapa_datos_fondos.get(isin, {}))
        metricas_fondos.append(m)
    df_funds_metrics = pd.DataFrame(metricas_fondos)

    # Cálculo de métricas de la cartera
    portfolio = Portfolio(filtered_navs, pesos_cartera_activa)
    portfolio_metrics = {}
    if portfolio and portfolio.nav is not None:
        calculated_metrics = portfolio.calculate_metrics(risk_free_rate=0.0)
        if calculated_metrics:
            portfolio.metrics = calculated_metrics
            portfolio_metrics = calculated_metrics
            
    return portfolio, portfolio_metrics, df_funds_metrics, ter_ponderado

# --- INICIALIZACIÓN Y FLUJO PRINCIPAL ---

# 1. Autenticación y configuración inicial de la página
auth, db = page_init_and_auth()
if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

if not st.session_state.get("cartera_activa"):
    st.info("⬅️ No has seleccionado ninguna cartera.")
    if st.button("⬅️ Volver a Mis Carteras"): st.switch_page("pages/2_carteras.py")
    st.stop()

cartera_activa_nombre = st.session_state.cartera_activa
st.title(f"📈 Análisis de: {cartera_activa_nombre}")

# 2. Carga de datos generales
df_catalogo = load_funds_from_db()
if df_catalogo.empty:
    st.error("No se pudo cargar el catálogo de fondos.")
    st.stop()

mapa_isin_nombre = pd.Series(df_catalogo['name'].values, index=df_catalogo['isin']).to_dict()
mapa_nombre_isin = {f"{row['name']} ({row['isin']})": row['isin'] for _, row in df_catalogo.iterrows()}
data_manager = DataManager()

# 3. Renderizado de UI y obtención de parámetros del usuario
horizonte, run_optimization, modelo_seleccionado = render_analysis_sidebar()
pesos_cartera_activa = st.session_state.carteras[cartera_activa_nombre]["pesos"]
with st.expander("✍️ Editar Composición"):
    render_composition_controls(pesos_cartera_activa, mapa_nombre_isin, mapa_isin_nombre)

# 4. Carga de datos de precios y cálculo de retornos
isines_a_cargar = tuple(pesos_cartera_activa.keys())
if not isines_a_cargar:
    st.warning("Esta cartera está vacía. Añade fondos desde el expander de composición.")
    st.stop()

all_navs_df = load_all_navs(data_manager, isines_a_cargar)
if all_navs_df.empty:
    st.warning("No se encontraron datos de precios para los fondos de esta cartera.")
    st.stop()

filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns = filtered_navs.pct_change().fillna(0)

# 5. Lógica de negocio principal
handle_optimization(run_optimization, daily_returns, modelo_seleccionado, cartera_activa_nombre)
portfolio, portfolio_metrics, df_funds_metrics, ter_ponderado = calculate_page_metrics(
    daily_returns, filtered_navs, pesos_cartera_activa, df_catalogo
)

# 6. Renderizado de resultados
render_portfolio_summary(portfolio_metrics, pesos_cartera_activa, ter_ponderado, mapa_isin_nombre, horizonte)
st.markdown("---")
render_funds_analysis(df_funds_metrics, daily_returns, portfolio, mapa_isin_nombre, horizonte)

# 7. Guardado final de datos de usuario
if 'carteras' in st.session_state and 'user_info' in st.session_state:
    profile_data_to_save = {
        "subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
        "carteras": st.session_state.get("carteras", {})
    }
    save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)