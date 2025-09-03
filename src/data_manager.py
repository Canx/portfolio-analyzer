# src/data_manager.py

import pandas as pd
import mstarpy as ms
from pathlib import Path
from datetime import date, timedelta
import streamlit as st
import json


# --- La clase DataManager y filtrar_por_horizonte no cambian ---
class DataManager:
    # ... (código de la clase sin cambios)
    """
    Gestiona la obtención y el cacheo local de los datos NAV de los fondos.
    """

    def __init__(self, data_dir: str = "fondos_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.today = date.today()
        self.recency_threshold_days = 5

    def _download_nav(
        self, isin: str, start_date: date, end_date: date
    ) -> pd.DataFrame | None:
        st.write(f"🌐 Llamando a la API para {isin} desde {start_date}...")
        try:
            fund = ms.Funds(isin)
            nav_data = pd.DataFrame(fund.nav(start_date=start_date, end_date=end_date))
            if nav_data.empty:
                return None
            nav_col = next(
                (
                    c
                    for c in ["nav", "accumulatedNav", "totalReturn"]
                    if c in nav_data.columns
                ),
                None,
            )
            if nav_col is None:
                return None
            df = nav_data.rename(columns={nav_col: "nav"})[["date", "nav"]]
            df["date"] = pd.to_datetime(df["date"])
            return df.sort_values("date").drop_duplicates(subset="date")
        except Exception as e:
            st.error(f"Error descargando {isin}: {e}")
            return None

    def get_fund_nav(
        self, isin: str, force_to_today: bool = False
    ) -> pd.DataFrame | None:
        file_path = self.data_dir / f"{isin}.csv"
        df = None
        if file_path.exists():
            try:
                df = pd.read_csv(file_path, parse_dates=["date"], index_col="date")
                df.index = pd.to_datetime(df.index)
            except Exception:
                df = None
        if not force_to_today and df is not None and not df.empty:
            last_date = df.index.max().date()
            if last_date >= self.today - timedelta(days=self.recency_threshold_days):
                st.write(
                    f"📂 Datos de {isin} ya son recientes ({last_date}). Usando caché local."
                )
                return df
        start_update_date = date(1900, 1, 1)
        if df is not None and not df.empty:
            start_update_date = df.index.max().date() + timedelta(days=1)
        if start_update_date <= self.today:
            nuevos_datos = self._download_nav(
                isin, start_date=start_update_date, end_date=self.today
            )
            if nuevos_datos is not None and not nuevos_datos.empty:
                nuevos_datos.set_index("date", inplace=True)
                df = pd.concat([df, nuevos_datos]) if df is not None else nuevos_datos
                df = df[~df.index.duplicated(keep="last")].sort_index()
                df.to_csv(file_path, index=True)
        return df


def filtrar_por_horizonte(df: pd.DataFrame, horizonte: str) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.sort_index()
    anchor = df.index.max()
    start = None
    if horizonte.endswith("m"):
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
        return df
    if start:
        return df.loc[start:anchor]
    return df


# --- NUEVA FUNCIÓN HELPER PRIVADA ---
def _fetch_fund_metadata(isin: str) -> dict | None:
    """
    Función centralizada para obtener los metadatos de un fondo desde la API.
    Devuelve un diccionario con los datos o None si falla.
    """
    try:
        fund = ms.Funds(term=isin)
        snapshot_data = fund.snapshot()

        if not snapshot_data:
            st.warning(f"La API devolvió datos vacíos para {isin}.")
            return None

        metadata = {
            "isin": fund.isin,
            "nombre": fund.name,
            "nombre_legal": snapshot_data.get("LegalName", fund.name),
            "gestora": snapshot_data.get("BrandingCompanyName"),
            "ter": snapshot_data.get("TotalExpenseRatio"),
            "fecha_creacion": snapshot_data.get("InceptionDate"),
            "domicilio": snapshot_data.get("Domicile"),
            "srri": snapshot_data.get("CollectedSRRI", {}).get("Rank"),
        }
        return metadata

    except ValueError:
        st.error(f"Error: No se pudo encontrar ningún fondo con el ISIN '{isin}'.")
        return None
    except Exception as e:
        st.error(f"Ocurrió un error inesperado al buscar el fondo: {e}")
        return None


# --- FUNCIONES PÚBLICAS REFACTORIZADAS ---
def find_and_add_fund_by_isin(new_isin):
    """
    Añade un nuevo fondo al catálogo. Ahora usa el helper _fetch_fund_metadata.
    """
    config_file = Path("fondos.json")
    data = {"fondos": []}
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    if any(f["isin"] == new_isin for f in data["fondos"]):
        fund_name = next(
            (f["nombre"] for f in data["fondos"] if f["isin"] == new_isin), new_isin
        )
        st.warning(f"El fondo '{fund_name}' ({new_isin}) ya existe en el catálogo.")
        return False

    st.info(f"Buscando información para el ISIN {new_isin}...")
    metadata = _fetch_fund_metadata(new_isin)

    if metadata:
        data["fondos"].append(metadata)
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        st.success(f"¡Fondo '{metadata['nombre']}' añadido! La app se recargará.")
        return True
    return False


def update_fund_details_in_config(isin_to_update: str):
    """
    Actualiza los datos de un fondo existente. Ahora usa el helper _fetch_fund_metadata.
    """
    config_file = Path("fondos.json")
    if not config_file.exists():
        return False

    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    fund_found_and_updated = False
    for i, fund_details in enumerate(data["fondos"]):
        if fund_details["isin"] == isin_to_update:
            st.info(f"Actualizando metadatos para {fund_details['nombre']}...")
            metadata = _fetch_fund_metadata(isin_to_update)

            if metadata:
                # Usamos .update() para fusionar los datos nuevos con los existentes
                data["fondos"][i].update(metadata)
                fund_found_and_updated = True
            break

    if fund_found_and_updated:
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        st.success("Metadatos actualizados en fondos.json.")
        return True

    return False
