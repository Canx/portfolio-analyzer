import streamlit as st
import pandas as pd
import plotly.express as px

# Importamos las funciones y clases compartidas que hemos creado
from src.state import initialize_session_state
from src.utils import load_config, load_all_navs
from src.data_manager import DataManager, filtrar_por_horizonte
from src.portfolio import Portfolio

# --- Configuración e inicialización de la página ---
st.set_page_config(
    page_title="Comparador de Carteras",
    page_icon="📊",
    layout="wide"
)
initialize_session_state()

st.title("📊 Comparador de Carteras")
st.write("Selecciona dos o más de tus carteras para comparar su rendimiento y métricas en un horizonte temporal específico.")

# --- Selección de Carteras ---
lista_carteras = list(st.session_state.carteras.keys())

# Comprobamos si hay suficientes carteras para comparar
if len(lista_carteras) < 2:
    st.warning("Necesitas tener al menos dos carteras guardadas para poder comparar.")
    st.info("Ve a la página de 'Análisis de Cartera' para crear más carteras.")
    st.stop()

# Selector múltiple para que el usuario elija qué carteras comparar
carteras_seleccionadas = st.multiselect(
    "Selecciona las carteras que quieres comparar",
    options=lista_carteras,
    default=lista_carteras[:2] # Por defecto, seleccionamos las dos primeras
)

if len(carteras_seleccionadas) < 2:
    st.info("Por favor, selecciona al menos dos carteras para iniciar la comparación.")
    st.stop()

# --- Selector de Horizonte en la Sidebar ---
horizonte = st.sidebar.selectbox(
    "Horizonte temporal para la comparación",
    ["3m", "6m", "YTD", "1y", "3y", "5y", "max"],
    key="comp_horizonte"
)
st.markdown("---")

# --- Carga y Procesamiento de Datos ---
# 1. Recopilar todos los ISINs únicos de las carteras seleccionadas
todos_los_isines = set()
for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras.get(nombre_cartera, {}).get("pesos", {})
    todos_los_isines.update(pesos.keys())

# 2. Cargar el NAV de todos los fondos necesarios
data_manager = DataManager()
all_navs_df = load_all_navs(data_manager, tuple(sorted(todos_los_isines)))

if all_navs_df.empty:
    st.error("No se pudieron cargar los datos de los fondos para la comparación.")
    st.stop()

# 3. Filtrar todos los NAVs por el horizonte seleccionado
filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)

# --- Bucle de Cálculo para Cada Cartera ---
lista_metricas = []
navs_a_graficar = {}

for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras[nombre_cartera].get("pesos", {})
    
    # Creamos un objeto Portfolio para cada una
    portfolio_obj = Portfolio(nav_data=filtered_navs, weights=pesos)
    
    # Calculamos sus métricas si hay datos suficientes
    if portfolio_obj.daily_returns is not None and len(portfolio_obj.daily_returns.dropna()) > 1:
        metricas = portfolio_obj.calculate_metrics()
        metricas["nombre"] = nombre_cartera # Usamos el nombre de la cartera como identificador
        lista_metricas.append(metricas)
    
    # Guardamos su NAV para el gráfico
    if portfolio_obj.nav is not None:
        navs_a_graficar[nombre_cartera] = portfolio_obj.nav

# --- Visualización de Resultados ---

# 1. Tabla Comparativa de Métricas
if lista_metricas:
    st.subheader("📈 Tabla Comparativa de Métricas")
    df_comparativa = pd.DataFrame(lista_metricas)
    df_display = df_comparativa.rename(columns={
        "nombre": "Cartera", "annualized_return_%": "Rent. Anual (%)",
        "volatility_ann_%": "Volatilidad (%)", "sharpe_ann": "Ratio Sharpe",
        "max_drawdown_%": "Caída Máxima (%)"
    }).set_index("Cartera")[["Rent. Anual (%)", "Volatilidad (%)", "Ratio Sharpe", "Caída Máxima (%)"]]
    st.dataframe(df_display.style.format("{:.2f}"))

st.markdown("---")

# 2. Gráfico de Rendimiento Comparado
if navs_a_graficar:
    st.subheader("🚀 Gráfico Comparativo de Rendimiento")
    # Combinamos los NAVs de todas las carteras en un solo DataFrame
    df_grafico = pd.DataFrame(navs_a_graficar)
    
    st.line_chart(df_grafico)