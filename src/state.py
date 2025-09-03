# src/state.py

import streamlit as st
import json
from streamlit_local_storage import LocalStorage

def initialize_session_state():
    """
    Inicializa el estado de la sesión para toda la app si no existe.
    Esta función debe ser llamada al principio de cada página.
    """
    if 'initialized' not in st.session_state:
        localS = LocalStorage()
        json_carteras = localS.getItem('mis_carteras')
        carteras_guardadas = {}
        if json_carteras:
            try:
                carteras_guardadas = json.loads(json_carteras)
            except json.JSONDecodeError:
                st.warning("Formato de carteras guardadas incorrecto.")
        
        st.session_state.carteras = carteras_guardadas
        
        if carteras_guardadas:
            st.session_state.cartera_activa = list(carteras_guardadas.keys())[0]
        else:
            st.session_state.cartera_activa = None
        
        st.session_state.initialized = True