# src/utils.py

import streamlit as st
import pandas as pd
from src.db_connector import get_db_connection

@st.cache_data
def load_single_fund_nav_cached(_data_manager, isin: str):
    """
    Obtiene el NAV de un único fondo desde el CSV y cachea el resultado.
    Ya no tiene el parámetro 'force_update'.
    """
    return _data_manager.get_fund_nav(isin)

@st.cache_data
def load_funds_from_db():
    """
    Carga el catálogo completo de fondos desde la base de datos PostgreSQL.
    Esta es ahora la única fuente de verdad para el catálogo.
    """
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql("SELECT * FROM funds", conn)
            return df
        finally:
            conn.close()
    return pd.DataFrame()

@st.cache_data
def load_all_navs(_data_manager, isines: tuple):
    """
    Orquesta la carga de datos para un conjunto de ISINs LEYENDO DIRECTAMENTE
    DESDE POSTGRESQL en una sola consulta eficiente.
    """
    if not isines:
        return pd.DataFrame()

    conn = get_db_connection()
    if not conn:
        st.error("No se pudo conectar a la base de datos de precios.")
        return pd.DataFrame()
        
    try:
        query = "SELECT date, isin, nav FROM historical_prices WHERE isin IN %s"
        df = pd.read_sql(query, conn, params=(isines,))
        
        if df.empty:
            return pd.DataFrame()

        # --- LÍNEA AÑADIDA: La Solución ---
        # Convertimos explícitamente la columna 'date' al formato correcto (Timestamp)
        # antes de usarla como índice.
        df['date'] = pd.to_datetime(df['date'])
            
        nav_table = df.pivot_table(index='date', columns='isin', values='nav')
        
        # Rellenamos los valores nulos que puedan quedar en fines de semana o festivos
        return nav_table.ffill()
        
    except Exception as e:
        st.error(f"Error al leer los precios desde la base de datos: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()