# tools/metrics_worker.py

import sys
import os
import pandas as pd
import numpy as np # <-- Importamos numpy para el manejo de tipos

# Añadimos el directorio raíz al path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db_connector import get_db_connection
from src.metrics import calcular_metricas_desde_rentabilidades
from src.data_manager import filtrar_por_horizonte
from src.config import HORIZONTE_OPCIONES
from psycopg2.extras import execute_values

print("--- Iniciando Worker de Cálculo de Métricas ---")

# --- 1. CONECTAR A LA BASE DE DATOS Y OBTENER DATOS ---
conn = get_db_connection()
if not conn:
    exit()

try:
    print("Leyendo catálogo de fondos y precios históricos...")
    funds_df = pd.read_sql("SELECT isin FROM funds", conn)
    prices_df = pd.read_sql("SELECT isin, date, nav FROM historical_prices", conn, index_col='date', parse_dates=['date'])
    
    if funds_df.empty or prices_df.empty:
        print("No hay fondos o precios para calcular métricas. Finalizando.")
        exit()

    print(f"✅ Se procesarán métricas para {len(funds_df)} fondos.")

except Exception as e:
    print(f"❌ Error al leer datos de la base de datos: {e}")
    exit()
finally:
    if conn:
        conn.close()

# --- 2. CALCULAR MÉTRICAS ---
all_metrics_to_insert = []
for isin in funds_df['isin']:
    fund_prices = prices_df[prices_df['isin'] == isin]['nav']
    if fund_prices.empty or len(fund_prices) < 2:
        continue

    fund_prices_df = pd.DataFrame(fund_prices)

    # --- Remuestrear a diario para consistencia con el comparador ---
    daily_index = pd.date_range(start=fund_prices_df.index.min(), end=fund_prices_df.index.max(), freq='D')
    resampled_prices = fund_prices_df.reindex(daily_index).ffill()

    for horizonte in HORIZONTE_OPCIONES:
        # 1. Filtrar los precios REMUESTREADOS por el horizonte temporal
        filtered_prices = filtrar_por_horizonte(resampled_prices, horizonte)['nav']
        if len(filtered_prices) < 2:
            continue

        # 2. Calcular los retornos sobre los precios ya filtrados y remuestreados
        filtered_returns = filtered_prices.pct_change().dropna()

        metrics = calcular_metricas_desde_rentabilidades(filtered_returns)

        
        all_metrics_to_insert.append((
            isin,
            horizonte,
            metrics.get('annualized_return_%'),
            metrics.get('cumulative_return_%'),
            metrics.get('volatility_ann_%'),
            metrics.get('sharpe_ann'),
            metrics.get('sortino_ann'),
            metrics.get('max_drawdown_%')
        ))

print(f"Se han calculado un total de {len(all_metrics_to_insert)} conjuntos de métricas.")

# --- 3. LIMPIAR E INSERTAR MÉTRICAS ---
if all_metrics_to_insert:
    
    # --- SOLUCIÓN CLAVE: LIMPIEZA DE DATOS ---
    # Convertimos los tipos de numpy a tipos nativos de Python que la BD entiende.
    cleaned_metrics = []
    for metric_tuple in all_metrics_to_insert:
        cleaned_tuple = tuple(
            # Si es un número de numpy, lo convierte a float de Python.
            # Si es NaN, lo convierte a None (que en SQL es NULL).
            float(val) if pd.notna(val) else None
            for val in metric_tuple[2:] # Solo aplicamos a las columnas numéricas
        )
        # Reconstruimos la tupla con el isin y el horizonte
        cleaned_metrics.append( (metric_tuple[0], metric_tuple[1]) + cleaned_tuple )
    
    conn = get_db_connection()
    if not conn:
        exit()
    try:
        with conn.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO fund_metrics (isin, horizon, annualized_return_pct, cumulative_return_pct, volatility_pct, sharpe_ratio, sortino_ratio, max_drawdown_pct)
                VALUES %s
                ON CONFLICT (isin, horizon) DO UPDATE SET
                    annualized_return_pct = EXCLUDED.annualized_return_pct,
                    cumulative_return_pct = EXCLUDED.cumulative_return_pct,
                    volatility_pct = EXCLUDED.volatility_pct,
                    sharpe_ratio = EXCLUDED.sharpe_ratio,
                    sortino_ratio = EXCLUDED.sortino_ratio,
                    max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    last_calculated = NOW();
                """,
                cleaned_metrics # <-- Usamos la lista de datos limpios
            )
            conn.commit()
            print(f"✅ ¡Éxito! Se han guardado {cursor.rowcount} registros de métricas en la base de datos.")
    except Exception as e:
        print(f"❌ Error al guardar las métricas en la base de datos: {e}")
    finally:
        if conn:
            conn.close()

print("\n--- Worker de Métricas finalizado ---")