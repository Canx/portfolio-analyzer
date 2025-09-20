# src/auth.py

import streamlit as st
import yaml
import pyrebase
from src.database import load_user_data
from src.state import initialize_session_state
from streamlit_local_storage import LocalStorage

# --- La función initialize_firebase no cambia ---
def initialize_firebase():
    # ... (código existente)
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

# --- La función signup_user no cambia ---
def signup_user(auth, email, password, confirm_password):
    # ... (código existente)
    if password != confirm_password:
        st.error("Las contraseñas no coinciden.")
        return
    try:
        auth.create_user_with_email_and_password(email, password)
        st.success("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
        st.balloons()
    except Exception:
        st.error("Error al crear la cuenta. Es posible que el email ya esté en uso.")


def page_init_and_auth():
    """
    Función única para ser llamada al principio de CADA página.
    Ahora gestiona su propia instancia de LocalStorage.
    """
    localS = LocalStorage() # <-- Se crea la instancia internamente
    
    # Lógica para forzar un re-run y evitar la 'race condition' al refrescar
    if 'local_storage_ready' not in st.session_state:
        st.session_state.local_storage_ready = False
        st.rerun()

    initialize_session_state()
    auth, db = initialize_firebase()

    if not st.session_state.get("logged_in", False):
        if auth and db:
            check_persistent_login(auth, db, localS)
    
    st.session_state.local_storage_ready = True
    return auth, db

def check_persistent_login(auth, db, localS):
    """Comprueba si hay un refreshToken en LocalStorage."""
    token = localS.getItem("firebase_refreshToken")
    
    if token:
        try:
            refreshed_user = auth.refresh(token)
            account_info = auth.get_account_info(refreshed_user['idToken'])
            user_email = account_info['users'][0]['email']
            
            user_info = { "email": user_email, "uid": refreshed_user['userId'], "idToken": refreshed_user['idToken'], "refreshToken": refreshed_user['refreshToken'] }
            st.session_state.user_info = user_info
            st.session_state.logged_in = True
            
            st.session_state.carteras = load_user_data(db, user_info, "carteras")
            if st.session_state.carteras:
                st.session_state.cartera_activa = list(st.session_state.carteras.keys())[0]
            else:
                st.session_state.cartera_activa = None
                
        except Exception as e:
            print(f"--- DEBUG: Fallo en la autenticación persistente: {e}")
            localS.setItem("firebase_refreshToken", None)

def login_user(auth, db, email, password):
    """Loguea a un usuario y guarda su refreshToken."""
    localS = LocalStorage() # <-- Instancia interna
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_info = { "email": user['email'], "uid": user['localId'], "idToken": user['idToken'], "refreshToken": user['refreshToken'] }
        st.session_state.user_info = user_info
        st.session_state.logged_in = True
        
        localS.setItem("firebase_refreshToken", user['refreshToken'])
        
        st.session_state.carteras = load_user_data(db, user_info, "carteras")
        if st.session_state.carteras:
            st.session_state.cartera_activa = list(st.session_state.carteras.keys())[0]
        else:
            st.session_state.cartera_activa = None

        st.toast("¡Inicio de sesión exitoso!", icon="✅")
        st.rerun()
    except Exception:
        st.error("Error al iniciar sesión: Email o contraseña incorrectos.")

def logout_user():
    """Desloguea al usuario y limpia el estado."""
    localS = LocalStorage() # <-- Instancia interna
    st.session_state.logged_in = False
    st.session_state.user_info = {}
    st.session_state.carteras = {} 
    st.session_state.cartera_activa = None
    localS.setItem("firebase_refreshToken", None)
    st.toast("Has cerrado sesión.", icon="👋")

# El resto de funciones (initialize_firebase, signup_user) no cambian.
# ...