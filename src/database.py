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
        user_id = user_info['uid']
        token = user_info['idToken']
        data = db.child("users").child(user_id).child(data_key).get(token)
        
        if data.val():
            if isinstance(data.val(), str):
                return json.loads(data.val())
            return data.val()
        return {}
    except Exception as e:
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. Por favor, cierra sesión y vuelve a entrar.")
            st.session_state.logged_in = False
            st.stop()
        else:
            # No mostramos error de carga aquí para no ser intrusivos
            pass
        return {}

def save_user_data(db, auth, user_info, data_key, data):
    """
    Refresca el token del usuario y luego guarda sus datos.
    Esta es la versión que acepta 5 argumentos.
    """
    if not db or not user_info:
        return
    try:
        # Refrescamos la sesión para obtener un nuevo idToken
        refreshed_user = auth.refresh(user_info['refreshToken'])
        st.session_state.user_info['idToken'] = refreshed_user['idToken']
        
        # Usamos el token recién refrescado para guardar los datos
        user_id = user_info['uid']
        token = refreshed_user['idToken']
        
        # La ruta ahora apunta a users/{user_id}/{data_key}
        # Ejemplo: users/USER123/profile o users/USER123/carteras
        db.child("users").child(user_id).child(data_key).set(data, token)
        
    except Exception as e:
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. No se pudieron guardar los cambios.")
            st.session_state.logged_in = False
            st.stop()
        else:
            st.error(f"Error al guardar los datos de '{data_key}': {e}")