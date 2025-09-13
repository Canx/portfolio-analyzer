import streamlit as st
import pandas as pd
import json
from pathlib import Path
import time
import random

# Esta función se mantiene igual
@st.cache_data
def load_config(config_file="fondos.json"):
    """Carga la configuración de fondos desde un JSON."""
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])


# --- NUEVA FUNCIÓN CACHEADA PARA UN SOLO FONDO ---
@st.cache_data
def load_single_fund_nav_cached(_data_manager, isin: str, force_update: bool = False):
    """
    Obtiene el NAV de un único fondo y cachea el resultado.
    El guion bajo en _data_manager evita que Streamlit intente cachear el objeto.
    """
    return _data_manager.get_fund_nav(isin, force_to_today=force)


# --- FUNCIÓN load_all_navs MODIFICADA (YA NO ESTÁ CACHEADA) ---
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    """
    Orquesta la carga de datos para múltiples ISINs, llamando a la
    función cacheada para cada uno. Añade una pausa para evitar bloqueos.
    """
    all_navs = {}
    
    # El spinner ahora se muestra fuera, en la página que llama a la función si es necesario
    # st.spinner(f"Cargando datos de {len(isines)} fondos...")

    for i, isin in enumerate(isines):
        # La pausa se mantiene para las llamadas que SÍ van a la API
        if i > 0:
            pausa = random.uniform(1, 3)
            time.sleep(pausa)

        force = (isin == force_update_isin)
        
        # Llamamos a la nueva función cacheada individual
        df = load_single_fund_nav_cached(_data_manager, isin, force_update=force)
        
        if df is not None and 'nav' in df.columns:
            all_navs[isin] = df['nav']
            
    if not all_navs:
        return pd.DataFrame()
        
    return pd.concat(all_navs, axis=1).ffill()
