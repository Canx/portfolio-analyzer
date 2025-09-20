# src/auth.py

import streamlit as st
import yaml
import pyrebase
from src.database import load_user_data
from src.state import initialize_session_state
from streamlit_local_storage import LocalStorage
from src.database import save_user_data


def page_init_and_auth():
    """
    Función única para ser llamada al principio de CADA página.
    """
    localS = LocalStorage()
    
    # --- LÓGICA DE LOGOUT (NUEVA) ---
    # Si estamos en proceso de logout, limpiamos todo y paramos.
    if st.session_state.get("logout_in_progress"):
        st.session_state.clear() # Limpia TODA la memoria de la sesión
        localS.setItem("firebase_refreshToken", None)
        st.session_state.logout_complete = True # Marcamos que hemos terminado
        
    # Si acabamos de terminar el logout, hacemos un último rerun para refrescar
    if st.session_state.get("logout_complete"):
        del st.session_state.logout_complete
        st.rerun()

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
    token = localS.getItem("firebase_refreshToken")
    if token:
        try:
            refreshed_user = auth.refresh(token)
            account_info = auth.get_account_info(refreshed_user['idToken'])
            user_email = account_info['users'][0]['email']
            
            user_info = { "email": user_email, "uid": refreshed_user['userId'], "idToken": refreshed_user['idToken'], "refreshToken": refreshed_user['refreshToken'] }
            st.session_state.user_info = user_info
            st.session_state.logged_in = True

            # Cargamos el perfil completo
            profile_data = load_user_data(db, user_info, "profile")
            st.session_state.user_info["subscription_plan"] = profile_data.get("subscription_plan", "free")
            st.session_state.carteras = profile_data.get("carteras", {})
            
            if st.session_state.carteras:
                st.session_state.cartera_activa = list(st.session_state.carteras.keys())[0]
            else:
                st.session_state.cartera_activa = None
                
        except Exception as e:
            print(f"--- DEBUG: Fallo en la autenticación persistente: {e}")
            localS.setItem("firebase_refreshToken", None)

def login_user(auth, db, email, password):
    localS = LocalStorage()
    try:
        user = auth.sign_in_with_email_and_password(email, password)
        user_info = { "email": user['email'], "uid": user['localId'], "idToken": user['idToken'], "refreshToken": user['refreshToken'] }
        
        localS.setItem("firebase_refreshToken", user['refreshToken'])
        
        # Cargamos el perfil completo
        profile_data = load_user_data(db, user_info, "profile")
        user_info["subscription_plan"] = profile_data.get("subscription_plan", "free")
        st.session_state.carteras = profile_data.get("carteras", {})

        st.session_state.user_info = user_info
        st.session_state.logged_in = True
        
        if st.session_state.carteras:
            st.session_state.cartera_activa = list(st.session_state.carteras.keys())[0]
        else:
            st.session_state.cartera_activa = None

        st.toast("¡Inicio de sesión exitoso!", icon="✅")
        st.rerun()
    except Exception:
        st.error("Error al iniciar sesión: Email o contraseña incorrectos.")

def signup_user(auth, db, email, password, confirm_password):
    if password != confirm_password:
        st.error("Las contraseñas no coinciden.")
        return
    try:
        user = auth.create_user_with_email_and_password(email, password)
        
        # Preparamos los datos del perfil y las carteras para el nuevo usuario
        user_info_for_save = {"uid": user['localId'], "refreshToken": user['refreshToken']}
        profile_data = {
            "subscription_plan": "free",
            "carteras": {}
        }
        
        # Llamamos a la función de guardado con 5 argumentos
        save_user_data(db, auth, user_info_for_save, "profile", profile_data)

        st.success("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
        st.balloons()
    except Exception as e:
        st.error(f"Error al crear la cuenta: {e}")

def logout_user():
    """
    Inicia el proceso de logout. Solo pone una bandera.
    """
    st.session_state.logout_in_progress = True

def initialize_firebase():
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