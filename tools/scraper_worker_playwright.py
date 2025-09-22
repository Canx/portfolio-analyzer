import sys
import os
# Añadimos el directorio raíz del proyecto al path de Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import argparse # <-- NUEVA IMPORTACIÓN
from pathlib import Path # <-- NUEVA IMPORTACIÓN
from playwright.sync_api import sync_playwright
from src.fund_operations_playwright import update_fund_in_db
from src.db_connector import get_db_connection

# --- 1. CONFIGURAR EL PARSER DE ARGUMENTOS ---
parser = argparse.ArgumentParser(description="Worker con Playwright para actualizar datos de fondos.")
parser.add_argument(
    '--only-new',
    action='store_true',  # Esto convierte el argumento en una bandera (flag)
    help="Si se especifica, solo procesará los fondos que no tengan un fichero CSV existente."
)
args = parser.parse_args()

print("--- Iniciando Worker con Playwright (para PostgreSQL) ---")

# --- LÓGICA MODIFICADA: LEER ISINs DESDE LA BD ---
try:
    conn = get_db_connection()
    with conn.cursor() as cursor:
        cursor.execute("SELECT isin FROM funds")
        # Obtenemos una lista de tuplas, así que la aplanamos
        isins_a_procesar = [item[0] for item in cursor.fetchall()]
    conn.close()
    print(f"✅ Se encontraron {len(isins_a_procesar)} ISINs en la base de datos.")
except Exception as e:
    print(f"❌ Error al leer ISINs de la base de datos: {e}"); exit()

# --- 3. APLICAR EL FILTRO SI EL FLAG ESTÁ ACTIVO ---
if args.only_new:
    print("🚩 Flag '--only-new' detectado. Filtrando solo fondos sin CSV...")
    data_dir = Path("fondos_data")
    
    # Creamos una nueva lista solo con los ISINs que no tienen un fichero CSV
    isins_filtrados = [
        isin for isin in isins_a_procesar 
        if not (data_dir / f"{isin}.csv").exists()
    ]
    
    print(f"  -> {len(isins_filtrados)} de {len(isins_a_procesar)} fondos serán procesados por primera vez.")
    isins_a_procesar = isins_filtrados # Reemplazamos la lista original por la filtrada

# --- 4. PROCESAR CADA ISIN DE LA LISTA ---
if not isins_a_procesar:
    print("No hay fondos que procesar.")
else:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for i, isin in enumerate(isins_a_procesar):
            print(f"\nProcesando {i+1}/{len(isins_a_procesar)}: {isin}...")
            
            # --- LLAMADA MODIFICADA ---
            api_call_made = update_fund_in_db(page, isin)
            
            if api_call_made and i < len(isins_a_procesar) - 1:
                pausa = random.uniform(5, 10)
                print(f"  -> Esperando {pausa:.0f} segundos...")
                time.sleep(pausa)

        browser.close()

print("\n--- Worker finalizado ---")