import os
import sys
import json
import time
import random
import argparse
from pathlib import Path
import pandas as pd

# Añadimos el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importamos las funciones de lógica
from src.fund_operations import update_fund_csv
from src.metrics import calcular_metricas_desde_rentabilidades
from src.data_manager import filtrar_por_horizonte

def calculate_and_save_metrics(isin: str, config_file: str = "fondos.json"):
    """
    Lee el CSV de un fondo, calcula las métricas para diferentes horizontes
    y las guarda en el fichero de configuración JSON.
    """
    csv_path = Path("fondos_data") / f"{isin}.csv"
    if not csv_path.exists():
        return

    try:
        # Cargar datos históricos
        nav_df = pd.read_csv(csv_path, parse_dates=["date"], index_col="date")
        if nav_df.empty:
            return
            
        horizontes = ["YTD", "1y", "3y", "5y"]
        metrics_to_save = {}

        # Calcular métricas para cada horizonte
        for h in horizontes:
            filtered_navs = filtrar_por_horizonte(nav_df.copy(), h)
            daily_returns = filtered_navs['nav'].pct_change().dropna()
            
            if not daily_returns.empty and len(daily_returns) > 2:
                metrics = calcular_metricas_desde_rentabilidades(daily_returns)
                metrics_to_save[h] = {
                    "return": metrics.get("annualized_return_%") if h not in ["YTD"] else metrics.get("cumulative_return_%"),
                    "sharpe": metrics.get("sharpe_ann"),
                    "sortino": metrics.get("sortino_ann")
                }

        # Guardar las métricas en el fichero JSON
        with open(config_file, 'r+', encoding='utf-8') as f:
            data = json.load(f)
            fondos = data.get("fondos", [])
            
            for fondo in fondos:
                if fondo.get("isin") == isin:
                    fondo["metrics"] = metrics_to_save
                    break
            
            f.seek(0)
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.truncate()
        
        print(f"  -> ✅ Métricas pre-calculadas y guardadas para {isin}.")

    except Exception as e:
        print(f"  -> ❌ Error calculando o guardando métricas para {isin}: {e}")


# --- Flujo Principal del Worker ---
parser = argparse.ArgumentParser(description="Worker para actualizar los datos y métricas de fondos.")
parser.add_argument('--only-new', action='store_true', help="Solo procesa fondos sin CSV.")
args = parser.parse_args()

print("--- Iniciando worker de actualización de fondos y métricas ---")

try:
    with open('fondos.json') as file:
        fondos_data = json.load(file)
    isins_a_procesar = [fondo['isin'] for fondo in fondos_data.get('fondos', [])]
    print(f"✅ Se encontraron {len(isins_a_procesar)} ISINs en 'fondos.json'.")
except Exception as e:
    print(f"❌ Error al cargar 'fondos.json': {e}"); exit()

if args.only_new:
    # (Lógica del flag --only-new no cambia)
    # ...

for i, isin in enumerate(isins_a_procesar):
    print(f"\nProcesando {i+1}/{len(isins_a_procesar)}: {isin}...")
    
    # 1. Actualizar el fichero CSV
    api_call_made = update_fund_csv(isin)
    
    # 2. Calcular y guardar las métricas en fondos.json
    calculate_and_save_metrics(isin)
    
    if api_call_made and i < len(isins_a_procesar) - 1:
        pausa = random.uniform(5, 10)
        print(f"  -> Esperando {pausa:.0f} segundos...")
        time.sleep(pausa)

print("\n--- Worker finalizado ---")