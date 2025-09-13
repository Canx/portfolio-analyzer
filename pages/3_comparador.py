import streamlit as st
import pandas as pd
import plotly.express as px

# Importaciones de funciones compartidas
from src.state import initialize_session_state
from src.utils import load_config, load_all_navs
from src.data_manager import DataManager, filtrar_por_horizonte
from src.portfolio import Portfolio

st.set_page_config(
    page_title="Comparador",
    page_icon="📊",
    layout="wide"
)
initialize_session_state()

st.title("📊 Comparador de Carteras y Fondos")
st.write("Selecciona carteras y/o fondos individuales para comparar su rendimiento y métricas.")

# --- Carga de datos de configuración ---
fondos_config = load_config()
if not fondos_config:
    st.warning("No hay fondos en el catálogo. Por favor, añádelos en el Explorador de Fondos.")
    st.stop()

mapa_isin_nombre = {f['isin']: f['nombre'] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f['isin'] for f in fondos_config}
nombres_fondos_catalogo = list(mapa_nombre_isin.keys())

# --- Selectores de Carteras y Fondos ---
lista_carteras = list(st.session_state.carteras.keys())

col1, col2 = st.columns(2)
with col1:
    carteras_seleccionadas = st.multiselect(
        "Selecciona Carteras",
        options=lista_carteras,
        default=lista_carteras[:2] if len(lista_carteras) >= 2 else []
    )
with col2:
    fondos_seleccionados_nombres = st.multiselect(
        "Añadir Fondos Individuales a la Comparación",
        options=nombres_fondos_catalogo
    )
    fondos_seleccionados_isines = [mapa_nombre_isin[n] for n in fondos_seleccionados_nombres]

if not carteras_seleccionadas and not fondos_seleccionados_isines:
    st.info("Por favor, selecciona al menos una cartera o un fondo para iniciar la comparación.")
    st.stop()

# --- Selector de Horizonte en la Sidebar ---
horizonte = st.sidebar.selectbox("Horizonte temporal para la comparación", ["3m", "6m", "YTD", "1y", "3y", "5y", "max"], key="comp_horizonte")
st.markdown("---")

# --- Lógica de Carga Adaptada ---
todos_los_isines = set(fondos_seleccionados_isines)
for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras.get(nombre_cartera, {}).get("pesos", {})
    todos_los_isines.update(pesos.keys())

data_manager = DataManager()
all_navs_df = load_all_navs(data_manager, tuple(sorted(todos_los_isines)))

if all_navs_df.empty:
    st.error("No se pudieron cargar los datos de los fondos para la comparación."); st.stop()

filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)

# --- Bucle de Cálculo Modificado ---
lista_metricas = []
navs_a_graficar = {}

# 1. Procesar las carteras compuestas
for nombre_cartera in carteras_seleccionadas:
    pesos = st.session_state.carteras[nombre_cartera].get("pesos", {})
    portfolio_obj = Portfolio(nav_data=filtered_navs, weights=pesos)
    if portfolio_obj.daily_returns is not None and len(portfolio_obj.daily_returns.dropna()) > 1:
        metricas = portfolio_obj.calculate_metrics(); metricas["nombre"] = f"💼 {nombre_cartera}"
        lista_metricas.append(metricas)
    if portfolio_obj.nav is not None:
        navs_a_graficar[f"💼 {nombre_cartera}"] = portfolio_obj.nav

# 2. Procesar los fondos individuales (tratándolos como carteras de un solo activo)
for isin in fondos_seleccionados_isines:
    pesos = {isin: 100} # Cartera con 100% de peso en este único fondo
    portfolio_obj = Portfolio(nav_data=filtered_navs, weights=pesos)
    nombre_fondo = mapa_isin_nombre.get(isin, isin)
    if portfolio_obj.daily_returns is not None and len(portfolio_obj.daily_returns.dropna()) > 1:
        metricas = portfolio_obj.calculate_metrics(); metricas["nombre"] = nombre_fondo
        lista_metricas.append(metricas)
    if portfolio_obj.nav is not None:
        navs_a_graficar[nombre_fondo] = portfolio_obj.nav

# --- Visualización de Resultados ---
if lista_metricas:
    st.subheader("📈 Tabla Comparativa de Métricas")
    df_comparativa = pd.DataFrame(lista_metricas)
    df_display = df_comparativa.rename(columns={
        "nombre": "Activo", "annualized_return_%": "Rent. Anual (%)",
        "volatility_ann_%": "Volatilidad (%)", "sharpe_ann": "Ratio Sharpe",
        "max_drawdown_%": "Caída Máxima (%)"
    }).set_index("Activo")[["Rent. Anual (%)", "Volatilidad (%)", "Ratio Sharpe", "Caída Máxima (%)"]]
    st.dataframe(df_display.style.format("{:.2f}"))

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