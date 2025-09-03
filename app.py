# app.py (fichero raíz)

import streamlit as st
from src.state import initialize_session_state # <-- Importamos la nueva función

st.set_page_config(
    page_title="Analizador de Carteras",
    page_icon="📊",
    layout="wide"
)

# --- LLAMAMOS A LA INICIALIZACIÓN GLOBAL ---
initialize_session_state()

# --- Página de Bienvenida ---
st.title("📊 Bienvenido al Analizador de Carteras")

st.markdown("""
Esta aplicación te permite crear, analizar, comparar y optimizar múltiples carteras de fondos de inversión.
...
""")