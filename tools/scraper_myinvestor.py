import os
import time
import json
import re
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

# --- CONFIGURACIÓN ---
# Carga las variables de entorno desde el fichero .env
load_dotenv()

# Lee las credenciales de forma segura desde las variables de entorno
MYINVESTOR_USER = os.getenv("MYINVESTOR_USER")
MYINVESTOR_PASSWORD = os.getenv("MYINVESTOR_PASSWORD")
OUTPUT_FILE = "myinvestor_isins.json"

def scrape_myinvestor_isins():
    """
    Inicia sesión en MyInvestor, navega a la sección de fondos y extrae todos los ISINs.
    """
    if not MYINVESTOR_USER or not MYINVESTOR_PASSWORD or "TU_DNI" in MYINVESTOR_USER:
        print("❌ Error: Por favor, configura tus credenciales en el fichero .env")
        return

    print("--- Iniciando Scraper de MyInvestor ---")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=100) # headless=False para ver lo que pasa
        page = browser.new_page()

        try:
            # --- PASO 1: Iniciar Sesión ---
            print("➡️  Paso 1: Navegando a la página principal de MyInvestor...")
            page.goto("https://www.myinvestor.es/", timeout=60000)

            print("➡️  Paso 1: Aceptando las cookies...")
            page.get_by_role("button", name="Aceptar cookies").click(timeout=15000)
            print("✅ Paso 1: Cookies aceptadas.")

            print("➡️  Paso 1: Buscando y haciendo clic en 'Inicia sesión'...")
            page.locator('nav.nav-desktop button[data-cy="cta-header-signin-click"]').click()

            page.wait_for_url("https://newapp.myinvestor.es/auth/signin/**", timeout=30000)
            print("➡️  Paso 1: Página de login cargada. Rellenando credenciales...")
            
            page.locator('input[placeholder="DNI / NIE / Pasaporte"]').fill(MYINVESTOR_USER)
            page.locator('input[placeholder="Contraseña"]').fill(MYINVESTOR_PASSWORD)
            page.get_by_role("button", name="Iniciar sesión").click()
            
            print("✅ Paso 1: Login enviado. Esperando a la autenticación...")
            
            # --- LÓGICA DE ESPERA CORREGIDA ---
            # Ahora esperamos a la URL de productos que has identificado.
            page.wait_for_url("https://newapp.myinvestor.es/app/products", timeout=90000)
            print("✅ Paso 1: Autenticación completada. Área de cliente cargada.")

            # --- 2. Navegar a la Página de Fondos ---
            print("\n➡️  Paso 2: Navegando al buscador de fondos...")
            funds_url = "https://newapp.myinvestor.es/app/explore/investments/funds/search"
            page.goto(funds_url, wait_until="load", timeout=60000)
            
            page.wait_for_selector("table.dpvxsb0", timeout=30000)
            print("✅ Paso 2: Página y tabla de fondos cargadas.")
            
            # --- 3. Hacer Scroll para Cargar Todos los Fondos ---
            print("\n➡️  Paso 3: Haciendo scroll para cargar todos los datos...")
            previous_height = -1
            consecutive_no_change = 0
            
            while consecutive_no_change < 5:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2.5)
                
                current_height = page.evaluate("document.body.scrollHeight")
                
                if current_height == previous_height:
                    consecutive_no_change += 1
                else:
                    consecutive_no_change = 0
                
                previous_height = current_height
                print(f"   -> Altura del scroll: {current_height}px")

            print("✅ Paso 3: Scroll completado.")

            # --- 4. Extraer los ISINs ---
            print("\n➡️  Paso 4: Extrayendo ISINs de la página...")
            isin_pattern = re.compile(r'[A-Z]{2}[A-Z0-9]{9}\d')
            all_cells_text = page.locator("td.dpvxsb9").all_text_contents()
            
            found_isins = []
            for text in all_cells_text:
                match = isin_pattern.search(text)
                if match:
                    found_isins.append(match.group(0))
            
            unique_isins = sorted(list(set(found_isins)))
            
            print(f"✅ Paso 4: Se han encontrado {len(unique_isins)} ISINs únicos.")

            # --- 5. Guardar los Resultados ---
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(unique_isins, f, indent=2)
            print(f"\n🎉 ¡Éxito! Los ISINs se han guardado en el fichero '{OUTPUT_FILE}'.")

        except Exception as e:
            print(f"\n❌ Error durante el proceso: {e}")
            print("   -> Se ha guardado una captura de pantalla como 'error_screenshot.png' para depuración.")
            page.screenshot(path="error_screenshot.png")
        finally:
            browser.close()
            print("\n--- Scraper finalizado ---")

if __name__ == "__main__":
    scrape_myinvestor_isins()



