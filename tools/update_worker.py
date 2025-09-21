import sys
import os
# Añadimos el directorio raíz del proyecto al path de Python
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
import random
import argparse # <-- NUEVA IMPORTACIÓN
from pathlib import Path # <-- NUEVA IMPORTACIÓN
from src.fund_operations import update_fund_csv

# --- 1. CONFIGURAR EL PARSER DE ARGUMENTOS ---
parser = argparse.ArgumentParser(description="Worker para actualizar los datos de fondos de inversión.")
parser.add_argument(
    '--only-new',
    action='store_true',  # Esto convierte el argumento en una bandera (flag)
    help="Si se especifica, solo procesará los fondos que no tengan un fichero CSV existente."
)
args = parser.parse_args()

print("--- Iniciando worker de actualización de fondos (CSV) ---")

# --- 2. CARGAR LA LISTA DE ISINs ---
try:
    with open('fondos.json') as file:
        fondos_data = json.load(file)
    isins_a_procesar = [fondo['isin'] for fondo in fondos_data.get('fondos', [])]
    print(f"✅ Se encontraron {len(isins_a_procesar)} ISINs totales en 'fondos.json'.")
except Exception as e:
    print(f"❌ Error: No se pudo cargar 'fondos.json'. Abortando. Detalle: {e}")
    exit()

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

# --- 4. PROCESAR CADA ISIN DE LA LISTA (filtrada o no) ---
fondos_procesados = 0
for i, isin in enumerate(isins_a_procesar):
    print(f"\nProcesando {i+1}/{len(isins_a_procesar)}: {isin}...")
    
    api_call_made = update_fund_csv(isin)
    fondos_procesados += 1
    
    if api_call_made and i < len(isins_a_procesar) - 1:
        pausa = random.uniform(5, 10)
        print(f"  -> Esperando {pausa:.0f} segundos antes del siguiente fondo...")
        time.sleep(pausa)

# --- 5. RESUMEN FINAL ---
print("\n--- Worker finalizado ---")
print(f"Resumen:")
print(f"  - Fondos procesados en esta ejecución: {fondos_procesados}")