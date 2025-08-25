# src/data_manager.py

import pandas as pd
import mstarpy as ms
from pathlib import Path
from datetime import date, timedelta
import streamlit as st

class DataManager:
    """
    Gestiona la obtención y el cacheo local de los datos NAV de los fondos.
    Versión optimizada para minimizar llamadas a la API.
    """
    def __init__(self, data_dir: str = "fondos_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.today = date.today()
        # Define qué consideramos "reciente". 5 días cubre fines de semana.
        self.recency_threshold_days = 5

    def _download_nav(self, isin: str, start_date: date, end_date: date) -> pd.DataFrame | None:
        """Descarga datos de Morningstar para un ISIN y un rango de fechas."""
        st.write(f"🌐 Llamando a la API para {isin} desde {start_date}...")
        try:
            fund = ms.Funds(isin)
            nav_data = pd.DataFrame(fund.nav(start_date=start_date, end_date=end_date))

            if nav_data.empty:
                return None
            
            nav_col = next((c for c in ["nav", "accumulatedNav", "totalReturn"] if c in nav_data.columns), None)
            if nav_col is None:
                st.warning(f"No se encontró columna NAV válida para {isin}")
                return None

            df = nav_data.rename(columns={nav_col: "nav"})[["date", "nav"]]
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").drop_duplicates(subset="date")

        except Exception as e:
            st.error(f"Error descargando {isin}: {e}")
            return None

    def get_fund_nav(self, isin: str, force_to_today: bool = False) -> pd.DataFrame | None:
        """
        Obtiene el NAV de un fondo. Comprueba si los datos locales son
        suficientemente recientes antes de hacer una llamada a la API.
        """
        file_path = self.data_dir / f"{isin}.csv"
        df = None

        # --- Paso 1: Intentar leer los datos locales existentes ---
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, parse_dates=["date"], index_col="date")
                df.index = pd.to_datetime(df.index)
            except Exception:
                df = None # Fichero corrupto, se tratará como si no existiera

        # --- Paso 2: LÓGICA DE OPTIMIZACIÓN ---
        # Si NO forzamos la actualización y los datos son recientes, los devolvemos directamente.
        if not force_to_today and df is not None and not df.empty:
            last_date = df.index.max().date()
            if last_date >= self.today - timedelta(days=self.recency_threshold_days):
                st.write(f"📂 Datos de {isin} ya son recientes ({last_date}). Usando caché local.")
                return df

        # --- Paso 3: Si llegamos aquí, es necesario descargar o actualizar ---
        start_update_date = date(1900, 1, 1)
        if df is not None and not df.empty:
            start_update_date = df.index.max().date() + timedelta(days=1)
        
        if start_update_date <= self.today:
            nuevos_datos = self._download_nav(isin, start_date=start_update_date, end_date=self.today)
            
            if nuevos_datos is not None and not nuevos_datos.empty:
                nuevos_datos.set_index('date', inplace=True)
                df = pd.concat([df, nuevos_datos]) if df is not None else nuevos_datos
                df = df[~df.index.duplicated(keep='last')].sort_index()
                df.to_csv(file_path, index=True)

        return df
    
    
def filtrar_por_horizonte(df: pd.DataFrame, horizonte: str) -> pd.DataFrame:
    """Filtra un DataFrame con DatetimeIndex por un horizonte temporal."""
    if df.empty:
        return df

    df = df.sort_index()
    anchor = df.index.max()

    start = None
    if horizonte.endswith('m'):
        try:
            months = int(horizonte[:-1])
            start = anchor - pd.DateOffset(months=months)
        except (ValueError, TypeError):
            pass
    elif horizonte in ("1y", "3y", "5y"):
        years = int(horizonte[:-1])
        start = anchor - pd.DateOffset(years=years)
    elif horizonte.lower() == "ytd":
        start = pd.Timestamp(year=anchor.year, month=1, day=1)
    elif horizonte.lower() == "max":
        return df
    else:
        st.error(f"Horizonte no reconocido: {horizonte}")
        return df # Devuelve el original como fallback

    if start:
        return df.loc[start:anchor]
    
    # Si algo falló (ej. 'm' sin número válido), devuelve el original
    return df