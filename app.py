# app.py (fichero en la raíz del proyecto)

import streamlit as st
import json
from pathlib import Path
from streamlit_local_storage import LocalStorage

st.set_page_config(
    page_title="Analizador de Carteras",
    page_icon="📊",
    layout="wide"
)

# --- FUNCIÓN DE INICIALIZACIÓN (AHORA VIVE AQUÍ) ---
def initialize_session_state(localS):
    """Inicializa el estado de la sesión para toda la app si no existe."""
    if 'initialized' not in st.session_state:
        json_cartera = localS.getItem('mi_cartera')
        cartera_guardada = {}
        if json_cartera:
            try:
                cartera_guardada = json.loads(json_cartera)
            except json.JSONDecodeError:
                st.warning("Formato de cartera guardada incorrecto.")
        
        st.session_state.cartera_isines = cartera_guardada.get('fondos', [])
        st.session_state.pesos = cartera_guardada.get('pesos', {})
        st.session_state.initialized = True

# --- LLAMADA A LA INICIALIZACIÓN ---
# Esto se ejecutará siempre, sin importar en qué página estemos.
localS = LocalStorage()
initialize_session_state(localS)


# --- Página de Bienvenida ---
st.title("📊 Bienvenido al Analizador de Carteras")

st.markdown("""
Esta aplicación te permite analizar y optimizar tus carteras de fondos de inversión.

### ¿Cómo empezar?
1.  **Añade fondos a tu catálogo:** Usa la página **Explorador de Fondos** para buscar y añadir nuevos fondos.
2.  **Construye tu cartera:** En el Explorador o en la página de Análisis, añade fondos a "Mi Cartera".
3.  **Analiza los resultados:** Navega a la página **Análisis de Cartera** para ver todas las métricas y gráficos interactivos.

**👈 Selecciona una página en el menú de la izquierda para comenzar.**
""")