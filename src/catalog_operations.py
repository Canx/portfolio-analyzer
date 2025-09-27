# src/catalog_operations.py

from playwright.sync_api import Page, Route, expect
import pandas as pd
from bs4 import BeautifulSoup
import re
import json

def scrape_fund_data(page: Page, isin: str) -> dict | None:
    """
    Función de scraping DEFINITIVA. Usa el performanceId para navegar y el securityId
    para interceptar las llamadas a la API correctas, asegurando la captura de datos.
    """
    performance_id = None
    security_id = None
    metadata = {}

    # --- Paso 1: Buscar el fondo para obtener sus IDs ---
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

    # --- Paso 2: Ir a la página de Cotización para TER y SRRI ---
    try:
        quote_url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/cotizacion"
        srri_api_pattern = f"**/sal-service/v1/fund/quote/v7/{security_id}/data**"

        print(f"  -> Navegando a 'Cotización' para obtener TER y SRRI...")
        with page.expect_response(srri_api_pattern, timeout=20000) as srri_info:
            page.goto(quote_url, wait_until="domcontentloaded", timeout=20000)

        srri_response = srri_info.value
        if srri_response.ok:
            srri_data = srri_response.json()
            # CORRECCIÓN CLAVE: Multiplicamos el valor del TER por 100
            ter_value = srri_data.get("onGoingCharge") or srri_data.get("totalExpenseRatio")
            if ter_value is not None:
                metadata['ter'] = float(ter_value) * 100
                print(f"  -> ✅ TER capturado: {metadata['ter']:.2f}%")
            
            srri = srri_data.get("srri")
            if srri is not None:
                metadata['srri'] = int(srri)
                print(f"  -> ✅ SRRI capturado: {metadata['srri']}")

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudo capturar la API de Cotización. Error: {e}")

    # --- Paso 3: Ir a la página de Matriz para datos de la Gestora ---
    try:
        matriz_url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/matriz"
        manager_api_pattern = f"**/sal-service/v1/fund/parent/parentSummary/{security_id}/data**"

        print(f"  -> Navegando a 'Matriz' para obtener datos de la Gestora...")
        with page.expect_response(manager_api_pattern, timeout=20000) as manager_info:
            page.goto(matriz_url, wait_until="domcontentloaded", timeout=20000)

        manager_response = manager_info.value
        if manager_response.ok:
            manager_data = manager_response.json()
            firm_name = manager_data.get("firmName")
            if firm_name:
                metadata['gestora'] = firm_name
                print(f"  -> ✅ Gestora encontrada: {metadata['gestora']}")
        else:
             print(f"  -> Respuesta no OK de la API de Gestora: {manager_response.status}")

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudo capturar la API de la Gestora. Error: {e}")


    # --- Paso 4 (Opcional): Scraping HTML como fallback ---
    try:
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        labels = soup.find_all("span", class_="sal-dp-value")
        values = soup.find_all("span", class_="sal-dp-data")

        for label, value in zip(labels, values):
            label_text = label.get_text(strip=True)
            value_text = value.get_text(strip=True)

            if "Categoría Morningstar" in label_text: metadata.setdefault('morningstar_category', value_text)
            if "Domicilio" in label_text: metadata.setdefault('domicilio', value_text)
            if "Gestora" in label_text: metadata.setdefault('gestora', value_text)

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudieron extraer metadatos del HTML. Error: {e}")

    # --- Paso 5: Obtener precios desde la página de Gráfico ---
    prices_df = None
    try:
        print("  -> Navegando a 'Gráfico' para obtener precios...")
        graph_url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/grafico"
        with page.expect_response("**/chartservice/v2/timeseries**", timeout=15000) as ts_response_info:
            page.goto(graph_url, wait_until="domcontentloaded")

        timeseries_data = ts_response_info.value.json()
        if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
            df = pd.DataFrame(timeseries_data[0]['series'])
            df.dropna(subset=['date', 'nav'], inplace=True)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                prices_df = df[['date', 'nav']]
                print("  -> ✅ Precios históricos obtenidos.")
    except Exception as e:
        print(f"  -> ❌ Error al cargar la página o datos del gráfico: {e}")

    if 'isin' in metadata and prices_df is not None:
        return {"metadata": metadata, "prices": prices_df}
    else:
        print("  -> Fallo al recopilar la información completa del fondo.")
        return None