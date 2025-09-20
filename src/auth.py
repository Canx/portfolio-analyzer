# src/auth.py

import streamlit as st
import yaml
import pyrebase
from src.database import load_user_data # <-- IMPORTACIÓN MODIFICADA

def initialize_firebase():
    """Inicializa Firebase y devuelve los servicios de auth y db."""
    try:
        with open('config.yaml') as file:
            config = yaml.safe_load(file)
        
        firebase_config = config['firebase']
        firebase = pyrebase.initialize_app(firebase_config)
        return firebase.auth(), firebase.database()
    except FileNotFoundError:
        st.error("Error: Fichero 'config.yaml' no encontrado.")
        return None, None
    except Exception as e:
        st.error(f"Error al inicializar Firebase: {e}")
        return None, None

def login_user(auth, db, email, password):
    """Loguea a un usuario y carga sus carteras."""
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_info = {
            "email": user['email'],
            "uid": user['localId'],
            "idToken": user['idToken']
        }
        st.session_state.user_info = user_info
        st.session_state.logged_in = True
        
        # --- LÍNEA MODIFICADA ---
        # Pasamos el diccionario completo 'user_info'
        st.session_state.carteras = load_user_data(db, user_info, "carteras")
        
        if st.session_state.carteras:
            st.session_state.cartera_activa = list(st.session_state.carteras.keys())[0]
        else:
            st.session_state.cartera_activa = None

        st.toast("¡Inicio de sesión exitoso!", icon="✅")
        st.rerun()
    except Exception as e:
        st.error("Error al iniciar sesión: Email o contraseña incorrectos.")

def signup_user(auth, email, password, confirm_password):
    """Registra a un nuevo usuario."""
    if password != confirm_password:
        st.error("Las contraseñas no coinciden.")
        return
    try:
        auth.create_user_with_email_and_password(email, password)
        st.success("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
        st.balloons()
    except Exception:
        st.error("Error al crear la cuenta. Es posible que el email ya esté en uso.")

def logout_user():
    """Desloguea al usuario actual y limpia el estado."""
    st.session_state.logged_in = False
    st.session_state.user_info = {}
    st.session_state.carteras = {} 
    st.session_state.cartera_activa = None
    st.toast("Has cerrado sesión.", icon="👋")