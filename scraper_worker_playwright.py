# scraper_worker_playwright.py

import json
import time
import random
from playwright.sync_api import sync_playwright
from src.fund_operations_playwright import update_fund_csv_playwright

print("--- Iniciando Worker con Playwright ---")

try:
    with open('fondos.json') as file:
        fondos_data = json.load(file)
    # Ahora solo necesitamos el ISIN
    isins_a_procesar = [fondo.get("isin") for fondo in fondos_data.get('fondos', []) if fondo.get("isin")]
    print(f"✅ Se encontraron {len(isins_a_procesar)} ISINs en 'fondos.json'.")
except Exception as e:
    print(f"❌ Error al cargar 'fondos.json': {e}"); exit()

# Lanzamos el navegador UNA SOLA VEZ al principio
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    for i, isin in enumerate(isins_a_procesar):
        print(f"\nProcesando {i+1}/{len(isins_a_procesar)}: {isin}...")
        
        # Reutilizamos la misma página para cada fondo
        update_fund_csv_playwright(page, isin)
        
        if i < len(isins_a_procesar) - 1:
            pausa = random.uniform(5, 10) # Pausa reducida, ya que no abrimos/cerramos navegadores
            print(f"  -> Esperando {pausa:.0f} segundos...")
            time.sleep(pausa)

    browser.close()

print("\n--- Worker con Playwright finalizado ---")