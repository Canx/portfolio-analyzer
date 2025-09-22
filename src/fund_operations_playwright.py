# src/fund_operations_playwright.py

from playwright.sync_api import sync_playwright, Page, Route
import pandas as pd
from pathlib import Path
from datetime import date, timedelta
import json
from src.db_connector import get_db_connection # <-- NUEVA IMPORTACIÓN
from psycopg2.extras import execute_values # <-- NUEVA IMPORTACIÓN

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
    
    page.remove_listener("response", handle_response)

    if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
        df = pd.DataFrame(timeseries_data[0]['series'])
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'], errors='coerce')
        # Aseguramos que solo devolvemos las columnas que nos interesan
        return_cols = ['date']
        if 'nav' in df.columns:
            return_cols.append('nav')
        
        # --- CORRECCIÓN SettingWithCopyWarning ---
        # Devolvemos una copia explícita para evitar la advertencia
        return df[return_cols].copy()
    
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
    
# --- NUEVA FUNCIÓN ---
def find_and_add_fund_to_catalog(page: Page, isin: str, config_file: str = "fondos.json"):
    """
    Busca los detalles de un fondo por ISIN usando Playwright y, si lo encuentra,
    lo añade al fichero de catálogo (fondos.json).
    Devuelve True si tiene éxito, False si no.
    """
    found_details = {
        "performanceID": None,
        "name": None
    }
    
    def handle_route(route: Route):
        nonlocal found_details
        response = route.fetch()
        try:
            data = response.json()
            if data.get('results'):
                meta = data['results'][0]['meta']
                fields = data['results'][0]['fields']
                found_details["performanceID"] = meta.get('performanceID')
                found_details["name"] = fields.get('name', {}).get('value')
                print(f"  -> Datos encontrados: {found_details['name']}")
        except Exception:
            pass
        route.fulfill(response=response)

    try:
        page.route("**/api/v1/es/search/securities**", handle_route)
        page.goto("https://www.morningstar.es/", wait_until="domcontentloaded", timeout=60000)
        
        search_box = page.locator('input[placeholder="Buscar cotizaciones"]')
        search_box.wait_for(timeout=15000)
        search_box.fill(isin)
        page.wait_for_timeout(5000)
        
    except Exception as e:
        print(f"  -> ❌ Error durante la búsqueda del fondo: {e}")
        return False
    finally:
        page.unroute("**/api/v1/es/search/securities**")

    # Si hemos encontrado los detalles, los añadimos al fichero JSON
    if found_details.get("performanceID") and found_details.get("name"):
        try:
            # Leemos el fichero JSON actual
            config_path = Path(config_file)
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            else:
                config_data = {"fondos": []}

            # Añadimos el nuevo fondo con los datos obtenidos y placeholders
            new_fund = {
                "isin": isin,
                "performanceID": found_details["performanceID"],
                "nombre": found_details["name"],
                "gestora": "Desconocida", # Estos datos no los podemos obtener fácilmente
                "ter": None,
                "srri": None,
                "domicilio": None
            }
            config_data["fondos"].append(new_fund)

            # Guardamos el fichero actualizado
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"  -> ❌ Error al guardar en '{config_file}': {e}")
            return False
            
    return False


def update_fund_in_db(page: Page, isin: str) -> bool:
    """
    Función que orquesta el proceso para un ISIN, guardando los datos en PostgreSQL.
    """
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        last_date_in_db = None
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(date) FROM historical_prices WHERE isin = %s", (isin,))
                result = cursor.fetchone()
                if result and result[0]: last_date_in_db = result[0]
        except Exception:
            conn.rollback()

        today = date.today()
        if last_date_in_db and (today - last_date_in_db).days < 2:
            print(f"  -> Datos recientes (última fecha: {last_date_in_db}). Saltando.")
            return False

        performance_id = find_performance_id(page, isin)
        if not performance_id: return False
            
        nuevos_datos_df = get_nav_data_with_playwright(page, performance_id)
        
        if nuevos_datos_df is not None and not nuevos_datos_df.empty:
            
            # Limpiamos los datos malos (donde la fecha o el NAV son nulos)
            nuevos_datos_df.dropna(subset=['date', 'nav'], inplace=True)

            if nuevos_datos_df.empty:
                print("  -> No se encontraron nuevos datos válidos tras la limpieza.")
                return False

            data_to_insert = [
                (isin, row['date'].date(), row['nav']) 
                for index, row in nuevos_datos_df.iterrows()
            ]
            
            with conn.cursor() as cursor:
                execute_values(cursor, "INSERT INTO historical_prices (isin, date, nav) VALUES %s ON CONFLICT (isin, date) DO NOTHING", data_to_insert)
                conn.commit()
                print(f"  -> ✅ {cursor.rowcount} nuevos registros de precios insertados.")
            return True
        else:
            print(f"  -> ❌ No se pudieron obtener nuevos datos para {isin}.")
            return False
    finally:
        if conn:
            conn.close()