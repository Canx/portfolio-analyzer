# pages/2_cartera.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from streamlit_local_storage import LocalStorage
from src.utils import load_config, load_all_navs
import plotly.express as px
import plotly.graph_objects as go

# Importaciones de los módulos
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.portfolio import Portfolio
from src.state import initialize_session_state
from src.optimizer import optimize_portfolio
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX

from src.database import save_user_data
from src.auth import logout_user
from src.auth import page_init_and_auth

auth, db = page_init_and_auth()

# --- Bloque de Protección ---
if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    # Ofrecemos un enlace para facilitar la navegación al login
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop() # Detenemos la ejecución del resto de la página

# --- BOTÓN DE LOGOUT EN LA SIDEBAR ---
with st.sidebar:
    st.write(f"Usuario: {st.session_state.user_info.get('email')}")
    if st.button("Cerrar Sesión"):
        logout_user()
        st.switch_page("app.py")


def render_sidebar(mapa_nombre_isin, mapa_isin_nombre):
    """
    Renderiza la barra lateral con un completo gestor de carteras,
    incluyendo la opción de crear una cartera nueva y vacía.
    """
    with st.sidebar:
        st.header("Configuración del Análisis")
        horizonte = st.sidebar.selectbox(
            "Horizonte temporal",
            HORIZONTE_OPCIONES,
            index=HORIZONTE_DEFAULT_INDEX,
            key="horizonte")
        st.markdown("---")
        st.header("🗂️ Gestor de Carteras")
        
        lista_carteras = list(st.session_state.carteras.keys())
        if not lista_carteras:
            st.session_state.carteras["Mi Primera Cartera"] = {"pesos": {}}
            st.session_state.cartera_activa = "Mi Primera Cartera"
            st.rerun()

        cartera_seleccionada = st.selectbox(
            "Cartera Activa",
            lista_carteras,
            index=lista_carteras.index(st.session_state.cartera_activa) if st.session_state.cartera_activa in lista_carteras else 0
        )
        if cartera_seleccionada != st.session_state.cartera_activa:
            st.session_state.cartera_activa = cartera_seleccionada
            st.rerun()

        with st.expander("Opciones de Gestión"):
            # --- FORMULARIO PARA CREAR CARTERA NUEVA ---
            with st.form("form_create_portfolio"):
                st.markdown("**Crear nueva cartera vacía**")
                new_portfolio_name = st.text_input("Nombre de la nueva cartera", label_visibility="collapsed")
                submitted_create = st.form_submit_button("➕ Crear")
                if submitted_create and new_portfolio_name:
                    if new_portfolio_name in st.session_state.carteras:
                        st.warning("Ya existe una cartera con ese nombre.")
                    else:
                        st.session_state.carteras[new_portfolio_name] = {"pesos": {}}
                        st.session_state.cartera_activa = new_portfolio_name
                        st.rerun()
            
            st.markdown("---")

            # --- Opciones para la cartera activa ---
            if st.session_state.cartera_activa:
                st.markdown(f"**Opciones para '{st.session_state.cartera_activa}'**")
                
                # --- NUEVO: FORMULARIO PARA RENOMBRAR CARTERA ---
                with st.form("form_rename_portfolio"):
                    st.markdown("**Renombrar cartera activa**")
                    new_name = st.text_input(
                        "Nuevo nombre",
                        value=st.session_state.cartera_activa,
                        label_visibility="collapsed"
                    )
                    submitted_rename = st.form_submit_button("🔁 Renombrar")

                    if submitted_rename:
                        old_name = st.session_state.cartera_activa
                        if new_name and new_name != old_name:
                            if new_name in st.session_state.carteras:
                                st.warning("Ya existe una cartera con ese nombre.")
                            else:
                                # Renombramos la cartera
                                st.session_state.carteras[new_name] = st.session_state.carteras.pop(old_name)
                                st.session_state.cartera_activa = new_name
                                st.toast(f"Cartera '{old_name}' renombrada a '{new_name}'!")
                                st.rerun()
                
                # Botones de Copiar y Borrar
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("❐ Copiar", help=f"Crea un duplicado de '{st.session_state.cartera_activa}'"):
                        nombre_original = st.session_state.cartera_activa
                        nuevo_nombre = f"Copia de {nombre_original}"
                        i = 1
                        while nuevo_nombre in st.session_state.carteras:
                            i += 1
                            nuevo_nombre = f"Copia ({i}) de {nombre_original}"
                        st.session_state.carteras[nuevo_nombre] = st.session_state.carteras[nombre_original].copy()
                        st.session_state.cartera_activa = nuevo_nombre
                        st.toast(f"Cartera '{nombre_original}' copiada a '{nuevo_nombre}'!")
                        st.rerun()
                with col2:
                    if st.button("🗑️ Borrar", type="primary", help=f"Elimina la cartera '{st.session_state.cartera_activa}'"):
                        del st.session_state.carteras[st.session_state.cartera_activa]
                        st.session_state.cartera_activa = next(iter(st.session_state.carteras), None)
                        st.rerun()
    
        
        st.markdown("---")

        run_optimization = False
        modelo_optimización = None
        risk_measure = None

        if st.session_state.cartera_activa:
            st.header(f"💼 Composición de '{st.session_state.cartera_activa}'")
            st.number_input("Monto total de la cartera (€)", min_value=0, step=1000, key='total_investment_amount')
            total_amount = st.session_state.total_investment_amount
            
            pesos_actuales = st.session_state.carteras[st.session_state.cartera_activa]['pesos']
            
            # --- LÓGICA PARA AÑADIR FONDOS ---
            cartera_actual_isines = pesos_actuales.keys()
            candidatos = [n for n in mapa_nombre_isin.keys() if mapa_nombre_isin[n] not in cartera_actual_isines]
            add_sel = st.selectbox("Añadir fondo a la cartera", ["—"] + candidatos, index=0, key=f"add_fund_{st.session_state.cartera_activa}")
            if add_sel != "—" and st.button("➕ Añadir"):
                nuevo_isin = mapa_nombre_isin[add_sel]
                pesos_actuales[nuevo_isin] = 0
                st.rerun()

            isines_ordenados = sorted(pesos_actuales.keys(), key=lambda isin: pesos_actuales.get(isin, 0), reverse=True)
            
            # --- BUCLE DE VISUALIZACIÓN DE FONDOS ---
            for isin in isines_ordenados:
                col_name, col_minus, col_slider, col_plus, col_del = st.columns([4, 1, 4, 1, 1])
                with col_name:
                    st.markdown(f"**{mapa_isin_nombre.get(isin, isin)}**")
                    peso_en_porcentaje = pesos_actuales.get(isin, 0)
                    cantidad_en_euros = (peso_en_porcentaje / 100) * total_amount
                    st.caption(f"{cantidad_en_euros:,.2f} €")
                
                peso_actual = pesos_actuales.get(isin, 0)
                with col_minus:
                    if st.button("➖", key=f"minus_{st.session_state.cartera_activa}_{isin}"):
                        if peso_actual > 0: 
                            pesos_actuales[isin] = peso_actual - 1
                            st.rerun()
                with col_slider:
                    nuevo_peso = st.slider("Peso %", 0, 100, peso_actual, 1, key=f"peso_{st.session_state.cartera_activa}_{isin}", label_visibility="collapsed")
                    if nuevo_peso != peso_actual:
                        pesos_actuales[isin] = nuevo_peso
                        # No es necesario rerun, el slider lo provoca
                with col_plus:
                    if st.button("➕", key=f"plus_{st.session_state.cartera_activa}_{isin}"):
                        if peso_actual < 100: 
                            pesos_actuales[isin] = peso_actual + 1
                            st.rerun()
                with col_del:
                    if st.button("🗑️", key=f"remove_{st.session_state.cartera_activa}_{isin}"):
                        del pesos_actuales[isin]
                        st.rerun()

            if pesos_actuales:
                total_peso = sum(pesos_actuales.values())
                st.metric("Suma Total", f"{total_peso}%")
                if total_peso != 100:
                    st.error(f"⚠️ La suma de los pesos debe ser 100%. Actualmente es {total_peso}%.")

            st.markdown("---")
            st.subheader("⚖️ Optimización")

            # --- SECCIÓN MODIFICADA ---
            opciones_optimizacion = ["MSR", "MV", "HRP"] # Añadimos el nuevo modelo
            
            modelo_optimización = st.selectbox(
                "Selecciona un modelo",
                options=opciones_optimizacion,
                index=0,
                format_func=lambda x: {
                    "MSR": "Máximo Ratio de Sharpe",
                    "MV": "Mínima Volatilidad",
                    "HRP": "Hierarchical Risk Parity"   
                }[x],
                key=f"model_{st.session_state.cartera_activa}"
            )

            risk_measure = 'MV'
            if modelo_optimización == 'HRP':
                rms_disponibles = ['MV', 'MAD', 'MSV', 'VaR', 'CVaR', 'CDaR']
                rms_nombres = {'MV': 'Varianza', 'MAD': 'Desviación Absoluta', 'MSV': 'Semi Varianza', 'VaR': 'Valor en Riesgo', 'CVaR': 'VaR Condicional', 'CDaR': 'Drawdown Condicional'}
                risk_measure = st.selectbox("Medida de Riesgo (para HRP)", rms_disponibles, format_func=lambda x: rms_nombres.get(x, x), key=f"rm_{st.session_state.cartera_activa}")
            
            run_optimization = st.button("🚀 Optimizar Cartera")
        else:
            st.warning("Crea o selecciona una cartera para continuar.")
        
    return horizonte, run_optimization, modelo_optimización, risk_measure

def render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre):
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

    # Tabla de Métricas (no cambia)
    st.subheader(f"📑 Métricas para el horizonte: {st.session_state.horizonte}")
    if not df_metrics.empty:
        df_display = df_metrics.rename(
            columns={
                "nombre": "Nombre",
                "annualized_return_%": "Rent. Anual (%)",
                "volatility_ann_%": "Volatilidad Anual (%)",
                "sharpe_ann": "Ratio Sharpe",
                "max_drawdown_%": "Caída Máxima (%)",
            }
        ).set_index("Nombre")[
            [
                "Rent. Anual (%)",
                "Volatilidad Anual (%)",
                "Ratio Sharpe",
                "Caída Máxima (%)",
            ]
        ]
        # --- LÍNEA MODIFICADA ---
        st.dataframe(
        df_display.style.format("{:.2f}")
                  .background_gradient(cmap='RdYlGn', subset=['Rent. Anual (%)', 'Ratio Sharpe', 'Caída Máxima (%)'])
                  # --- LÍNEA CORREGIDA ---
                  .background_gradient(cmap='RdYlGn_r', subset=['Volatilidad Anual (%)'])
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
            fondos_metrics = df_metrics[~df_metrics["nombre"].str.startswith("💼")]
            fig_risk = px.scatter(
                fondos_metrics,
                x="volatility_ann_%",
                y="annualized_return_%",
                text="nombre",
                hover_name="nombre",
                title="Riesgo vs. Retorno de los Fondos",
            )
            fig_risk.update_traces(textposition="top center")
            cartera_metrics = df_metrics[df_metrics["nombre"].str.startswith("💼")]
            if not cartera_metrics.empty:
                fig_risk.add_trace(
                    go.Scatter(
                        x=cartera_metrics["volatility_ann_%"],
                        y=cartera_metrics["annualized_return_%"],
                        mode="markers",
                        marker=dict(color="red", size=15, symbol="star"),
                        name=cartera_metrics.iloc[0]["nombre"],
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


def render_update_panel(isines, mapa_isin_nombre):
    """Muestra el panel para forzar la actualización de los datos."""
    st.markdown("---")
    st.subheader("📅 Estado de actualización de los fondos")

    for isin in isines:
        c1, c2, c3 = st.columns([4, 2, 2])
        c1.write(mapa_isin_nombre.get(isin, isin))

        file_path = Path("fondos_data") / f"{isin}.csv"
        if file_path.exists():
            try:
                # --- AQUÍ ESTÁ EL ARREGLO ---
                # 1. Leemos solo la columna de fechas para que sea rápido.
                df_dates = pd.read_csv(file_path, usecols=["date"])
                # 2. Obtenemos el último valor de esa columna.
                last_date = df_dates.iloc[-1, 0]
                c2.write(f"Último dato: {last_date}")
            except (pd.errors.EmptyDataError, IndexError):
                c2.write("Fichero vacío")
        else:
            c2.write("No descargado")

        if c3.button("🔄 Actualizar", key=f"update_{isin}"):
            # 1. Forzamos la actualización de metadatos en fondos.json
            update_fund_details_in_config(isin)
            # 2. Forzamos la actualización del NAV (CSV)
            st.session_state.force_update_isin = isin
            # 3. Limpiamos toda la caché para recargar ambos ficheros y re-ejecutamos
            st.cache_data.clear()
            st.rerun()



def render_efficient_frontier(frontier_df: pd.DataFrame, df_metrics: pd.DataFrame, portfolio_metrics: dict):
    """
    Dibuja el gráfico de la Frontera Eficiente.
    
    Args:
        frontier_df (pd.DataFrame): DataFrame con los puntos de la frontera.
        df_metrics (pd.DataFrame): DataFrame con las métricas de los fondos individuales.
        portfolio_metrics (dict): Diccionario con las métricas de la cartera activa.
    """
    st.markdown("---")
    st.subheader("🌐 Frontera Eficiente")
    st.write(
        "Este gráfico muestra el conjunto de carteras óptimas. "
        "Tu objetivo es situar tu cartera (la estrella) lo más cerca posible de la curva, "
        "en el punto que mejor se ajuste a tu perfil de riesgo/retorno."
    )

    # Creamos la figura
    fig = go.Figure()

    # 1. Añadimos la curva de la frontera eficiente
    fig.add_trace(
        go.Scatter(
            x=frontier_df['volatility_ann_%'],
            y=frontier_df['annualized_return_%'],
            mode='lines',
            name='Frontera Eficiente',
            line=dict(color='blue', width=2, dash='dash')
        )
    )

    # 2. Añadimos los puntos de los fondos individuales
    fondos_metrics = df_metrics[~df_metrics["nombre"].str.startswith('💼')]
    fig.add_trace(
        go.Scatter(
            x=fondos_metrics['volatility_ann_%'],
            y=fondos_metrics['annualized_return_%'],
            mode='markers',
            marker=dict(size=8),
            name='Fondos Individuales',
            text=fondos_metrics['nombre'], # Texto para el hover
            hoverinfo='text+x+y'
        )
    )

    # 3. Añadimos el punto de la cartera activa
    if portfolio_metrics:
        fig.add_trace(
            go.Scatter(
                x=[portfolio_metrics['volatility_ann_%']],
                y=[portfolio_metrics['annualized_return_%']],
                mode='markers',
                marker=dict(color='red', size=15, symbol='star'),
                name=portfolio_metrics['nombre'],
                hoverinfo='name+x+y'
            )
        )
        
    fig.update_layout(
        title="Frontera Eficiente de la Cartera",
        xaxis_title="Volatilidad Anualizada (%)",
        yaxis_title="Rentabilidad Anualizada (%)",
        legend_title="Leyenda",
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)


# ==============================
#   FLUJO PRINCIPAL DE LA PÁGINA
# ==============================

# 1. CARGAR CONFIGURACIÓN
st.title("📈 Análisis de Cartera")
fondos_config = load_config()
if not fondos_config:
    st.stop()
mapa_isin_nombre = {f["isin"]: f["nombre"] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f["isin"] for f in fondos_config}
data_manager = DataManager()

# 2. RENDERIZAR SIDEBAR Y OBTENER ACCIONES
horizonte, run_optimization, modelo_seleccionado, risk_measure = render_sidebar(
    mapa_nombre_isin, mapa_isin_nombre
)


# 3. VERIFICAR SI HAY UNA CARTERA ACTIVA
if not st.session_state.get("cartera_activa") or not st.session_state.carteras.get(
    st.session_state.cartera_activa
):
    st.info(
        "⬅️ Por favor, crea o selecciona una cartera en la barra lateral para empezar el análisis."
    )
    st.stop()

# 4. OBTENER DATOS DE LA CARTERA ACTIVA
cartera_activa_nombre = st.session_state.cartera_activa
cartera_activa_data = st.session_state.carteras[cartera_activa_nombre]
pesos_cartera_activa = cartera_activa_data["pesos"]
isines_a_cargar = tuple(pesos_cartera_activa.keys())

if not isines_a_cargar:
    st.warning("Tu cartera está vacía. Añade fondos desde la barra lateral.")
    st.stop()

# 5. CARGA DE DATOS Y PROCESADO
with st.spinner(f"Cargando datos de precios para {len(isines_a_cargar)} fondos en la cartera..."):
    all_navs_df = load_all_navs(data_manager, isines_a_cargar)
if all_navs_df.empty:
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

# --- NUEVO: CÁLCULO DEL TER PONDERADO ---
if pesos_cartera_activa:
    ter_ponderado = 0
    for isin, peso in pesos_cartera_activa.items():
        # Buscamos el TER del fondo en la configuración
        ter_fondo = next((f.get('ter', 0) for f in fondos_config if f.get('isin') == isin), 0)
        # Nos aseguramos de que el TER sea un número
        try:
            ter_numerico = float(ter_fondo)
        except (ValueError, TypeError):
            ter_numerico = 0
        
        ter_ponderado += (peso / 100) * ter_numerico
    
    # Mostramos el resultado en una métrica
    st.metric("Costo Total de la Cartera (TER Ponderado)", f"{ter_ponderado:.2f}%")
    st.markdown("---")

# 7. CÁLCULO DE MÉTRICAS Y CARTERA
mapa_datos_fondos = {f["isin"]: f for f in fondos_config}
metricas = []
for isin in daily_returns.columns:
    m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
    datos_fondo = mapa_datos_fondos.get(isin, {})
    m.update(datos_fondo)
    metricas.append(m)
df_metrics = pd.DataFrame(metricas)

portfolio = Portfolio(filtered_navs, pesos_cartera_activa)
portfolio_metrics = {}
if portfolio and portfolio.nav is not None:
    metricas_cartera = portfolio.calculate_metrics()
    metricas_cartera["nombre"] = f"💼 {cartera_activa_nombre}"
    portfolio_metrics = metricas_cartera
    df_metrics = pd.concat([pd.DataFrame([metricas_cartera]), df_metrics], ignore_index=True)

df_metrics["peso_cartera"] = df_metrics["isin"].map(pesos_cartera_activa).fillna(0)
df_metrics.loc[df_metrics["nombre"].str.startswith("💼"), "peso_cartera"] = 101
df_metrics = df_metrics.sort_values(by="peso_cartera", ascending=False).drop(
    columns=["peso_cartera"]
)

# 8. RENDERIZAR RESULTADOS
render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre)

@st.cache_data
def load_config(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])


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


if 'carteras' in st.session_state and 'user_info' in st.session_state and st.session_state.user_info:
    save_user_data(db, st.session_state.user_info, "carteras", st.session_state.carteras)

