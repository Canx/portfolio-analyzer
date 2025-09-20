# src/fund_operations.py

import mstarpy as ms
import pandas as pd
from pathlib import Path
import json
import time
import random
from datetime import date, timedelta

def download_nav_data(isin: str, start_date: date, end_date: date) -> pd.DataFrame | None:
    """
    Descarga datos de Morningstar con una lógica de reintentos y espera exponencial.
    """
    max_retries = 4
    base_delay = 10

    for attempt in range(max_retries):
        try:
            if attempt == 0:
                time.sleep(random.uniform(3, 5))
            
            fund = ms.Funds(isin)
            nav_data = pd.DataFrame(fund.nav(start_date=start_date, end_date=end_date))
            
            if nav_data.empty: return None
            nav_col = next((c for c in ["nav", "accumulatedNav", "totalReturn"] if c in nav_data.columns), None)
            if nav_col is None: return None
            df = nav_data.rename(columns={nav_col: "nav"})[["date", "nav"]]
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").drop_duplicates(subset="date")

        except Exception as e:
            error_message = str(e).lower()
            if "401" in error_message or "unauthorized" in error_message or "timeout" in error_message:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    print(f"  -> Error de API (intento {attempt + 1}/{max_retries}). Reintentando en {delay:.0f} segundos...")
                    time.sleep(delay)
                else:
                    print(f"  -> ❌ Error: La API ha fallado después de {max_retries} intentos. El ISIN no se actualizará.")
                    return None
            else:
                print(f"  -> ❌ Error no recuperable al descargar {isin}: {e}")
                return None
    
    return None

def update_fund_csv(isin: str, data_dir: str = "fondos_data"):
    """
    Función principal para el worker. Comprueba si los datos son recientes antes de intentar descargar.
    """
    data_dir_path = Path(data_dir)
    data_dir_path.mkdir(exist_ok=True)
    file_path = data_dir_path / f"{isin}.csv"
    
    last_date_in_csv = None
    df_existente = None
    if file_path.exists():
        try:
            df_existente = pd.read_csv(file_path, parse_dates=["date"], index_col="date")
            if not df_existente.empty:
                last_date_in_csv = df_existente.index.max().date()
        except Exception:
            df_existente = None
            
    today = date.today()

    # --- LÓGICA DE COMPROBACIÓN MEJORADA ---
    # Si tenemos datos y son de menos de 5 días de antigüedad (hoy o ayer),
    # consideramos que el fondo está actualizado y no hacemos nada.
    if last_date_in_csv and (today - last_date_in_csv).days < 5:
        print(f"  -> Datos recientes (última fecha: {last_date_in_csv}). No se necesita actualizar. Saltando.")
        return True

    start_update_date = date(1900, 1, 1)
    if last_date_in_csv:
        start_update_date = last_date_in_csv + timedelta(days=1)
    
    # Si la fecha de inicio es futura, tampoco hacemos nada
    if start_update_date > today:
        print(f"  -> El fichero CSV ya está actualizado (fecha inicio: {start_update_date}). Saltando.")
        return True

    print(f"  -> Buscando datos desde {start_update_date} hasta {today}...")
    nuevos_datos = download_nav_data(isin, start_date=start_update_date, end_date=today)
    
    if nuevos_datos is not None and not nuevos_datos.empty:
        nuevos_datos.set_index('date', inplace=True)
        df_final = pd.concat([df_existente, nuevos_datos]) if df_existente is not None else nuevos_datos
        df_final = df_final[~df_final.index.duplicated(keep='last')].sort_index()
        df_final.to_csv(file_path, index=True)
        print(f"  -> Se han añadido {len(nuevos_datos)} nuevos registros al CSV.")
    else:
        print("  -> No se encontraron nuevos datos.")
    
    return True