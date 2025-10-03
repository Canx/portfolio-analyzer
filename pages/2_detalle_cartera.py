# pages/2_detalle_cartera.py

import streamlit as st
import pandas as pd
from streamlit_local_storage import LocalStorage
from src.auth import page_init_and_auth, logout_user
from src.database import save_user_data
from src.portfolio import Portfolio
from src.utils import load_all_navs # Ya no importamos load_config
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import optimize_portfolio
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX
from src.utils import load_funds_from_db, load_all_navs
import plotly.express as px
import plotly.graph_objects as go


@st.dialog("Añadir Fondos a la Cartera")
def add_fund_dialog(mapa_nombre_isin, pesos_actuales):
    """
    Renderiza un diálogo modal para buscar y añadir fondos a la cartera.
    """
    search_term = st.text_input("Buscar por Nombre o ISIN", key="fund_search_dialog")

    # Filtrar candidatos que no están ya en la cartera
    if search_term:
        candidatos = [
            nombre for nombre in mapa_nombre_isin.keys()
            if (search_term.lower() in nombre.lower()) and (mapa_nombre_isin[nombre] not in pesos_actuales)
        ]
    else:
        # Mostrar una lista limitada si no hay búsqueda para no sobrecargar
        candidatos = [
            nombre for nombre in list(mapa_nombre_isin.keys())[:200] # Limitar a 200 resultados sin busqueda
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


def render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre, horizonte):
    """
    Renderiza el contenido principal.
    Añade una comprobación para mostrar un aviso si no hay suficientes datos para los gráficos.
    """
    st.header("Análisis de la Cartera")

    # Gráfico de Tarta (no cambia)
    pesos = (
        st.session_state.get("carteras", {})
        .get(st.session_state.get("cartera_activa"), {})
        .get("pesos", {})
    )
    if pesos and sum(pesos.values()) > 0:
        st.subheader("📊 Distribución de la Cartera")
        df_pie = pd.DataFrame(list(pesos.items()), columns=["ISIN", "Peso"])
        df_pie["Fondo"] = df_pie["ISIN"].map(mapa_isin_nombre)
        fig_pie = px.pie(
            df_pie,
            names="Fondo",
            values="Peso",
            title="Composición Actual de la Cartera",
            hole=0.3,
        )
        fig_pie.update_traces(
            textposition="inside", textinfo="percent+label", pull=[0.05] * len(df_pie)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Tabla de Métricas
    st.subheader(f"📑 Métricas para el horizonte: {horizonte}")
    if not df_metrics.empty:
        # --- BLOQUE MODIFICADO ---
        df_display = df_metrics.rename(
            columns={
                "name": "Nombre",
                "annualized_return_%": "Rent. Anual (%)",
                "volatility_ann_%": "Volatilidad Anual (%)",
                "sharpe_ann": "Ratio Sharpe",
                "sortino_ann": "Ratio Sortino",
                "calmar_ratio": "Ratio Calmar", # <-- NUEVA ETIQUETA
                "max_drawdown_%": "Caída Máxima (%)",
            }
        ).set_index("Nombre")[
            [
                "Rent. Anual (%)",
                "Volatilidad Anual (%)",
                "Ratio Sharpe",
                "Ratio Sortino",
                "Ratio Calmar", # <-- NUEVA COLUMNA
                "Caída Máxima (%)",
            ]
        ]

        df_display = df_display[~df_display.index.duplicated(keep='first')]
        
        # Añadimos el nuevo ratio al coloreado de la tabla
        st.dataframe(
            df_display.style.format("{:.2f}")
                      .background_gradient(cmap='RdYlGn', subset=['Rent. Anual (%)', 'Ratio Sharpe', 'Ratio Sortino', 'Ratio Calmar', 'Caída Máxima (%)'])
                      .background_gradient(cmap='RdYlGn_r', subset=['Volatilidad Anual (%)']),
                      use_container_width=True # 
        )

    st.markdown("---")

    # --- LÓGICA DE GRÁFICOS CORREGIDA ---
    # Comprobamos si hay al menos 2 filas de datos para poder calcular rentabilidades y volatilidad.
    if daily_returns.empty or len(daily_returns) < 2:
        st.warning(
            "No hay suficientes datos históricos en el periodo seleccionado para generar los gráficos."
        )
        st.info(
            "💡 Prueba a seleccionar un horizonte temporal más largo (ej. '1y' o 'max')."
        )
    else:
        # Si hay datos suficientes, mostramos todos los gráficos.
        # Gráfico de Rentabilidad
        st.subheader("📈 Evolución normalizada")
        navs_normalizados = (1 + daily_returns).cumprod()
        navs_normalizados = (navs_normalizados / navs_normalizados.iloc[0]) * 100
        df_plot = navs_normalizados.rename(columns=mapa_isin_nombre).reset_index()
        df_plot = df_plot.melt(
            id_vars="date", var_name="Fondo", value_name="Valor Normalizado"
        )
        fig_rent = px.line(
            df_plot,
            x="date",
            y="Valor Normalizado",
            color="Fondo",
            title="Evolución Normalizada de la Cartera",
        )
        if portfolio and portfolio.nav is not None:
            fig_rent.add_trace(
                go.Scatter(
                    x=portfolio.nav.index,
                    y=portfolio.nav.values,
                    mode="lines",
                    name="💼 Mi Cartera",
                    line=dict(color="black", width=3, dash="dash"),
                )
            )
        st.plotly_chart(fig_rent, use_container_width=True)

        # Gráfico de Volatilidad
        st.subheader("📊 Volatilidad rolling (30d)")
        rolling_vol = daily_returns.rolling(30).std() * (252**0.5) * 100
        df_vol_plot = rolling_vol.rename(columns=mapa_isin_nombre).reset_index()
        df_vol_plot = df_vol_plot.melt(
            id_vars="date", var_name="Fondo", value_name="Volatilidad Anualizada (%)"
        )
        fig_vol = px.line(
            df_vol_plot,
            x="date",
            y="Volatilidad Anualizada (%)",
            color="Fondo",
            title="Volatilidad Anualizada (Rolling 30 días)",
        )
        if portfolio and portfolio.daily_returns is not None:
            portfolio_vol = portfolio.daily_returns.rolling(30).std() * (252**0.5) * 100
            fig_vol.add_trace(
                go.Scatter(
                    x=portfolio_vol.index,
                    y=portfolio_vol.values,
                    mode="lines",
                    name="💼 Mi Cartera",
                    line=dict(color="black", width=3, dash="dash"),
                )
            )
        st.plotly_chart(fig_vol, use_container_width=True)

        # Gráfico de Riesgo vs. Retorno
        if not df_metrics.empty:
            st.subheader("🎯 Riesgo vs. Retorno")
            fondos_metrics = df_metrics[~df_metrics["name"].str.startswith("💼")]
            fig_risk = px.scatter(
                fondos_metrics,
                x="volatility_ann_%",
                y="annualized_return_%",
                text="name",
                hover_name="name",
                title="Riesgo vs. Retorno de los Fondos",
            )
            fig_risk.update_traces(textposition="top center")
            cartera_metrics = df_metrics[df_metrics["name"].str.startswith("💼")]
            if not cartera_metrics.empty:
                fig_risk.add_trace(
                    go.Scatter(
                        x=cartera_metrics["volatility_ann_%"],
                        y=cartera_metrics["annualized_return_%"],
                        mode="markers",
                        marker=dict(color="red", size=15, symbol="star"),
                        name=cartera_metrics.iloc[0]["name"],
                    )
                )
            fig_risk.update_layout(
                xaxis_title="Volatilidad Anualizada (%)",
                yaxis_title="Rentabilidad Anualizada (%)",
            )
            st.plotly_chart(fig_risk, use_container_width=True)

        # --- BLOQUE DE CÓDIGO REINTRODUCIDO ---
        # Gráfico de Correlaciones
        cartera_activa_nombre = st.session_state.get("cartera_activa")
        if cartera_activa_nombre:
            cartera_activa_isines = list(st.session_state.carteras.get(cartera_activa_nombre, {}).get("pesos", {}).keys())
            
            if len(cartera_activa_isines) > 1:
                st.subheader("🔗 Correlación de la Cartera")
                
                # Nos aseguramos de que solo usamos las columnas que existen en daily_returns
                returns_cartera = daily_returns[[isin for isin in cartera_activa_isines if isin in daily_returns.columns]]
                
                corr_matrix = returns_cartera.corr()
                
                # Renombramos para que sea legible
                corr_matrix.columns = [mapa_isin_nombre.get(c, c) for c in corr_matrix.columns]
                corr_matrix.index = [mapa_isin_nombre.get(i, i) for i in corr_matrix.index]
                
                fig_corr = px.imshow(corr_matrix, text_auto=True, aspect="auto",
                                       color_continuous_scale='RdBu_r', range_color=[-1, 1],
                                       title="Matriz de Correlación de la Cartera Activa")
                st.plotly_chart(fig_corr, use_container_width=True)

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

# --- COMPROBACIÓN DE CARTERA ACTIVA ---
if not st.session_state.get("cartera_activa"):
    st.info("⬅️ No has seleccionado ninguna cartera.")
    if st.button("⬅️ Volver a Mis Carteras"):
        st.switch_page("pages/2_carteras.py")
    st.stop()

cartera_activa_nombre = st.session_state.cartera_activa
st.title(f"📈 Análisis de: {cartera_activa_nombre}")

# --- RENDERIZADO DE LA SIDEBAR DE ANÁLISIS ---
def render_analysis_sidebar(mapa_nombre_isin, mapa_isin_nombre):
    # (Esta función no necesita grandes cambios, ya que usa los diccionarios)
    run_optimization = False
    modelo_seleccionado = None
    risk_measure = 'MV'
    target_return = 0.0

    with st.sidebar:
        st.write(f"Usuario: {st.session_state.user_info.get('email')}")
        if st.button("Cerrar Sesión"):
            localS = LocalStorage()
            logout_user(localS)
            st.rerun()
        
        st.markdown("---")
        if st.button("⬅️ Volver a Mis Carteras"):
            st.switch_page("pages/2_carteras.py")
        st.markdown("---")
        
        st.header("Configuración del Análisis")
        horizonte = st.selectbox("Horizonte temporal", HORIZONTE_OPCIONES, index=HORIZONTE_DEFAULT_INDEX, key="horizonte_detalle")
        
        st.header(f"💼 Composición de '{cartera_activa_nombre}'")
        pesos_actuales = st.session_state.carteras[cartera_activa_nombre]['pesos']
        
        if st.button("➕ Añadir Fondo a la Cartera", use_container_width=True):
            add_fund_dialog(mapa_nombre_isin, pesos_actuales)

        for isin in sorted(pesos_actuales.keys()):
            col_name, col_slider, col_del = st.columns([3, 6, 1])
            with col_name:
                st.markdown(mapa_isin_nombre.get(isin, isin))
            with col_slider:
                nuevo_peso = st.slider("Peso %", 0, 100, pesos_actuales[isin], 1, key=f"peso_{isin}", label_visibility="collapsed")
                if nuevo_peso != pesos_actuales[isin]:
                    pesos_actuales[isin] = nuevo_peso
            with col_del:
                if st.button("🗑️", key=f"remove_{isin}", help="Eliminar fondo"):
                    del pesos_actuales[isin]
                    st.rerun()

        if pesos_actuales:
            total_peso = sum(pesos_actuales.values())
            st.metric("Suma Total", f"{total_peso}%")
            if total_peso != 100: st.error(f"⚠️ La suma debe ser 100%.")
        
        st.markdown("---")
        st.subheader("⚖️ Optimización")
        if st.session_state.user_info.get("subscription_plan") == "premium":
            opciones_optimizacion = ["MSR", "MSoR", "MCR", "MV", "HRP", "CVaR", "ERC"]
            modelo_seleccionado = st.selectbox("Selecciona un modelo", opciones_optimizacion, index=0, format_func=lambda x: {"MSR": "Máximo Ratio de Sharpe", "MSoR": "Máximo Ratio de Sortino", "MCR": "Máximo Ratio de Calmar", "MV": "Mínima Volatilidad", "HRP": "Hierarchical Risk Parity", "CVaR": "Mínimo CVaR (Pérdida Esperada)", "ERC": "Contribución Equitativa al Riesgo (ERC)"}[x])
            run_optimization = st.button("🚀 Optimizar Cartera")
        else:
            st.info("La optimización es una funcionalidad Premium.")
            if st.button("✨ Mejorar a Premium"):
                st.switch_page("pages/4_cuenta.py")
                
    return horizonte, run_optimization, modelo_seleccionado, risk_measure, target_return

# --- FLUJO PRINCIPAL ---

# 1. CARGAR CATÁLOGO DESDE LA BASE DE DATOS
df_catalogo = load_funds_from_db()
if df_catalogo.empty:
    st.error("No se pudo cargar el catálogo de fondos desde la base de datos.")
    st.stop()

# 2. CREAR DICCIONARIOS DE MAPEADO (usando la columna 'name')
mapa_isin_nombre = pd.Series(df_catalogo['name'].values, index=df_catalogo['isin']).to_dict()
mapa_nombre_isin = {f"{row['name']} ({row['isin']})": row['isin'] for index, row in df_catalogo.iterrows()}
data_manager = DataManager()

# 3. RENDERIZAR SIDEBAR
horizonte, run_optimization, modelo_seleccionado, risk_measure, target_return = render_analysis_sidebar(mapa_nombre_isin, mapa_isin_nombre)

# 4. OBTENER DATOS DE LA CARTERA ACTIVA
pesos_cartera_activa = st.session_state.carteras[cartera_activa_nombre]["pesos"]
isines_a_cargar = tuple(pesos_cartera_activa.keys())

if not isines_a_cargar:
    st.warning("Esta cartera está vacía. Añade fondos desde la barra lateral.")
    st.stop()

# 5. CARGA DE DATOS DE PRECIOS
all_navs_df = load_all_navs(data_manager, isines_a_cargar)
if all_navs_df.empty:
    st.warning("No se encontraron datos de precios para los fondos de esta cartera.")
    st.stop()

filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns = filtered_navs.pct_change().dropna()

# 6. LÓGICA DE OPTIMIZACIÓN
if run_optimization and not daily_returns.empty:
    st.info(f"Ejecutando optimización con el modelo: {modelo_seleccionado}...")
    pesos_opt = optimize_portfolio(
        daily_returns,
        model=modelo_seleccionado,
        risk_measure=risk_measure
    )

    if pesos_opt is not None:
        pesos_opt_dict = {isin: int(round(p * 100)) for isin, p in pesos_opt.items()}
        resto = 100 - sum(pesos_opt_dict.values())
        if resto != 0 and not pesos_opt.empty:
            pesos_opt_dict[pesos_opt.idxmax()] += resto
        st.session_state.carteras[cartera_activa_nombre]["pesos"] = pesos_opt_dict
        st.success(
            f"Cartera '{cartera_activa_nombre}' optimizada con {modelo_seleccionado} ✅"
        )
        st.rerun()
    elif modelo_seleccionado == 'TARGET_RET':
        st.error(f"No se encontró ninguna cartera que cumpla con una rentabilidad objetivo del {target_return}%. Prueba con un valor más bajo o un horizonte temporal más largo.")
    else:
        st.error("No se pudo optimizar la cartera con los parámetros seleccionados.")

if pesos_cartera_activa:
    # 1. Creamos un "mapa" de ISIN -> TER para una búsqueda ultra-rápida.
    #    Esto es mucho más eficiente que recorrer una lista en cada iteración.
    ter_map = pd.Series(df_catalogo['ter'].values, index=df_catalogo['isin']).to_dict()

    ter_ponderado = 0
    for isin, peso in pesos_cartera_activa.items():
        # Buscamos el TER del fondo directamente en nuestro mapa
        ter_fondo = ter_map.get(isin, 0)
        
        # Nos aseguramos de que el TER sea un número (si es nulo, usamos 0)
        ter_numerico = pd.to_numeric(ter_fondo, errors='coerce')
        ter_numerico = 0 if pd.isna(ter_numerico) else ter_numerico
        
        ter_ponderado += (peso / 100) * ter_numerico
    
    st.metric("Costo Total de la Cartera (TER Ponderado)", f"{ter_ponderado:.2f}%")
    st.markdown("---")

# --- CÁLCULO DE MÉTRICAS Y CARTERA (BLOQUE CORREGIDO) ---

# 1. Creamos el mapa de datos de fondos a partir del catálogo
mapa_datos_fondos = df_catalogo.set_index('isin').to_dict('index')
metricas = []

# 2. Calculamos las métricas para cada fondo individual
for isin in daily_returns.columns:
    m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
    datos_fondo = mapa_datos_fondos.get(isin, {})
    m.update(datos_fondo)
    metricas.append(m)

# 3. Creamos el DataFrame de métricas
df_metrics = pd.DataFrame(metricas)

# --- SOLUCIÓN CLAVE ---
# 4. Nos aseguramos de que la columna 'isin' exista, incluso si el DataFrame está vacío
if 'isin' not in df_metrics.columns:
    df_metrics['isin'] = pd.Series(dtype='str')

    # 5. Calculamos las métricas de la cartera y las añadimos a la tabla
    portfolio = Portfolio(filtered_navs, pesos_cartera_activa)
    portfolio_metrics = {}
    # Asumimos una tasa libre de riesgo de 0.0 para el cálculo de métricas de cartera
    risk_free_rate_for_portfolio = 0.0
    if portfolio and portfolio.nav is not None:
        metricas_cartera = portfolio.calculate_metrics(risk_free_rate=risk_free_rate_for_portfolio)
        metricas_cartera["name"] = f"💼 {cartera_activa_nombre}"
        portfolio_metrics = metricas_cartera
        df_metrics = pd.concat([pd.DataFrame([metricas_cartera]), df_metrics], ignore_index=True)
# 5. Ordenamos la tabla para mostrar la cartera primero
if not df_metrics.empty:
    df_metrics["peso_cartera"] = df_metrics["isin"].map(pesos_cartera_activa).fillna(0)
    
    # --- LÍNEA CORREGIDA ---
    # Añadimos .fillna(False) para manejar los nombres nulos de forma segura
    df_metrics.loc[df_metrics["name"].str.startswith("💼").fillna(False), "peso_cartera"] = 101
    
    df_metrics = df_metrics.sort_values(by="peso_cartera", ascending=False).drop(
        columns=["peso_cartera"]
    )

# 8. RENDERIZAR RESULTADOS
# (Asegúrate de que esta llamada a render_main_content esté después del bloque de cálculo)
render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre, horizonte)

@st.cache_data
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    with st.spinner("Cargando datos..."):
        all_navs = {}
        for isin in isines:
            force = isin == force_update_isin
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None:
                all_navs[isin] = df["nav"]
    if not all_navs:
        return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()

# GUARDADO FINAL DE DATOS
if 'carteras' in st.session_state and 'user_info' in st.session_state:
    profile_data_to_save = {
        "subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
        "carteras": st.session_state.get("carteras", {})
    }
    save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)