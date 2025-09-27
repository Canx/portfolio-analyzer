# src/catalog_operations.py

from playwright.sync_api import Page, Route, expect
import pandas as pd
from bs4 import BeautifulSoup
import re
import json

def scrape_fund_data(page: Page, isin: str) -> dict | None:
    """
    Función de scraping DEFINITIVA. Usa una espera concurrente (Promise.all) para
    navegar y capturar la respuesta de la API de forma fiable, eliminando
    condiciones de carrera.
    """
    performance_id = None
    security_id = None
    ter_from_api = None
    srri_from_api = None
    metadata = {}

    # --- Paso 1: Buscar el fondo para obtener sus IDs (sin cambios) ---
    def handle_search_route(route: Route):
        nonlocal performance_id, security_id, metadata
        response = route.fetch()
        try:
            data = response.json()
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
                print(f"  -> PerformanceID encontrado: {performance_id}")
                print(f"  -> SecurityID encontrado: {security_id}")
        except Exception: pass
        route.fulfill(response=response)

    try:
        page.route("**/api/v1/es/search/securities**", handle_search_route)
        page.goto("https://www.morningstar.es/", wait_until="domcontentloaded", timeout=60000)
        search_box = page.locator('input[placeholder="Buscar cotizaciones"]')
        search_box.wait_for(timeout=15000)
        search_box.fill(isin)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  -> ❌ Error durante la búsqueda inicial: {e}")
        return None
    finally:
        page.unroute("**/api/v1/es/search/securities**")

    if not performance_id or not security_id:
        print(f"  -> No se pudo encontrar el ID necesario para {isin}.")
        return None

    # --- Paso 2: NAVEGAR y ESPERAR LA RESPUESTA DE FORMA CONCURRENTE ---
    try:
        print(f"  -> Navegando y esperando las APIs de TER y SRRI simultáneamente...")

        # URL de la página a la que vamos a navegar
        quote_url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/cotizacion"

        # Patrón de la URL de la API que queremos capturar para el TER
        ter_api_pattern = f"**/sal-service/v1/fund/price/costProjection/{security_id}/data**"

        # Patrón de la URL de la API que queremos capturar para el SRRI
        srri_api_pattern = f"**/sal-service/v1/fund/quote/v7/{security_id}/data**"

        # Ejecutamos ambas acciones en paralelo
        with page.expect_response(ter_api_pattern, timeout=20000) as ter_response_info, \
             page.expect_response(srri_api_pattern, timeout=20000) as srri_response_info:
            page.goto(quote_url, wait_until="domcontentloaded", timeout=20000)

        # Cuando ambas han terminado, procesamos las respuestas capturadas
        ter_response = ter_response_info.value
        if ter_response.ok:
            ter_data = ter_response.json()
            ter = ter_data.get("ongoingCostsOtherCosts")
            if ter is not None:
                print(f"  -> ✅ ¡Éxito! TER capturado de la red: {ter}%")
                ter_from_api = float(ter)

        metadata['ter'] = ter_from_api

        srri_response = srri_response_info.value
        if srri_response.ok:
            srri_data = srri_response.json()
            srri = srri_data.get("srri")
            if srri is not None:
                print(f"  -> ✅ ¡Éxito! SRRI capturado de la red: {srri}")
                srri_from_api = int(srri)

        metadata['srri'] = srri_from_api

    except Exception as e:
        print(f"  -> ⚠️  Aviso: No se pudo capturar alguna de las APIs. Se usará scraping como fallback. Error: {e}")


    # --- Paso 3: Extraer el resto de metadatos del HTML ---
    try:
        # Damos un respiro extra para que el JavaScript renderice todo
        page.wait_for_timeout(2000)
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Lógica de scraping (fallback)
        labels = soup.find_all("span", class_="sal-dp-value")
        values = soup.find_all("span", class_="sal-dp-data")

        for label, value in zip(labels, values):
            label_text = label.get_text(strip=True)
            value_text = value.get_text(strip=True)

            if "Categoría Morningstar" in label_text:
                metadata['morningstar_category'] = value_text
            elif "TER" in label_text and metadata.get('ter') is None:
                ter_match = re.search(r'(\d+\.?\d*)', value_text)
                if ter_match:
                    print(f"  -> TER obtenido por scraping (fallback): {ter_match.group(1)}%")
                    metadata['ter'] = float(ter_match.group(1))
            elif "Domicilio" in label_text:
                metadata['domicilio'] = value_text
            elif "Gestora" in label_text:
                metadata['gestora'] = value_text

        print("  -> Metadatos detallados extraídos.")

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudieron extraer los metadatos del HTML. Error: {e}")

    # --- Pasos 4 y 5 (Obtener precios y devolver datos) no cambian ---
    prices_df = None
    try:
        with page.expect_response("**/chartservice/v2/timeseries**", timeout=15000) as ts_response_info:
            url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/grafico"
            page.goto(url, wait_until="domcontentloaded")

        timeseries_data = ts_response_info.value.json()
        if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
            df = pd.DataFrame(timeseries_data[0]['series'])
            df.dropna(subset=['date', 'nav'], inplace=True)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                prices_df = df[['date', 'nav']]
    except Exception as e:
        print(f"  -> ❌ Error al cargar la página o datos del gráfico: {e}")

    if metadata and prices_df is not None:
        return {"metadata": metadata, "prices": prices_df}
    else:
        print("  -> Fallo al recopilar la información completa del fondo.")
        return None