# pages/2_carteras.py

import streamlit as st
import pandas as pd
from src.auth import page_init_and_auth, logout_user
from src.database import save_user_data
from src.portfolio import Portfolio
from src.utils import load_all_navs, load_config
from src.data_manager import DataManager

# --- INICIALIZACIÓN Y PROTECCIÓN ---
auth, db = page_init_and_auth()

if not st.session_state.get("logged_in", False):
    st.warning("🔒 Debes iniciar sesión para acceder a esta página.")
    st.page_link("app.py", label="Ir a la página de Login", icon="🏠")
    st.stop()

with st.sidebar:
    st.write(f"Usuario: {st.session_state.user_info.get('email')}")
    if st.button("Cerrar Sesión"):
        logout_user()
        st.rerun()

# --- LÓGICA DE LA PÁGINA ---
st.title("🗂️ Mis Carteras")
st.write("Aquí puedes ver un resumen de todas tus carteras, crear nuevas o eliminar las existentes.")

# --- 1. SECCIÓN PARA CREAR NUEVAS CARTERAS ---
with st.expander("➕ Crear una nueva cartera"):
    with st.form("form_create_portfolio"):
        new_portfolio_name = st.text_input("Nombre de la nueva cartera")
        submitted_create = st.form_submit_button("Crear Cartera")
        if submitted_create and new_portfolio_name:
            if new_portfolio_name in st.session_state.carteras:
                st.warning("Ya existe una cartera con ese nombre.")
            else:
                st.session_state.carteras[new_portfolio_name] = {"pesos": {}}
                st.toast(f"¡Cartera '{new_portfolio_name}' creada!")
                st.rerun()

st.markdown("---")

# --- 2. LISTADO Y MÉTRICAS DE CARTERAS EXISTENTES ---
data_manager = DataManager()
fondos_config = load_config()
mapa_isin_nombre = {f["isin"]: f["nombre"] for f in fondos_config}

lista_carteras = st.session_state.get("carteras", {})

if not lista_carteras:
    st.info("Aún no tienes ninguna cartera. ¡Crea una para empezar!")
    st.stop()

# Cache para evitar recalcular las métricas en cada rerun
@st.cache_data
def calculate_portfolio_metrics(cartera_tuple):
    # Streamlit necesita que los argumentos de funciones cacheadas sean "hashables"
    # Por eso convertimos el diccionario de la cartera a una tupla de items
    nombre_cartera, cartera_data = cartera_tuple
    pesos = cartera_data.get("pesos", {})
    if not pesos:
        return {"nombre": nombre_cartera}

    isines = tuple(pesos.keys())
    all_navs = load_all_navs(data_manager, isines)
    if all_navs.empty:
        return {"nombre": nombre_cartera}
    
    portfolio = Portfolio(all_navs, pesos)
    metrics = portfolio.calculate_metrics()
    metrics["nombre"] = nombre_cartera
    return metrics

# Mostramos cada cartera como una "tarjeta"
for nombre_cartera, cartera_data in lista_carteras.items():
    
    # Calculamos las métricas usando la función cacheada
    metrics = calculate_portfolio_metrics((nombre_cartera, cartera_data))
    
    col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 1, 1])
    
    with col1:
        st.subheader(nombre_cartera)
    
    with col2:
        st.metric("Rent. Anual", f"{metrics.get('annualized_return_%', 0):.2f}%")
        
    with col3:
        st.metric("Volatilidad", f"{metrics.get('volatility_ann_%', 0):.2f}%")
        
    with col4:
        st.metric("R. Sharpe", f"{metrics.get('sharpe_ann', 0):.2f}")

    with col5:
        if st.button("Ver Detalle", key=f"detail_{nombre_cartera}"):
            st.session_state.cartera_activa = nombre_cartera
            st.switch_page("pages/2_detalle_cartera.py")
    
    with col6:
        if st.button("🗑️", key=f"delete_{nombre_cartera}", help="Borrar cartera"):
            del st.session_state.carteras[nombre_cartera]
            if st.session_state.cartera_activa == nombre_cartera:
                st.session_state.cartera_activa = None
            st.rerun()
            
    st.markdown("---")

# Guardamos los cambios (si se ha borrado o creado alguna cartera)
if 'carteras' in st.session_state and 'user_info' in st.session_state:
    save_user_data(db, auth, st.session_state.user_info, "profile", 
                   {"subscription_plan": st.session_state.user_info.get("subscription_plan", "free"),
                    "carteras": st.session_state.get("carteras", {})})