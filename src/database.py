# src/database.py

import streamlit as st
import json

def load_user_data(db, user_info, data_key):
    """
    Carga un conjunto de datos específico para un usuario, usando su token de autenticación.
    """
    if not db or not user_info:
        return {}
    try:
        # Extraemos el id del usuario y el token de sesión
        user_id = user_info['uid']
        token = user_info['idToken']
        
        # Hacemos la llamada a la base de datos pasando el token
        data = db.child("users").child(user_id).child(data_key).get(token)
        
        if data.val():
            if isinstance(data.val(), str):
                return json.loads(data.val())
            return data.val()
        return {}
    except Exception as e:
        # Si el token ha expirado, Pyrebase puede lanzar un error específico.
        # Lo capturamos para dar un mensaje más claro al usuario.
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. Por favor, cierra sesión y vuelve a entrar.")
            st.session_state.logged_in = False # Forzamos el logout
        else:
            st.error(f"No se pudieron cargar los datos de '{data_key}': {e}")
        return {}

def save_user_data(db, user_info, data_key, data):
    """
    Guarda un conjunto de datos de un usuario, usando su token de autenticación.
    """
    if not db or not user_info:
        return
    try:
        # Extraemos el id del usuario y el token de sesión
        user_id = user_info['uid']
        token = user_info['idToken']
        
        # Guardamos los datos pasando el token
        db.child("users").child(user_id).child(data_key).set(data, token)
    except Exception as e:
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. No se pudieron guardar los cambios. Por favor, cierra sesión y vuelve a entrar.")
            st.session_state.logged_in = False # Forzamos el logout
            st.stop()
        else:
            st.error(f"Error al guardar los datos de '{data_key}': {e}")