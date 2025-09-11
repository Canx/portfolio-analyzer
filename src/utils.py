# src/utils.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import time   # <-- Importamos la librería time
import random # <-- Importamos la librería random

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
    """
    Función centralizada para cargar datos NAV.
    AÑADE UNA PAUSA ALEATORIA entre cada petición para evitar bloqueos.
    """
    with st.spinner(f"Cargando datos de {len(isines)} fondos..."):
        all_navs = {}
        for i, isin in enumerate(isines):
            # --- LÓGICA AÑADIDA ---
            # Si no es la primera petición, hacemos una pausa
            if i > 0:
                # Esperamos entre 1 y 3 segundos para parecer más humanos
                pausa = random.uniform(1, 3)
                time.sleep(pausa)

            force = (isin == force_update_isin)
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None and 'nav' in df.columns:
                all_navs[isin] = df['nav']
    if not all_navs: return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()
