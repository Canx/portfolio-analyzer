# pages/2_carteras.py

import streamlit as st
import pandas as pd
from src.auth import page_init_and_auth, logout_user
from src.database import save_user_data
from src.portfolio import Portfolio
from src.utils import load_all_navs, load_config
from src.data_manager import DataManager, filtrar_por_horizonte # <-- Importamos filtrar_por_horizonte
from src.config import HORIZONTE_OPCIONES, HORIZONTE_DEFAULT_INDEX # <-- Importamos las opciones de horizonte

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.write(f"Usuario: {st.session_state.user_info.get('email')}")
    if st.button("Cerrar Sesión"):
        logout_user()
        st.rerun()
    
    st.markdown("---")
    st.header("Filtros de Visualización")
    # Añadimos el selector de horizonte a la barra lateral
    horizonte = st.selectbox(
        "Horizonte temporal para métricas",
        HORIZONTE_OPCIONES,
        index=HORIZONTE_DEFAULT_INDEX,
        key="horizonte_carteras"
    )

# --- LÓGICA DE LA PÁGINA ---
st.title("🗂️ Mis Carteras")
# ... (código de crear cartera no cambia) ...

# --- LISTADO Y MÉTRICAS DE CARTERAS EXISTENTES ---
data_manager = DataManager()
fondos_config = load_config()
mapa_isin_nombre = {f["isin"]: f["nombre"] for f in fondos_config}
lista_carteras = st.session_state.get("carteras", {})

if not lista_carteras:
    st.info("Aún no tienes ninguna cartera. ¡Crea una para empezar!")
    st.stop()

@st.cache_data
def calculate_portfolio_metrics(cartera_tuple, horizonte_seleccionado):
    nombre_cartera, cartera_data = cartera_tuple
    pesos = cartera_data.get("pesos", {})
    if not pesos:
        return {"nombre": nombre_cartera}

    isines = tuple(pesos.keys())
    all_navs = load_all_navs(data_manager, isines)
    if all_navs.empty:
        return {"nombre": nombre_cartera}
    
    # --- LÓGICA CORREGIDA ---
    # Filtramos los datos según el horizonte seleccionado ANTES de calcular las métricas
    filtered_navs = filtrar_por_horizonte(all_navs, horizonte_seleccionado)
    
    portfolio = Portfolio(filtered_navs, pesos)
    metrics = portfolio.calculate_metrics()
    metrics["nombre"] = nombre_cartera
    return metrics

# Mostramos cada cartera
for nombre_cartera, cartera_data in lista_carteras.items():
    
    # Creamos un expansor para cada cartera
    with st.expander(f"**{nombre_cartera}**"):
        
        # Calculamos las métricas
        metrics = calculate_portfolio_metrics((nombre_cartera, cartera_data), horizonte)
        
        # Decidimos qué métrica de rentabilidad mostrar
        label_rentabilidad = "Rent. Anual"
        valor_rentabilidad = metrics.get('annualized_return_%', 0)
        
        if horizonte in ["1m", "3m", "6m", "YTD"]:
            label_rentabilidad = f"Rent. ({horizonte})"
            valor_rentabilidad = metrics.get('cumulative_return_%', 0)

        # Fila 1: Las métricas clave
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label_rentabilidad, f"{valor_rentabilidad:.2f}%")
        with col2:
            st.metric("Volatilidad", f"{metrics.get('volatility_ann_%', 0):.2f}%")
        with col3:
            st.metric("R. Sharpe", f"{metrics.get('sharpe_ann', 0):.2f}")

        st.markdown("---") # Separador visual

        # Fila 2: Los botones de acción
        col_btn1, col_btn2, _ = st.columns([1, 1, 4]) # Usamos una columna vacía para alinear
        with col_btn1:
            if st.button("Ver Detalle", key=f"detail_{nombre_cartera}", type="primary"):
                st.session_state.cartera_activa = nombre_cartera
                st.switch_page("pages/2_detalle_cartera.py")
        
        with col_btn2:
            if st.button("Borrar", key=f"delete_{nombre_cartera}"):
                del st.session_state.carteras[nombre_cartera]
                if st.session_state.cartera_activa == nombre_cartera:
                    st.session_state.cartera_activa = None
                st.rerun()

# Guardamos los cambios (si se ha borrado o creado alguna cartera)
if 'carteras' in st.session_state and 'user_info' in st.session_state:
    save_user_data(db, auth, st.session_state.user_info, "profile", 
                   {"subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
                    "carteras": st.session_state.get("carteras", {})})