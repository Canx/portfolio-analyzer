from playwright.sync_api import Page, Route
import pandas as pd
from bs4 import BeautifulSoup
import re

def scrape_fund_data(page: Page, isin: str) -> dict | None:
    """
    Función mejorada de scraping. Dado un ISIN, busca toda su información,
    incluyendo metadatos detallados de la página de cotización.
    """
    performance_id = None
    metadata = {}

    # --- Paso 1: Buscar el fondo para obtener su performanceID ---
    def handle_search_route(route: Route):
        nonlocal performance_id, metadata
        response = route.fetch()
        try:
            data = response.json()
            if data.get('results'):
                result = data['results'][0]
                performance_id = result['meta'].get('performanceID')
                metadata['name'] = result.get('fields', {}).get('name', {}).get('value')
                metadata['isin'] = result.get('fields', {}).get('isin', {}).get('value')
                metadata['performance_id'] = performance_id
                print(f"  -> ID de rendimiento encontrado: {performance_id}")
        except Exception:
            pass
        route.fulfill(response=response)

    try:
        page.route("**/api/v1/es/search/securities**", handle_search_route)
        print("  -> Buscando el fondo en Morningstar.es...")
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

    if not performance_id:
        print(f"  -> No se pudo encontrar el performanceID para {isin}.")
        return None

    # --- Paso 2: Ir a la página de Cotización para extraer metadatos ---
    try:
        quote_url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/cotizacion"
        print(f"  -> Navegando a la página de cotización para obtener metadatos...")
        page.goto(quote_url, wait_until="load", timeout=45000)
        
        # Usamos BeautifulSoup para parsear el HTML
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')

        # Buscamos los datos en la tabla de la página
        # Esta es una forma más robusta de encontrar los datos, buscando por las etiquetas
        labels = soup.find_all("span", class_="sal-dp-value")
        values = soup.find_all("span", class_="sal-dp-data")

        # Creamos un diccionario con los datos encontrados
        for label, value in zip(labels, values):
            label_text = label.get_text(strip=True)
            value_text = value.get_text(strip=True)
            
            if "Categoría Morningstar" in label_text:
                metadata['morningstar_category'] = value_text
            elif "TER" in label_text:
                # Extraemos solo el número del TER
                ter_match = re.search(r'(\d+\.\d+)', value_text)
                if ter_match:
                    metadata['ter'] = float(ter_match.group(1))
            elif "Domicilio" in label_text:
                metadata['domicilio'] = value_text
            elif "Gestora" in label_text:
                metadata['gestora'] = value_text

        print("  -> ✅ Metadatos detallados extraídos con éxito.")

    except Exception as e:
        print(f"  -> ⚠️ Aviso: No se pudieron extraer los metadatos detallados. Se usarán los básicos. Error: {e}")


    # --- Paso 3: Ir a la página del Gráfico para obtener los precios ---
    timeseries_data = None
    def handle_chart_response(response):
        nonlocal timeseries_data
        if "QS-markets/chartservice/v2/timeseries" in response.url:
            print("  -> ✅ ¡Petición de datos del gráfico interceptada!")
            try:
                timeseries_data = response.json()
            except Exception as e:
                print(f"  -> ❌ Error al leer el JSON de precios: {e}")

    page.on("response", handle_chart_response)
    try:
        url = f"https://global.morningstar.com/es/inversiones/fondos/{performance_id}/grafico"
        print(f"  -> Navegando a la página del gráfico...")
        page.goto(url, wait_until="load", timeout=45000)
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  -> ❌ Error al cargar la página del gráfico: {e}")
    finally:
        page.remove_listener("response", handle_chart_response)
        
    # --- Paso 4: Procesar y devolver los datos ---
    prices_df = None
    if timeseries_data and isinstance(timeseries_data, list) and timeseries_data[0].get('series'):
        df = pd.DataFrame(timeseries_data[0]['series'])
        df.dropna(subset=['date', 'nav'], inplace=True)
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            prices_df = df[['date', 'nav']]

    if metadata and prices_df is not None:
        return {
            "metadata": metadata,
            "prices": prices_df
        }
    else:
        print("  -> Fallo al recopilar la información completa del fondo.")
        return None