# src/utils.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path

# Estas funciones ahora vivirán aquí y serán importadas por las páginas que las necesiten.


@st.cache_data
def load_config(config_file="fondos.json"):
    """Carga la configuración de fondos desde un JSON."""
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])


@st.cache_data
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    """Función centralizada y cacheada para cargar todos los datos NAV."""
    with st.spinner(f"Cargando datos de {len(isines)} fondos..."):
        all_navs = {}
        for isin in isines:
            force = isin == force_update_isin
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None and "nav" in df.columns:
                all_navs[isin] = df["nav"]
    if not all_navs:
        return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()
