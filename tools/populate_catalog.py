import os
import sys
import json
import time
import random

# Añadimos el directorio raíz al path para poder importar desde 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_manager import find_and_add_fund_by_isin

# --- CONFIGURACIÓN ---
INPUT_FILE = "myinvestor_isins.json"  # El fichero que generó el scraper
OUTPUT_FILE = "fondos.json"           # El fichero de catálogo de la app

def populate_catalog():
    """
    Lee una lista de ISINs, busca sus metadatos usando mstarpy y
    crea un fichero de catálogo completo.
    """
    print("--- Iniciando la creación del catálogo de fondos ---")

    # 1. Cargar la lista de ISINs a procesar
    try:
        with open(INPUT_FILE, 'r') as f:
            isins_to_process = json.load(f)
        print(f"✅ Se han cargado {len(isins_to_process)} ISINs desde '{INPUT_FILE}'.")
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el fichero de entrada '{INPUT_FILE}'.")
        return
    except json.JSONDecodeError:
        print(f"❌ Error: El fichero '{INPUT_FILE}' no es un JSON válido.")
        return

    # 2. Cargar el catálogo existente para no duplicar fondos
    existing_funds = []
    existing_isins = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                existing_funds = data.get("fondos", [])
                existing_isins = {fund.get("isin") for fund in existing_funds}
                print(f"✅ Se han cargado {len(existing_isins)} fondos existentes desde '{OUTPUT_FILE}'.")
            except json.JSONDecodeError:
                print(f"⚠️ El fichero '{OUTPUT_FILE}' existente está corrupto. Se creará uno nuevo.")

    # 3. Procesar solo los ISINs que no están ya en el catálogo
    new_isins = [isin for isin in isins_to_process if isin not in existing_isins]
    if not new_isins:
        print("✅ No hay fondos nuevos que añadir. El catálogo ya está completo.")
        print("--- Proceso finalizado ---")
        return

    print(f"➡️  Se añadirán {len(new_isins)} fondos nuevos al catálogo.")
    
    # 4. Bucle para buscar metadatos y añadir al catálogo
    for i, isin in enumerate(new_isins):
        print(f"\nProcesando {i+1}/{len(new_isins)}: {isin}...")
        
        # find_and_add_fund_by_isin ya modifica 'fondos.json' directamente.
        # Lo llamamos y le pasamos el fichero de salida como objetivo.
        if find_and_add_fund_by_isin(isin, config_file=OUTPUT_FILE):
            print(f"  -> ✅ {isin} añadido con éxito.")
        else:
            print(f"  -> ❌ No se pudo encontrar o añadir {isin}.")
        
        # Pausa para ser respetuosos con la API
        time.sleep(random.uniform(5, 8))

    print("\n🎉 ¡Éxito! El fichero de catálogo ha sido actualizado.")
    print("--- Proceso finalizado ---")

if __name__ == "__main__":
    populate_catalog()