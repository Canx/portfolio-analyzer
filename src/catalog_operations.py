# src/catalog_operations.py

from playwright.sync_api import Page, Route, expect
import pandas as pd
import re
import json
import time
from datetime import datetime

def scrape_fund_data(page: Page, isin: str) -> dict | None:
    """
    Función de scraping robusta y definitiva para Morningstar.
    """
    performance_id = None
    security_id = None
    metadata = {}

    # --- PASO 1: Búsqueda inicial ---
    def handle_search_route(route: Route):
        nonlocal performance_id, security_id, metadata
        response = route.fetch()
        # Estas sentencias de depuración son críticas para la sincronización.
        # No las elimines.
        # print(f"--- DEBUG: Search API Response Status: {response.status} ---")
        try:
            response_text = response.text()
            # print(f"--- DEBUG: Search API Response Text: {response_text[:100]} ... ---")
            data = json.loads(response_text)
            if data.get('results'):
                result = data['results'][0]
                performance_id = result['meta'].get('performanceID')
                security_id = result['meta'].get('securityID')
                metadata.update({
                    'name': result.get('fields', {}).get('name', {}).get('value'),
                    'isin': result.get('fields', {}).get('isin', {}).get('value'),
                    'performance_id': performance_id,
                    'security_id': security_id
                })
        except Exception:
            pass # Ignorar errores de parseo si la respuesta no es JSON
        
        route.fulfill(response=response)

    try:
        print("  -> Realizando búsqueda inicial...")
        page.route("**/api/v1/es/search/securities**", handle_search_route)
        page.goto("https://www.morningstar.es/", wait_until="domcontentloaded", timeout=60000)

        role_button = page.get_by_role("button", name="Soy un Inversor Individual")
        if role_button.is_visible():
            role_button.click()

        search_box = page.locator('input[placeholder="Buscar cotizaciones"]')
        search_box.wait_for(timeout=15000)
        search_box.fill(isin)
        page.wait_for_timeout(5000)
        page.unroute("**/api/v1/es/search/securities**")

    except Exception as e:
        print(f"  -> ❌ Error en la búsqueda inicial: {e}")
        return None

    if not security_id:
        print(f"  -> No se pudo encontrar el SecurityID necesario para {isin}.")
        return None
    print(f"  -> ✅ SecurityID encontrado: {security_id}")

    # --- PASO 2: Obtención de Metadatos ---
    try:
        print("  -> Obteniendo metadatos...")
        quote_url = f"https://global.morningstar.com/es/inversiones/fondos/{metadata['performance_id']}/cotizacion"
        srri_api_pattern = f"**/sal-service/v1/fund/quote/v7/{security_id}/data**"
        category_api_pattern = f"**/sal-service/v1/fund/esgRisk/{security_id}/data**"
        meta_api_pattern = f"**/sal-service/v1/fund/securityMetaData/{security_id}**"

        with page.expect_response(srri_api_pattern, timeout=20000) as srri_info, \
             page.expect_response(category_api_pattern, timeout=20000) as category_info, \
             page.expect_response(meta_api_pattern, timeout=20000) as meta_info:
            page.goto(quote_url, wait_until="domcontentloaded")

        srri_data = srri_info.value.json()
        metadata['ter'] = float(srri_data.get("onGoingCharge") or srri_data.get("totalExpenseRatio", 0)) * 100
        metadata['srri'] = int(srri_data.get("srri", 0))
        category_data = category_info.value.json()
        metadata['morningstar_category'] = category_data.get("globalCategoryName")
        meta_data = meta_info.value.json()
        metadata['domicilio'] = meta_data.get("domicileCountryId")
        metadata['currency'] = meta_data.get("baseCurrencyId")
        
        matriz_url = f"https://global.morningstar.com/es/inversiones/fondos/{metadata['performance_id']}/matriz"
        with page.expect_response(f"**/sal-service/v1/fund/parent/parentSummary/{security_id}/data**", timeout=20000) as manager_info:
            page.goto(matriz_url, wait_until="domcontentloaded")
        
        manager_data = manager_info.value.json()
        metadata['gestora'] = manager_data.get("firmName")
        print("  -> ✅ Metadatos obtenidos.")

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudieron obtener todos los metadatos. Error: {e}")

    # --- PASO 3: Obtención de Precios Históricos (Lógica de Doble Captura con Predicado) ---
    prices_df = None
    try:
        print("  -> Obteniendo precios históricos...")
        graph_url = f"https://global.morningstar.com/es/inversiones/fondos/{metadata['performance_id']}/grafico"
        page.goto(graph_url, wait_until="domcontentloaded", timeout=20000)

        page.get_by_text("PERÍODO", exact=True).wait_for(timeout=20000)

        period_select = page.locator('select.mds-select__input___markets').first
        frequency_select = page.locator('select.mds-select__input___markets').nth(1)

        print("  -> Seleccionando período y frecuencia...")
        with page.expect_response(
            lambda response: "chartservice/v2/timeseries" in response.url and "frequency=d" in response.url,
            timeout=20000
        ) as ts_response_info:
            period_select.select_option("max")
            page.wait_for_timeout(1000)
            frequency_select.select_option("d")

        timeseries_data = ts_response_info.value.json()
        if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
            df = pd.DataFrame(timeseries_data[0]['series'])
            df.dropna(subset=['date', 'nav'], inplace=True)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                prices_df = df[['date', 'nav']]
                num_navs = len(prices_df)
                start_date = prices_df['date'].min().strftime('%Y-%m-%d')
                end_date = prices_df['date'].max().strftime('%Y-%m-%d')
                print(f"  -> ✅ {num_navs} NAVs obtenidos desde {start_date} hasta {end_date}.")
    except Exception as e:
        print(f"  -> ❌ Error al obtener los precios: {e}")

    # --- PASO 4: Devolver resultado ---
    if 'isin' in metadata and prices_df is not None:
        return {"metadata": metadata, "prices": prices_df}
    else:
        if prices_df is not None:
            metadata['isin'] = isin
            return {"metadata": metadata, "prices": prices_df}
        
        print("  -> Fallo al recopilar la información completa del fondo.")
        return None