# src/utils.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import time
import random

@st.cache_data
def load_config(config_file="fondos.json"):
    """Carga la configuración de fondos desde un JSON."""
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])


# --- FUNCIÓN CACHEADA CORREGIDA ---
@st.cache_data
def load_single_fund_nav_cached(_data_manager, isin: str, force_update: bool = False):
    """
    Obtiene el NAV de un único fondo y cachea el resultado.
    """
    # --- LÍNEA CORREGIDA ---
    # Usamos 'force_update', que es el nombre correcto del parámetro.
    return _data_manager.get_fund_nav(isin, force_to_today=force_update)


def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    """
    Orquesta la carga de datos. YA NO NECESITA LA PAUSA.
    """
    all_navs = {}
    for isin in isines:
        # --- PAUSA ELIMINADA DE AQUÍ ---
        force = (isin == force_update_isin)
        df = load_single_fund_nav_cached(_data_manager, isin, force_update=force)
        
        if df is not None and 'nav' in df.columns:
            all_navs[isin] = df['nav']
            
    if not all_navs:
        return pd.DataFrame()
        
    return pd.concat(all_navs, axis=1).ffill()
