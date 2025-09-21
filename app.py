# app.py (fichero raíz)

import streamlit as st
from src.state import initialize_session_state
from src.auth import login_user, signup_user, logout_user, page_init_and_auth


st.set_page_config(page_title="Analizador de Carteras", page_icon="📊", layout="wide")

auth, db = page_init_and_auth()

# --- LÓGICA DE LA PÁGINA ---

if not st.session_state.get("logged_in", False):
    # --- FORMULARIO DE LOGIN Y REGISTRO ---
    st.title("📊 Bienvenido al Analizador de Carteras")
    st.write("Por favor, inicia sesión o crea una cuenta para continuar.")

    choice = st.selectbox("Login / Signup", ["Login", "Signup"])

    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if choice == "Signup":
        confirm_password = st.text_input("Confirm Password", type="password")
        if st.button("Crear Cuenta"):
            if auth:
                signup_user(auth, email, password, confirm_password)
    else:
        if st.button("Login"):
            if auth:
                 login_user(auth, db, email, password)
else:
    # --- PÁGINA DE BIENVENIDA UNA VEZ LOGUEADO ---
    st.title(f"📊 Bienvenido, {st.session_state.user_info.get('email', '')}!")
    st.markdown(
        """
        Esta aplicación te permite crear, analizar, comparar y optimizar múltiples carteras de fondos de inversión.

        **Usa el menú de la izquierda para navegar por las diferentes secciones:**
        - **Explorador de Fondos:** Descubre y gestiona tu catálogo de fondos.
        - **Análisis de Cartera:** Crea y optimiza tus carteras.
        - **Comparador:** Compara el rendimiento entre diferentes carteras y fondos.
        """
    )
    if st.button("Cerrar Sesión"):
        logout_user()
        st.rerun()