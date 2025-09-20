# update_worker.py

import json
# --- NUEVA IMPORTACIÓN ---
from src.fund_operations import update_fund_csv

print("--- Iniciando worker de actualización de fondos (CSV) ---")

# 1. Cargar la lista de ISINs desde fondos.json
try:
    with open('fondos.json') as file:
        fondos_data = json.load(file)
    isins_a_procesar = [fondo['isin'] for fondo in fondos_data.get('fondos', [])]
    print(f"✅ Se encontraron {len(isins_a_procesar)} ISINs en 'fondos.json'.")
except Exception as e:
    print(f"❌ Error: No se pudo cargar 'fondos.json'. Abortando. Detalle: {e}")
    exit()

fondos_actualizados = 0
fondos_con_error = 0

# 2. Procesar cada ISIN de la lista
for isin in isins_a_procesar:
    print(f"\nProcesando {isin}...")
    # Llamamos a nuestra nueva función, que hace todo el trabajo
    success = update_fund_csv(isin)
    
    if success:
        print(f"  -> ✅ Proceso para {isin} finalizado.")
        fondos_actualizados += 1
    else:
        print(f"  -> ❌ Error procesando el ISIN {isin}.")
        fondos_con_error += 1

# --- 3. Resumen final ---
print("\n--- Worker finalizado ---")
print(f"Resumen:")
print(f"  - Fondos procesados: {fondos_actualizados}")
print(f"  - Fondos con error durante el proceso: {fondos_con_error}")