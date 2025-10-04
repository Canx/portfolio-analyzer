# pages/2_detalle_cartera.py

import streamlit as st
import pandas as pd
from streamlit_local_storage import LocalStorage
from src.auth import page_init_and_auth, logout_user
from src.database import save_user_data
from src.portfolio import Portfolio
from src.utils import load_all_navs
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import optimize_portfolio
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX
from src.utils import load_funds_from_db
import plotly.express as px
import plotly.graph_objects as go

# --- DIÁLOGOS Y FUNCIONES DE RENDERIZADO ---

@st.dialog("Añadir Fondos a la Cartera")
def add_fund_dialog(mapa_nombre_isin, pesos_actuales):
    search_term = st.text_input("Buscar por Nombre o ISIN", key="fund_search_dialog")
    if search_term:
        candidatos = [
            nombre for nombre in mapa_nombre_isin.keys()
            if (search_term.lower() in nombre.lower()) and (mapa_nombre_isin[nombre] not in pesos_actuales)
        ]
    else:
        candidatos = [
            nombre for nombre in list(mapa_nombre_isin.keys())[:200]
            if mapa_nombre_isin[nombre] not in pesos_actuales
        ]

    if not candidatos and search_term:
        st.warning("No se encontraron fondos con ese criterio o ya están en la cartera.")

    fondos_seleccionados = st.multiselect(
        "Selecciona los fondos que quieres añadir:",
        options=candidatos,
        help="Puedes seleccionar varios fondos."
    )

    if st.button("➕ Añadir Selección", use_container_width=True):
        for fondo_nombre in fondos_seleccionados:
            isin = mapa_nombre_isin[fondo_nombre]
            if isin not in pesos_actuales:
                pesos_actuales[isin] = 0
        st.rerun()

    if st.button("Cerrar", use_container_width=True):
        st.rerun()

def render_portfolio_summary(portfolio_metrics, pesos, ter_ponderado, mapa_isin_nombre, horizonte):
    st.header("Resumen de la Cartera")
    if not portfolio_metrics:
        st.info("No hay suficientes datos para calcular las métricas de la cartera en el horizonte seleccionado.")
        # Aun sin metricas, mostramos el grafico de tarta si hay pesos
        if pesos and sum(pesos.values()) > 0:
            st.subheader("📊 Distribución de la Cartera")
            df_pie = pd.DataFrame(list(pesos.items()), columns=["ISIN", "Peso"])
            df_pie["Fondo"] = df_pie["ISIN"].map(mapa_isin_nombre)
            fig_pie = px.pie(df_pie, names="Fondo", values="Peso", title="Composición Actual de la Cartera", hole=0.3)
            fig_pie.update_traces(textposition="inside", textinfo="percent+label", pull=[0.05] * len(df_pie))
            st.plotly_chart(fig_pie, use_container_width=True)
        return

    label_rentabilidad = "Rent. Anual"
    valor_rentabilidad = portfolio_metrics.get('annualized_return_%', 0)
    if horizonte in ["1m", "3m", "6m", "YTD"]:
        label_rentabilidad = f"Rent. ({horizonte})"
        valor_rentabilidad = portfolio_metrics.get('cumulative_return_%', 0)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label_rentabilidad, f"{valor_rentabilidad:.2f}%")
    with col2: st.metric("Volatilidad", f"{portfolio_metrics.get('volatility_ann_%', 0):.2f}%")
    with col3: st.metric("R. Sharpe", f"{portfolio_metrics.get('sharpe_ann', 0):.2f}")
    with col4: st.metric("TER Ponderado", f"{ter_ponderado:.2f}%")

def render_composition_controls(pesos_actuales, mapa_nombre_isin, mapa_isin_nombre):
    st.subheader("Composición de la Cartera")
    if st.button("➕ Añadir Fondo", use_container_width=True):
        add_fund_dialog(mapa_nombre_isin, pesos_actuales)

    for isin in sorted(pesos_actuales.keys()):
        col_name, col_input, col_del = st.columns([3, 6, 1])
        with col_name: st.markdown(mapa_isin_nombre.get(isin, isin))
        with col_input:
            nuevo_peso = st.number_input("Peso %", min_value=0, max_value=100, value=pesos_actuales[isin], step=1, key=f"peso_{isin}", label_visibility="collapsed")
            if nuevo_peso != pesos_actuales[isin]: pesos_actuales[isin] = nuevo_peso
        with col_del:
            if st.button("🗑️", key=f"remove_{isin}", help="Eliminar fondo"):
                del pesos_actuales[isin]
                st.rerun()

    if pesos_actuales:
        total_peso = sum(pesos_actuales.values())
        st.metric("Suma Total", f"{total_peso}%")
        if total_peso != 100: st.error("⚠️ La suma debe ser 100%.")

def render_funds_analysis(df_funds_metrics, daily_returns, portfolio, mapa_isin_nombre, horizonte):
    st.header("Análisis de Fondos Individuales")
    st.subheader(f"📑 Métricas para el horizonte: {horizonte}")
    if not df_funds_metrics.empty:
        df_display = df_funds_metrics.rename(
            columns={
                "name": "Nombre", "annualized_return_%": "Rent. Anual (%)",
                "volatility_ann_%": "Volatilidad Anual (%)", "sharpe_ann": "Ratio Sharpe",
                "sortino_ann": "Ratio Sortino", "calmar_ratio": "Ratio Calmar",
                "max_drawdown_%": "Caída Máxima (%)",
            }
        ).set_index("Nombre")[[
            "Rent. Anual (%)", "Volatilidad Anual (%)", "Ratio Sharpe",
            "Ratio Sortino", "Ratio Calmar", "Caída Máxima (%)",
        ]]
        df_display = df_display[~df_display.index.duplicated(keep='first')]
        st.dataframe(
            df_display.style.format("{:.2f}")
                      .background_gradient(cmap='RdYlGn', subset=['Rent. Anual (%)', 'Ratio Sharpe', 'Ratio Sortino', 'Ratio Calmar'])
                      .background_gradient(cmap='RdYlGn_r', subset=['Volatilidad Anual (%)', 'Caída Máxima (%)']),
            use_container_width=True
        )

    st.markdown("---")

    if daily_returns.empty or len(daily_returns) < 2:
        st.warning("No hay suficientes datos históricos para generar los gráficos de análisis.")
    else:
        st.subheader("📈 Evolución y Distribución")
        col1, col2 = st.columns(2)
        with col1:
            if portfolio.weights.any():
                df_pie = pd.DataFrame(list(portfolio.weights.items()), columns=["ISIN", "Peso"])
                df_pie["Fondo"] = df_pie["ISIN"].map(mapa_isin_nombre)
                fig_pie = px.pie(df_pie, names="Fondo", values="Peso", title="Composición de la Cartera", hole=0.3)
                fig_pie.update_traces(textposition="inside", textinfo="percent+label", showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True)
        with col2:
            navs_normalizados = (1 + daily_returns).cumprod() * 100
            fig_rent = px.line(navs_normalizados.rename(columns=mapa_isin_nombre), title="Evolución Normalizada de Fondos vs. Cartera")
            if portfolio and portfolio.nav is not None:
                fig_rent.add_trace(go.Scatter(x=portfolio.nav.index, y=portfolio.nav.values, mode="lines", name="💼 Mi Cartera", line=dict(color="black", width=3, dash="dash")))
            st.plotly_chart(fig_rent, use_container_width=True)

        st.subheader("🎯 Riesgo vs. Retorno")
        if not df_funds_metrics.empty:
            fig_risk = px.scatter(df_funds_metrics, x="volatility_ann_%", y="annualized_return_%", text="name", hover_name="name", title="Riesgo vs. Retorno de los Fondos")
            fig_risk.update_traces(textposition="top center")
            if portfolio and portfolio.metrics:
                fig_risk.add_trace(go.Scatter(x=[portfolio.metrics.get("volatility_ann_%", 0)], y=[portfolio.metrics.get("annualized_return_%", 0)], mode="markers", marker=dict(color="red", size=15, symbol="star"), name=f"💼 {st.session_state.cartera_activa}"))
            fig_risk.update_layout(xaxis_title="Volatilidad Anualizada (%)", yaxis_title="Rentabilidad Anualizada (%)")
            st.plotly_chart(fig_risk, use_container_width=True)

        st.subheader("🔗 Correlación de la Cartera")
        if len(daily_returns.columns) > 1:
            corr_matrix = daily_returns.corr()
            corr_matrix.columns = [mapa_isin_nombre.get(c, c) for c in corr_matrix.columns]
            corr_matrix.index = [mapa_isin_nombre.get(i, i) for i in corr_matrix.index]
            fig_corr = px.imshow(corr_matrix, text_auto=True, aspect="auto", color_continuous_scale='RdBu_r', range_color=[-1, 1], title="Matriz de Correlación de los Fondos")
            st.plotly_chart(fig_corr, use_container_width=True)

# --- INICIALIZACIÓN Y SIDEBAR ---
auth, db = page_init_and_auth()
if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

if not st.session_state.get("cartera_activa"):
    st.info("⬅️ No has seleccionado ninguna cartera.")
    if st.button("⬅️ Volver a Mis Carteras"):
        st.switch_page("pages/2_carteras.py")
    st.stop()

cartera_activa_nombre = st.session_state.cartera_activa

def render_analysis_sidebar():
    run_optimization = False
    modelo_seleccionado = None
    with st.sidebar:
        st.write(f"Usuario: {st.session_state.user_info.get('email')}")
        if st.button("Cerrar Sesión"):
            LocalStorage().clear()
            st.session_state.logged_in = False
            st.rerun()
        
        st.markdown("---")
        if st.button("⬅️ Volver a Mis Carteras"):
            st.switch_page("pages/2_carteras.py")
        st.markdown("---")
        
        st.header("Configuración del Análisis")
        horizonte = st.selectbox("Horizonte temporal", HORIZONTE_OPCIONES, index=HORIZONTE_DEFAULT_INDEX, key="horizonte_detalle")
        
        st.markdown("---")
        st.subheader("⚖️ Optimización")
        if st.session_state.user_info.get("subscription_plan") == "premium":
            opciones = ["MSR", "MSoR", "MCR", "MV", "HRP", "CVaR", "ERC"]
            labels = {
                "MSR": "Máximo Ratio de Sharpe", "MSoR": "Máximo Ratio de Sortino",
                "MCR": "Máximo Ratio de Calmar", "MV": "Mínima Volatilidad",
                "HRP": "Hierarchical Risk Parity", "CVaR": "Mínimo CVaR",
                "ERC": "Equal Risk Contribution (HERC)"
            }
            modelo_seleccionado = st.selectbox("Selecciona un modelo", opciones, index=0, format_func=lambda x: labels.get(x, x))
            run_optimization = st.button("🚀 Optimizar Cartera")
        else:
            st.info("La optimización es una funcionalidad Premium.")
            if st.button("✨ Mejorar a Premium"): st.switch_page("pages/4_cuenta.py")
                
    return horizonte, run_optimization, modelo_seleccionado

# --- FLUJO PRINCIPAL ---
st.title(f"📈 Análisis de: {cartera_activa_nombre}")

df_catalogo = load_funds_from_db()
if df_catalogo.empty:
    st.error("No se pudo cargar el catálogo de fondos.")
    st.stop()

mapa_isin_nombre = pd.Series(df_catalogo['name'].values, index=df_catalogo['isin']).to_dict()
mapa_nombre_isin = {f"{row['name']} ({row['isin']})": row['isin'] for _, row in df_catalogo.iterrows()}
data_manager = DataManager()

horizonte, run_optimization, modelo_seleccionado = render_analysis_sidebar()

pesos_cartera_activa = st.session_state.carteras[cartera_activa_nombre]["pesos"]

# --- CÁLCULO DE MÉTRICAS Y DATOS ---
ter_ponderado = 0
if pesos_cartera_activa:
    ter_map = pd.Series(df_catalogo['ter'].values, index=df_catalogo['isin']).to_dict()
    for isin, peso in pesos_cartera_activa.items():
        ter_fondo = pd.to_numeric(ter_map.get(isin, 0), errors='coerce')
        ter_ponderado += (peso / 100) * (0 if pd.isna(ter_fondo) else ter_fondo)

isines_a_cargar = tuple(pesos_cartera_activa.keys())

# --- RENDERIZADO DE PÁGINA (PARTE 1) ---

# Primero renderizamos los controles de composición en un expander
with st.expander("✍️ Editar Composición"):
    render_composition_controls(pesos_cartera_activa, mapa_nombre_isin, mapa_isin_nombre)

if not isines_a_cargar:
    st.warning("Esta cartera está vacía. Añade fondos desde el expander de composición.")
    st.stop()

all_navs_df = load_all_navs(data_manager, isines_a_cargar)
if all_navs_df.empty:
    st.warning("No se encontraron datos de precios para los fondos de esta cartera.")
    st.stop()

filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns = filtered_navs.pct_change().dropna()

# --- LÓGICA DE OPTIMIZACIÓN ---
if run_optimization and not daily_returns.empty:
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

# --- CÁLCULO DE MÉTRICAS ---
mapa_datos_fondos = df_catalogo.set_index('isin').to_dict('index')
metricas_fondos = []
for isin in daily_returns.columns:
    m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
    m.update(mapa_datos_fondos.get(isin, {}))
    metricas_fondos.append(m)
df_funds_metrics = pd.DataFrame(metricas_fondos)

portfolio = Portfolio(filtered_navs, pesos_cartera_activa)
portfolio_metrics = {}
if portfolio and portfolio.nav is not None:
    calculated_metrics = portfolio.calculate_metrics(risk_free_rate=0.0)
    if calculated_metrics:
        portfolio.metrics = calculated_metrics
        portfolio_metrics = calculated_metrics

# --- RENDERIZADO DE PÁGINA (PARTE 2) ---
render_portfolio_summary(portfolio_metrics, pesos_cartera_activa, ter_ponderado, mapa_isin_nombre, horizonte)
st.markdown("---")
render_funds_analysis(df_funds_metrics, daily_returns, portfolio, mapa_isin_nombre, horizonte)

# --- GUARDADO FINAL ---
if 'carteras' in st.session_state and 'user_info' in st.session_state:
    profile_data_to_save = {
        "subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
        "carteras": st.session_state.get("carteras", {})
    }
    save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)