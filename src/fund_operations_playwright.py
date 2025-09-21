# src/fund_operations_playwright.py

from playwright.sync_api import sync_playwright, Page, Route
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
import json

# ... (la función find_performance_id no cambia) ...
def find_performance_id(page: Page, isin: str) -> str | None:
    """
    Paso 1: Usa el navegador para buscar un ISIN y capturar la respuesta de la API
    que contiene el performanceID.
    """
    performance_id = None
    
    def handle_route(route: Route):
        nonlocal performance_id
        response = route.fetch()
        try:
            data = response.json()
            if data.get('results'):
                meta = data['results'][0]['meta']
                performance_id = meta.get('performanceID')
                print(f"  -> ID de rendimiento encontrado: {performance_id}")
        except Exception:
            pass
        route.fulfill(response=response)

    try:
        page.route("**/api/v1/es/search/securities**", handle_route)
        
        print("  -> Buscando el fondo en Morningstar.es...")
        page.goto("https://www.morningstar.es/", wait_until="domcontentloaded", timeout=60000)
        
        search_box = page.locator('input[placeholder="Buscar cotizaciones"]')
        search_box.wait_for(timeout=15000)
        search_box.fill(isin)
        
        page.wait_for_timeout(5000)
        
    except Exception as e:
        print(f"  -> ❌ Error durante la búsqueda del performanceID: {e}")
    finally:
        page.unroute("**/api/v1/es/search/securities**")

    return performance_id


def get_nav_data_with_playwright(page: Page, performance_id: str) -> pd.DataFrame | None:
    """
    Paso 2: Navega a la página del gráfico y captura los datos históricos.
    """
    timeseries_data = None

    def handle_response(response):
        nonlocal timeseries_data
        if "QS-markets/chartservice/v2/timeseries" in response.url:
            print("  -> ✅ ¡Petición de datos del gráfico interceptada!")
            try:
                timeseries_data = response.json()
            except Exception as e:
                print(f"  -> ❌ Error al leer el JSON de la respuesta: {e}")

    page.on("response", handle_response)
    
    try:
        url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/grafico"
        print(f"  -> Navegando a la página del gráfico...")
        page.goto(url, wait_until="load", timeout=45000)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  -> ❌ Error al cargar la página del gráfico: {e}")
    
    # --- LÍNEA CORREGIDA ---
    # Cambiamos 'page.off' por el nombre correcto: 'page.remove_listener'
    page.remove_listener("response", handle_response)

    if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
        df = pd.DataFrame(timeseries_data[0]['series'])
        if 'date' in df.columns and 'nav' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            return df[['date', 'nav']]
    
    print("  -> No se pudieron capturar los datos del gráfico.")
    return None

# ... (la función update_fund_csv_playwright no cambia) ...
def update_fund_csv_playwright(page: Page, isin: str, data_dir: str = "fondos_data") -> bool:
    """
    Función que orquesta el proceso para un ISIN, buscando primero el ID.
    """
    data_dir_path = Path(data_dir)
    file_path = data_dir_path / f"{isin}.csv"
    
    performance_id = find_performance_id(page, isin)
    if not performance_id:
        return False
        
    df_existente = None
    if file_path.exists():
        try:
            df_existente = pd.read_csv(file_path, parse_dates=["date"], index_col="date")
        except Exception:
            df_existente = None
            
    nuevos_datos = get_nav_data_with_playwright(page, performance_id)
    
    if nuevos_datos is not None and not nuevos_datos.empty:
        nuevos_datos.set_index('date', inplace=True)
        df_final = pd.concat([df_existente, nuevos_datos]) if df_existente is not None else nuevos_datos
        df_final = df_final[~df_final.index.duplicated(keep='last')].sort_index()
        df_final.to_csv(file_path, index=True)
        print(f"  -> ✅ Fichero CSV para {isin} actualizado/creado con {len(df_final)} registros.")
        return True
    else:
        print(f"  -> ❌ No se pudieron obtener nuevos datos para {isin}.")
        return False