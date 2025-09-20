# src/utils.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path

@st.cache_data
def load_config(config_file="fondos.json"):
    """Carga la configuración de fondos desde un JSON."""
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])

@st.cache_data
def load_single_fund_nav_cached(_data_manager, isin: str):
    """
    Obtiene el NAV de un único fondo desde el CSV y cachea el resultado.
    Ya no tiene el parámetro 'force_update'.
    """
    return _data_manager.get_fund_nav(isin)

def load_all_navs(_data_manager, isines: tuple):
    """
    Orquesta la carga de datos LEYENDO SIEMPRE DESDE LOS FICHEROS CSV.
    Ya no tiene el parámetro 'force_update_isin'.
    """
    all_navs = {}
    for isin in isines:
        df = load_single_fund_nav_cached(_data_manager, isin)
        
        if df is not None and 'nav' in df.columns:
            all_navs[isin] = df['nav']
            
    if not all_navs:
        return pd.DataFrame()
        
    return pd.concat(all_navs, axis=1).ffill()
