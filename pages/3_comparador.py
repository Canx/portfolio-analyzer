import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_local_storage import LocalStorage

# Importaciones de funciones compartidas
from src.state import initialize_session_state
from src.utils import load_all_navs, load_funds_from_db
from src.data_manager import DataManager, filtrar_por_horizonte
from src.portfolio import Portfolio
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX
from src.auth import page_init_and_auth, logout_user

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
        logout_user(localS)
        st.switch_page("app.py")

st.set_page_config(
    page_title="Comparador de Carteras",
    page_icon="📊",
    layout="wide"
)
initialize_session_state()
localS = LocalStorage()

st.title("📊 Comparador de Carteras y Fondos")
st.write("Selecciona carteras y/o fondos individuales para comparar su rendimiento y métricas.")

# --- Carga de datos de configuración ---
df_catalogo = load_funds_from_db()
if df_catalogo.empty:
    st.error("No se pudo cargar el catálogo de fondos desde la base de datos.")
    st.stop()

mapa_isin_nombre = pd.Series(df_catalogo['name'].values, index=df_catalogo['isin']).to_dict()
mapa_nombre_isin = {f"{row['name']} ({row['isin']})": row['isin'] for index, row in df_catalogo.iterrows()}
nombres_fondos_catalogo = list(mapa_nombre_isin.keys())
lista_carteras = list(st.session_state.carteras.keys())

# --- Lógica de Carga de la última comparación ---
default_carteras = []
default_fondos_nombres = []
saved_comp_json = localS.getItem('saved_comparison')
if saved_comp_json:
    try:
        saved_comp = json.loads(saved_comp_json)
        # Nos aseguramos de que las carteras y fondos guardados todavía existen
        default_carteras = [c for c in saved_comp.get('carteras', []) if c in lista_carteras]
        saved_fondos_isines = saved_comp.get('fondos', [])
        default_fondos_nombres = [name for name, isin in mapa_nombre_isin.items() if isin in saved_fondos_isines]
    except (json.JSONDecodeError, TypeError):
        # Si hay un error en los datos guardados, empezamos de cero
        pass

# --- Selectores ---
col1, col2 = st.columns(2)
with col1:
    carteras_seleccionadas = st.multiselect(
        "Selecciona Carteras",
        options=lista_carteras,
        default=default_carteras # Usamos el valor cargado
    )
with col2:
    fondos_seleccionados_nombres = st.multiselect(
        "Añadir Fondos Individuales a la Comparación",
        options=nombres_fondos_catalogo,
        default=default_fondos_nombres # Usamos el valor cargado
    )


# --- Lógica de Guardado de la nueva comparación ---
fondos_seleccionados_isines = [mapa_nombre_isin[n] for n in fondos_seleccionados_nombres]
current_comp = {
    "carteras": carteras_seleccionadas,
    "fondos": fondos_seleccionados_isines
}
localS.setItem('saved_comparison', json.dumps(current_comp))


if not carteras_seleccionadas and not fondos_seleccionados_isines:
    st.info("Por favor, selecciona al menos una cartera o un fondo para iniciar la comparación.")
    st.stop()

# --- Selector de Horizonte en la Sidebar ---
horizonte = st.sidebar.selectbox(
            "Horizonte temporal",
            HORIZONTE_OPCIONES,
            index=HORIZONTE_DEFAULT_INDEX,
            key="horizonte"
        )

st.markdown("---")

# --- Carga y Procesamiento de Datos ---
todos_los_isines = set(fondos_seleccionados_isines)
for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras.get(nombre_cartera, {}).get("pesos", {})
    todos_los_isines.update(pesos.keys())

data_manager = DataManager()
with st.spinner(f"Cargando datos de precios para {len(todos_los_isines)} fondos seleccionados..."):
    all_navs_df = load_all_navs(data_manager, tuple(sorted(todos_los_isines)))

if all_navs_df.empty:
    st.error("No se pudieron cargar los datos de los fondos para la comparación."); st.stop()

# --- Bucle de Cálculo ---
lista_metricas = []
navs_a_graficar = {}
returns_a_correlacionar = {} # <-- NUEVO: Diccionario para guardar las rentabilidades

# 1. Procesar las carteras compuestas
for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras[nombre_cartera].get("pesos", {})
    # Filtramos el DataFrame para quedarnos solo con los ISINs de esta cartera
    isin_cartera = list(pesos.keys())
    navs_cartera = all_navs_df[isin_cartera].dropna(how='all')
    filtered_navs = filtrar_por_horizonte(navs_cartera, horizonte)

    portfolio_obj = Portfolio(nav_data=filtered_navs, weights=pesos)
    nombre_display = f"💼 {nombre_cartera}"
    if portfolio_obj.daily_returns is not None and len(portfolio_obj.daily_returns.dropna()) > 1:
        metricas = portfolio_obj.calculate_metrics(); metricas["nombre"] = nombre_display
        lista_metricas.append(metricas)
        returns_a_correlacionar[nombre_display] = portfolio_obj.daily_returns # <-- Guardamos rentabilidades
    if portfolio_obj.nav is not None:
        navs_a_graficar[nombre_display] = portfolio_obj.nav

# 2. Procesar los fondos individuales
for isin in fondos_seleccionados_isines:
    # Creamos un DF solo para este ISIN y eliminamos NaNs al final
    nav_fondo = all_navs_df[[isin]].dropna()
    filtered_navs = filtrar_por_horizonte(nav_fondo, horizonte)
    
    pesos = {isin: 100}
    portfolio_obj = Portfolio(nav_data=filtered_navs, weights=pesos)
    nombre_display = mapa_isin_nombre.get(isin, isin)
    if portfolio_obj.daily_returns is not None and len(portfolio_obj.daily_returns.dropna()) > 1:
        metricas = portfolio_obj.calculate_metrics(); metricas["nombre"] = nombre_display
        lista_metricas.append(metricas)
        returns_a_correlacionar[nombre_display] = portfolio_obj.daily_returns # <-- Guardamos rentabilidades
    if portfolio_obj.nav is not None:
        navs_a_graficar[nombre_display] = portfolio_obj.nav

# --- Visualización de Resultados ---
# --- Visualización de Resultados ---
if lista_metricas:
    st.subheader("📈 Tabla Comparativa de Métricas")
    df_comparativa = pd.DataFrame(lista_metricas)
    
    # --- BLOQUE MODIFICADO ---
    df_display = df_comparativa.rename(columns={
        "nombre": "Activo", 
        "annualized_return_%": "Rent. Anual (%)",
        "volatility_ann_%": "Volatilidad (%)", 
        "sharpe_ann": "Ratio Sharpe",
        "sortino_ann": "Ratio Sortino", # <-- NUEVA ETIQUETA
        "max_drawdown_%": "Caída Máxima (%)"
    }).set_index("Activo")[
        [
            "Rent. Anual (%)", 
            "Volatilidad (%)", 
            "Ratio Sharpe", 
            "Ratio Sortino", # <-- NUEVA COLUMNA
            "Caída Máxima (%)"
        ]
    ]
    
    # Añadimos la nueva columna al coloreado y la opción de expandir
    st.dataframe(
        df_display.style.format("{:.2f}")
                  .background_gradient(cmap='RdYlGn', subset=['Rent. Anual (%)', 'Ratio Sharpe', 'Ratio Sortino', 'Caída Máxima (%)'])
                  .background_gradient(cmap='RdYlGn_r', subset=['Volatilidad (%)']),
        use_container_width=True
    )

st.markdown("---")

if navs_a_graficar:
    st.subheader("🚀 Gráfico Comparativo de Rendimiento")
    df_grafico = pd.DataFrame(navs_a_graficar)
    
    # Preparamos los datos para Plotly
    df_plot_melted = df_grafico.reset_index().melt(id_vars="date", var_name="Activo", value_name="Valor Normalizado")
    
    fig = px.line(
        df_plot_melted, 
        x='date', 
        y='Valor Normalizado', 
        color='Activo',
        title=f"Rendimiento Comparado ({horizonte})"
    )
    st.plotly_chart(fig, use_container_width=True)

# --- NUEVO: Gráfico de Matriz de Correlación ---
if len(returns_a_correlacionar) > 1:
    st.markdown("---")
    st.subheader("🔗 Matriz de Correlación")
    
    # Combinamos todas las series de rentabilidades en un único DataFrame
    df_corr = pd.DataFrame(returns_a_correlacionar)
    
    # Calculamos la matriz de correlación
    corr_matrix = df_corr.corr()

    # Creamos el gráfico de calor
    fig_corr = px.imshow(
        corr_matrix,
        text_auto=True,
        aspect="auto",
        color_continuous_scale='RdBu_r', # Paleta de color rojo/azul
        range_color=[-1, 1],             # Rango de -1 (rojo) a 1 (azul)
        title="Correlación entre los Activos Seleccionados"
    )
    st.plotly_chart(fig_corr, use_container_width=True)

# --- NUEVO: Gráfico de Riesgo vs. Retorno ---
st.markdown("---")
st.subheader("🎯 Gráfico de Riesgo vs. Retorno")
if lista_metricas:
    df_comparativa = pd.DataFrame(lista_metricas)
    if not df_comparativa.empty:
        fig_risk = px.scatter(
            df_comparativa.dropna(subset=['volatility_ann_%', 'annualized_return_%']),
            x="volatility_ann_%",
            y="annualized_return_%",
            hover_name="nombre",
            title=f"Eficiencia de los Activos Seleccionados ({horizonte})"
        )
        fig_risk.update_layout(xaxis_title="Volatilidad Anualizada (%)", yaxis_title="Rentabilidad Anualizada (%)")
        st.plotly_chart(fig_risk, use_container_width=True)
else:
    st.warning("No hay datos suficientes para generar el gráfico de riesgo vs. retorno.")