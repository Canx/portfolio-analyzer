# src/database.py

import streamlit as st
import json

# --- Funciones de Sanitización para Claves de Firebase ---

def sanitize_key(key):
    """Reemplaza caracteres no válidos en una clave de Firebase."""
    return key.replace('.', '_DOT_')

def unsanitize_key(key):
    """Restaura caracteres originales en una clave de Firebase."""
    return key.replace('_DOT_', '.')

def sanitize_data(data):
    """Recorre recursivamente un diccionario o lista para sanitizar todas las claves."""
    if isinstance(data, dict):
        return {sanitize_key(k): sanitize_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data

def unsanitize_data(data):
    """Recorre recursivamente un diccionario o lista para des-sanitizar todas las claves."""
    if isinstance(data, dict):
        return {unsanitize_key(k): unsanitize_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [unsanitize_data(item) for item in data]
    return data

# --- Funciones de Base de Datos ---

def load_user_data(db, user_info, data_key):
    """Carga y des-sanitiza los datos de un usuario."""
    if not db or not user_info:
        return {}
    try:
        user_id = user_info['uid']
        token = user_info['idToken']
        data = db.child("users").child(user_id).child(data_key).get(token)
        
        val = data.val()
        if val:
            # Des-sanitizar los datos leídos de Firebase
            return unsanitize_data(val)
        return {}
    except Exception as e:
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. Por favor, cierra sesión y vuelve a entrar.")
            st.session_state.logged_in = False
            st.stop()
        else:
            pass
        return {}

def save_user_data(db, auth, user_info, data_key, data):
    """Sanitiza y guarda los datos de un usuario."""
    if not db or not user_info:
        return
    try:
        refreshed_user = auth.refresh(user_info['refreshToken'])
        st.session_state.user_info['idToken'] = refreshed_user['idToken']
        
        user_id = user_info['uid']
        token = refreshed_user['idToken']
        
        # Sanitizar los datos antes de guardarlos
        sanitized_data_to_save = sanitize_data(data)
        
        db.child("users").child(user_id).child(data_key).set(sanitized_data_to_save, token)
        
    except Exception as e:
        if "Permission denied" in str(e) or "Auth token is expired" in str(e):
            st.warning("Tu sesión ha expirado. No se pudieron guardar los cambios.")
            st.session_state.logged_in = False
            st.stop()
        else:
            st.error(f"Error al guardar los datos de '{data_key}': {e}")

def update_user_profile(db, user_id, profile_data_to_update):
    """Actualiza campos específicos del perfil de un usuario."""
    if not db or not user_id:
        return False
    try:
        path = f"users/{user_id}/profile"
        # La data a actualizar también podría necesitar sanitización si las claves son dinámicas
        sanitized_update = sanitize_data(profile_data_to_update)
        db.child(path).update(sanitized_update)
        print(f"✅ Perfil actualizado para el usuario {user_id} con los datos: {sanitized_update}")
        return True
    except Exception as e:
        print(f"🔥 ERROR al actualizar el perfil para el usuario {user_id}: {e}")
        return False
