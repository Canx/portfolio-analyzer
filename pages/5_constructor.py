# pages/5_constructor.py

import streamlit as st
import pandas as pd

from src.auth import page_init_and_auth
from src.utils import load_funds_from_db, load_all_navs
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import optimize_portfolio
from src.database import save_user_data
from src.portfolio import Portfolio

# --- INICIALIZACIÓN Y AUTENTICACIÓN ---
auth, db = page_init_and_auth()
if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

st.set_page_config(layout="wide")
st.title("🛠️ Constructor de Carteras Óptimas")
st.info(
    """Esta herramienta busca en todo el universo de fondos para construir la mejor cartera posible 
    basándose en tus objetivos y restricciones.
    """)

# --- CARGA DE DATOS INICIAL ---
df_catalogo = load_funds_from_db()
if df_catalogo.empty:
    st.error("No se pudo cargar el catálogo de fondos. El constructor no puede funcionar.")
    st.stop()

# --- CONTROLES EN LA SIDEBAR ---
with st.sidebar:
    st.header("1. Define tu Objetivo")
    optimization_goal = st.selectbox(
        "Objetivo Principal",
        options=["Maximizar Ratio de Sharpe", "Minimizar Volatilidad"],
        index=0,
        help="Define qué buscas en tu cartera ideal."
    )

    st.header("2. Define tus Reglas")
    horizonte = st.selectbox(
        "Horizonte de Análisis",
        options=["1y", "2y", "3y", "5y"],
        index=2, # Default a 3 años
        help="El rendimiento de los fondos se evaluará en este periodo para la preselección."
    )

    num_assets = st.number_input(
        "Número de fondos en la cartera final",
        min_value=3,
        max_value=25,
        value=10,
        step=1,
        help="¿Cuántos fondos quieres que tenga la cartera final?"
    )

    st.header("3. Define el Método de Búsqueda")
    preselection_method = st.radio(
        "Método de Preselección",
        options=["Global (Top 50)", "Por Categorías"],
        index=0,
        horizontal=True,
    )

    if preselection_method == "Global (Top 50)":
        with st.expander("Filtros Adicionales"):
            min_return = st.number_input(
                "Rentabilidad Anual Mínima (%)",
                min_value=-20.0,
                max_value=50.0,
                value=5.0,
                step=0.5,
                help=f"Solo se considerarán fondos con una rentabilidad anualizada (en el horizonte de {horizonte}) superior a este valor."
            )
            max_ter = st.slider(
                "TER Máximo (%)",
                min_value=0.0,
                max_value=5.0,
                value=1.5,
                step=0.1,
                help="Solo se considerarán fondos con un coste anual total (TER) inferior o igual a este valor."
            )
            
            available_currencies = sorted(df_catalogo['currency'].dropna().unique().tolist())
            selected_currencies = st.multiselect(
                "Moneda del fondo",
                options=available_currencies,
                default=['EUR'] if 'EUR' in available_currencies else [],
                help="Selecciona las monedas de los fondos a considerar."
            )
    else: # Por Categorías
        available_categories = sorted(df_catalogo['morningstar_category'].dropna().unique().tolist())
        selected_categories = st.multiselect(
            "Seleccionar Categorías",
            options=available_categories,
            help="La búsqueda se hará solo dentro de las categorías que elijas."
        )
        n_per_category = st.number_input(
            "Mejores fondos a coger por categoría",
            min_value=1,
            max_value=10,
            value=3,
            step=1
        )
        # Dejamos estas variables con valores por defecto para no romper la lógica existente
        min_return = -100
        max_ter = 100
        selected_currencies = []


    st.markdown("---")
    run_build = st.button("🏗️ Construir Cartera", use_container_width=True, type="primary")

# --- LÓGICA DE CONSTRUCCIÓN ---
if run_build:
    if 'constructor_results' in st.session_state:
        del st.session_state.constructor_results

    with st.spinner(f"Fase 1: Analizando y filtrando el universo de fondos..."):
        data_manager = DataManager()
        
        df_filtered_catalog = df_catalogo.copy()
        if preselection_method == "Global (Top 50)":
            df_filtered_catalog['ter'] = pd.to_numeric(df_filtered_catalog['ter'], errors='coerce')
            df_filtered_catalog.dropna(subset=['ter'], inplace=True)
            df_filtered_catalog = df_filtered_catalog[df_filtered_catalog['ter'] <= max_ter]

            if selected_currencies:
                df_filtered_catalog = df_filtered_catalog[df_filtered_catalog['currency'].isin(selected_currencies)]

        if df_filtered_catalog.empty:
            st.error("Ningún fondo cumple los criterios de filtro iniciales.")
            st.stop()

        all_isins = tuple(df_filtered_catalog['isin'].unique())
        all_navs_df = load_all_navs(data_manager, all_isins)
        
        if all_navs_df.empty:
            st.error("No se encontraron datos de precios para los fondos filtrados.")
            st.stop()

        navs_filtered = filtrar_por_horizonte(all_navs_df, horizonte)
        all_metrics = []
        for isin in navs_filtered.columns:
            returns = navs_filtered[isin].pct_change().dropna()
            if len(returns) > 252: 
                metrics = calcular_metricas_desde_rentabilidades(returns)
                metrics['isin'] = isin
                all_metrics.append(metrics)
        
        if not all_metrics:
            st.error(f"No hay suficientes fondos con datos históricos en el horizonte de {horizonte}.")
            st.stop()

        df_all_metrics = pd.DataFrame(all_metrics)

        if preselection_method == "Global (Top 50)":
            df_filtered_metrics = df_all_metrics[df_all_metrics['annualized_return_%'] >= min_return]
            if df_filtered_metrics.empty:
                st.warning(f"Ningún fondo cumple el criterio de rentabilidad mínima del {min_return}%. Se continúa sin este filtro.")
                df_to_sort = df_all_metrics
            else:
                df_to_sort = df_filtered_metrics
            top_candidates = df_to_sort.sort_values(by="sharpe_ann", ascending=False).head(50)
        else: # Por Categorías
            if not selected_categories:
                st.error("Por favor, selecciona al menos una categoría para el método de búsqueda 'Por Categorías'.")
                st.stop()
            
            df_all_metrics = df_all_metrics.merge(df_filtered_catalog[['isin', 'morningstar_category']], on='isin')
            diversified_candidates = []
            for category in selected_categories:
                df_category = df_all_metrics[df_all_metrics['morningstar_category'] == category]
                top_funds_in_category = df_category.sort_values(by="sharpe_ann", ascending=False).head(n_per_category)
                diversified_candidates.append(top_funds_in_category)
            
            if not diversified_candidates:
                st.error("No se encontraron fondos para las categorías seleccionadas.")
                st.stop()
                
            top_candidates = pd.concat(diversified_candidates)

    if top_candidates.empty:
        st.error("No se pudieron preseleccionar fondos con los criterios definidos.")
    else:
        mapa_isin_nombre = pd.Series(df_catalogo['name'].values, index=df_catalogo['isin']).to_dict()
        top_candidates['nombre'] = top_candidates['isin'].map(mapa_isin_nombre)

        with st.spinner("Fase 2: Realizando optimización profunda..."):
            top_isins = top_candidates['isin'].tolist()
            navs_top_candidates = navs_filtered[top_isins]
            returns_top_candidates = navs_top_candidates.pct_change().fillna(0)
            model_map = {"Maximizar Ratio de Sharpe": "MSR", "Minimizar Volatilidad": "MV"}
            optimization_model = model_map.get(optimization_goal, "MSR")
            optimal_weights_series = optimize_portfolio(returns_top_candidates, model=optimization_model)

        if optimal_weights_series is not None and not optimal_weights_series.empty:
            final_weights = optimal_weights_series[optimal_weights_series > 0].sort_values(ascending=False)
            df_final_weights = pd.DataFrame(final_weights).reset_index()
            df_final_weights.columns = ['isin', 'weight']
            df_final_weights['nombre'] = df_final_weights['isin'].map(mapa_isin_nombre)
            df_final_weights['weight'] = df_final_weights['weight'] * 100

            with st.spinner("Fase 3: Ajustando la cartera al número de fondos deseado..."):
                df_adjusted = df_final_weights.head(num_assets)
                total_weight_adjusted = df_adjusted['weight'].sum()
                df_adjusted['final_weight'] = (df_adjusted['weight'] / total_weight_adjusted) * 100
                final_pesos_dict = pd.Series(df_adjusted['final_weight'].values, index=df_adjusted['isin']).to_dict()
                final_isins = list(final_pesos_dict.keys())
                final_portfolio = Portfolio(navs_top_candidates[final_isins], final_pesos_dict)
                final_metrics = final_portfolio.calculate_metrics()

            st.session_state.constructor_results = {
                'df_adjusted': df_adjusted,
                'final_metrics': final_metrics,
                'final_pesos_dict': final_pesos_dict,
                'optimization_goal': optimization_goal,
                'num_assets': num_assets
            }

# --- BLOQUE DE DISPLAY Y GUARDADO ---
if 'constructor_results' in st.session_state:
    results = st.session_state.constructor_results
    df_adjusted = results['df_adjusted']
    final_metrics = results['final_metrics']
    final_pesos_dict = results['final_pesos_dict']
    optimization_goal = results['optimization_goal']
    num_assets = results['num_assets']
    
    df_catalogo_reloaded = load_funds_from_db()
    mapa_isin_nombre_reloaded = pd.Series(df_catalogo_reloaded['name'].values, index=df_catalogo_reloaded['isin']).to_dict()
    df_adjusted['nombre'] = df_adjusted['isin'].map(mapa_isin_nombre_reloaded)

    st.header("Tu Cartera Óptima Personalizada", divider='rainbow')
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Rentabilidad Anual Estimada", f"{final_metrics.get('annualized_return_%', 0):.2f}%")
    col2.metric("Volatilidad Estimada", f"{final_metrics.get('volatility_ann_%', 0):.2f}%")
    col3.metric("Ratio de Sharpe Estimado", f"{final_metrics.get('sharpe_ann', 0):.2f}")

    st.write(f"Esta es la composición de tu cartera con **{len(df_adjusted)} fondos**:")
    st.dataframe(df_adjusted[['nombre', 'isin', 'final_weight']].rename(columns={'final_weight': 'Peso Final'}).style.format({'Peso Final': '{:.2f}%'}), use_container_width=True)

    st.markdown("---")
    new_portfolio_name = st.text_input("Nombre para la nueva cartera", f"Cartera Optima {optimization_goal} ({num_assets} fondos)", key="new_portfolio_name_input")
    if st.button("💾 Guardar Cartera en \"Mis Carteras\"", use_container_width=True):
        if not new_portfolio_name:
            st.error("Por favor, introduce un nombre para la cartera.")
        elif new_portfolio_name in st.session_state.carteras:
            st.error("Ya existe una cartera con este nombre. Por favor, elige otro.")
        else:
            final_pesos_int = {isin: round(weight) for isin, weight in final_pesos_dict.items()}
            resto = 100 - sum(final_pesos_int.values())
            if resto != 0 and final_pesos_int:
                max_weight_isin = max(final_pesos_int, key=final_pesos_int.get)
                final_pesos_int[max_weight_isin] += resto

            st.session_state.carteras[new_portfolio_name] = {"pesos": final_pesos_int}
            st.success(f"¡Cartera '{new_portfolio_name}' guardada! Puedes verla en la sección 'Mis Carteras'.")
            if 'user_info' in st.session_state:
                profile_data_to_save = {
                    "subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
                    "carteras": st.session_state.get("carteras", {})
                }
                save_user_data(db, auth, st.session_state.user_info, "profile", profile_data_to_save)
            st.page_link("pages/2_carteras.py", label="Ir a Mis Carteras", icon="🗂️")

if not run_build and 'constructor_results' not in st.session_state:
    st.write("Define tus objetivos en la barra lateral y pulsa \"Construir Cartera\".")