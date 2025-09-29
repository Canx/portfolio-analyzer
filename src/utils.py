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
    DESDE POSTGRESQL y aplicando un remuestreo diario individualizado para 
    evitar contaminación de datos.
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

        df['date'] = pd.to_datetime(df['date'])

        # Encontrar la fecha máxima global para alinear todos los fondos
        max_date = df['date'].max()

        all_navs_resampled = []
        for isin, group in df.groupby('isin'):
            fund_navs = group.set_index('date')[['nav']]
            
            # Usar la fecha máxima global para el índice de cada fondo
            daily_index = pd.date_range(start=fund_navs.index.min(), end=max_date, freq='D')
            
            resampled = fund_navs.reindex(daily_index).ffill()
            resampled.rename(columns={'nav': isin}, inplace=True)
            all_navs_resampled.append(resampled)

        if not all_navs_resampled:
            return pd.DataFrame()
            
        final_df = pd.concat(all_navs_resampled, axis=1)
        final_df.index.name = 'date'
        
        # Un último ffill para alinear los puntos de inicio si algún fondo empieza antes que otro
        return final_df.ffill()
        
    except Exception as e:
        st.error(f"Error al procesar los precios desde la base de datos: {e}")
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()