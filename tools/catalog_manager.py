# tools/catalog_manager.py

import sys
import os
import json
import argparse
from datetime import datetime, date, timedelta, timezone
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random

# --- NUEVAS IMPORTACIONES ---
# Añadimos las herramientas necesarias para el cálculo de métricas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.catalog_operations import scrape_fund_data
from src.db_connector import get_db_connection
from psycopg2.extras import execute_values
from src.metrics import calcular_metricas_desde_rentabilidades
from src.data_manager import filtrar_por_horizonte
from src.config import HORIZONTE_OPCIONES

METADATA_REFRESH_DAYS = int(os.getenv("CATALOG_METADATA_REFRESH_DAYS", "7"))
PRICE_REFRESH_DAYS = int(os.getenv("CATALOG_PRICE_REFRESH_DAYS", "2"))

# --- Lógica de Base de Datos (las 3 primeras funciones no cambian) ---
def get_pending_requests(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, isin FROM asset_requests WHERE status = 'pending'")
        return [{"id": row[0], "isin": row[1]} for row in cursor.fetchall()]

def get_existing_funds(conn):
    with conn.cursor() as cursor:
        cursor.execute("SELECT isin FROM funds")
        return [row[0] for row in cursor.fetchall()]

def update_request_status(conn, request_id, status):
    with conn.cursor() as cursor:
        cursor.execute("UPDATE asset_requests SET status = %s, processed_at = NOW() WHERE id = %s", (status, request_id))
        conn.commit()

def save_fund_data(conn, metadata, prices_df):
    print("  -> Intentando guardar los siguientes metadatos:")
    print(f"     ISIN: {metadata.get('isin')}, TER: {metadata.get('ter')}, Gestora: {metadata.get('gestora')}, SRRI: {metadata.get('srri')}")
    try:
        with conn.cursor() as cursor:
            # CORREGIDO: La sentencia SQL ahora coincide con la tabla optimizada
            sql_query = """
                INSERT INTO funds (isin, performance_id, security_id, name, ter, morningstar_category, gestora, domicilio, srri, currency)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (isin) DO UPDATE SET
                    performance_id = EXCLUDED.performance_id,
                    security_id = EXCLUDED.security_id,
                    name = EXCLUDED.name,
                    ter = EXCLUDED.ter,
                    morningstar_category = EXCLUDED.morningstar_category,
                    gestora = EXCLUDED.gestora,
                    domicilio = EXCLUDED.domicilio,
                    srri = EXCLUDED.srri,
                    currency = EXCLUDED.currency, 
                    last_updated_metadata = NOW();
            """
            # CORREGIDO: La tupla de datos ahora coincide con la sentencia SQL
            data_tuple = (
                metadata.get('isin'),
                metadata.get('performance_id'),
                metadata.get('security_id'),
                metadata.get('name'),
                metadata.get('ter'),
                metadata.get('morningstar_category'),
                metadata.get('gestora'),
                metadata.get('domicilio'),
                metadata.get('srri'),
                metadata.get('currency')
            )
            cursor.execute(sql_query, data_tuple)
            if prices_df is not None and not prices_df.empty:
                data_to_insert = [(metadata['isin'], row['date'].date(), row['nav']) for _, row in prices_df.iterrows()]
                execute_values(cursor, "INSERT INTO historical_prices (isin, date, nav) VALUES %s ON CONFLICT (isin, date) DO NOTHING", data_to_insert)
            conn.commit()
            print(f"  -> ✅ Metadatos y precios de {metadata['isin']} guardados en la base de datos.")
    except Exception as e:
        print(f"  -> ❌ ERROR DE BASE DE DATOS al guardar metadatos/precios: {e}")
        conn.rollback()


def _normalize_datetime(value):
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, datetime.min.time())
    else:
        return None

    if result.tzinfo is not None:
        result = result.astimezone(timezone.utc).replace(tzinfo=None)
    return result


def should_skip_fund(conn, isin: str) -> tuple[bool, str]:
    metadata_ts = None
    last_price_date = None

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT last_updated_metadata FROM funds WHERE isin = %s", (isin,))
            metadata_row = cursor.fetchone()
            if metadata_row:
                metadata_ts = metadata_row[0]

            cursor.execute("SELECT MAX(date) FROM historical_prices WHERE isin = %s", (isin,))
            price_row = cursor.fetchone()
            if price_row:
                last_price_date = price_row[0]
    except Exception as e:
        conn.rollback()
        return False, f"  -> ⚠️ No se pudo comprobar el estado previo de {isin}: {e}."

    now_utc = datetime.utcnow()
    today = date.today()

    metadata_recent = False
    if metadata_ts:
        normalized = _normalize_datetime(metadata_ts)
        if normalized:
            metadata_recent = (now_utc - normalized) <= timedelta(days=METADATA_REFRESH_DAYS)

    price_recent = False
    if last_price_date:
        if isinstance(last_price_date, datetime):
            last_price_as_date = last_price_date.date()
        else:
            last_price_as_date = last_price_date
        price_recent = (today - last_price_as_date) <= timedelta(days=PRICE_REFRESH_DAYS)

    if metadata_recent and price_recent:
        meta_text = metadata_ts.strftime('%Y-%m-%d %H:%M') if isinstance(metadata_ts, datetime) else str(metadata_ts)
        price_text = last_price_as_date.strftime('%Y-%m-%d') if isinstance(last_price_as_date, date) else str(last_price_as_date)
        return True, f"  -> Datos recientes para {isin} (metadata {meta_text}, último precio {price_text}). Saltando descarga."

    reasons = []
    if not metadata_recent:
        if metadata_ts:
            meta_text = metadata_ts.strftime('%Y-%m-%d %H:%M') if isinstance(metadata_ts, datetime) else str(metadata_ts)
            reasons.append(f"metadata desactualizada ({meta_text})")
        else:
            reasons.append("sin metadata previa")
    if not price_recent:
        if last_price_date:
            price_text = last_price_as_date.strftime('%Y-%m-%d') if isinstance(last_price_as_date, date) else str(last_price_as_date)
            reasons.append(f"último precio {price_text}")
        else:
            reasons.append("sin precios previos")

    reason_text = "; ".join(reasons)
    return False, f"  -> Se actualizará {isin} porque {reason_text}."

# --- NUEVA FUNCIÓN ---
def calculate_and_save_metrics(conn, isin: str, prices_df: pd.DataFrame):
    """
    Calcula las métricas para todos los horizontes y las guarda en la tabla 'fund_metrics'.
    """
    if prices_df is None or prices_df.empty or len(prices_df) < 2:
        print("  -> No hay suficientes datos de precios para calcular métricas.")
        return

    print("  -> Calculando métricas para los diferentes horizontes...")
    
    # Preparamos los datos para el cálculo
    # Hacemos una copia para no modificar el DataFrame original
    prices_df_copy = prices_df.copy()
    prices_df_copy.set_index('date', inplace=True)
    daily_returns = prices_df_copy['nav'].pct_change().dropna()
    
    metrics_to_insert = []
    for horizonte in HORIZONTE_OPCIONES:
        filtered_returns = filtrar_por_horizonte(pd.DataFrame(daily_returns), horizonte)['nav']
        if len(filtered_returns) < 2: continue

        metrics = calcular_metricas_desde_rentabilidades(filtered_returns)
        metrics_to_insert.append((
            isin, horizonte,
            metrics.get('annualized_return_%'), metrics.get('cumulative_return_%'),
            metrics.get('volatility_ann_%'), metrics.get('sharpe_ann'),
            metrics.get('sortino_ann'), metrics.get('max_drawdown_%')
        ))

    # Limpiamos los datos para la BBDD (convierte NaN a None, etc.)
    cleaned_metrics = []
    for m in metrics_to_insert:
        cleaned_tuple = tuple(float(v) if pd.notna(v) else None for v in m[2:])
        cleaned_metrics.append((m[0], m[1]) + cleaned_tuple)

    if not cleaned_metrics:
        print("  -> No se generaron métricas para guardar.")
        return

    try:
        with conn.cursor() as cursor:
            execute_values(
                cursor,
                """
                INSERT INTO fund_metrics (isin, horizon, annualized_return_pct, cumulative_return_pct, volatility_pct, sharpe_ratio, sortino_ratio, max_drawdown_pct)
                VALUES %s
                ON CONFLICT (isin, horizon) DO UPDATE SET
                    annualized_return_pct = EXCLUDED.annualized_return_pct, cumulative_return_pct = EXCLUDED.cumulative_return_pct,
                    volatility_pct = EXCLUDED.volatility_pct, sharpe_ratio = EXcluded.sharpe_ratio,
                    sortino_ratio = EXCLUDED.sortino_ratio, max_drawdown_pct = EXCLUDED.max_drawdown_pct,
                    last_calculated = NOW();
                """,
                cleaned_metrics
            )
            conn.commit()
            print(f"  -> ✅ {cursor.rowcount} registros de métricas guardados en la base de datos.")
    except Exception as e:
        print(f"  -> ❌ ERROR DE BASE DE DATOS al guardar métricas: {e}")
        conn.rollback()

# --- Lógica Principal del Worker (MODIFICADA) ---
def main():
    parser = argparse.ArgumentParser(description="Worker maestro para gestionar el catálogo de fondos.")
    parser.add_argument('--source-json', type=str, help="Ruta a un fichero JSON con una lista de ISINs para añadir/actualizar.")
    parser.add_argument('--process-requests', action='store_true', help="Procesa las peticiones pendientes de la tabla asset_requests.")
    parser.add_argument('--update-existing', action='store_true', help="Refresca los datos de todos los fondos existentes en el catálogo.")
    # NUEVO ARGUMENTO
    parser.add_argument('--update-isin', type=str, help="Actualiza los datos de un único fondo especificado por su ISIN.")
    args = parser.parse_args()

    isins_to_process = []
    request_map = {}
    
    # LÓGICA DE CARGA DE ISINs MODIFICADA
    if args.update_isin:
        print(f"Se procesará un único ISIN: {args.update_isin}")
        isins_to_process = [args.update_isin]
    elif args.source_json:
        print(f"Cargando ISINs desde {args.source_json}...")
        with open(args.source_json) as f:
            isins_to_process = json.load(f)
    elif args.process_requests:
        print("Buscando peticiones de fondos pendientes...")
        conn = get_db_connection()
        if not conn: exit()
        requests = get_pending_requests(conn)
        for req in requests:
            isins_to_process.append(req['isin'])
            request_map[req['isin']] = req['id']
        conn.close()
    elif args.update_existing:
        print("Buscando todos los fondos existentes para actualizar...")
        conn = get_db_connection()
        if not conn: exit()
        isins_to_process = get_existing_funds(conn)
        conn.close()
    else:
        print("No se especificó ninguna tarea. Usa --help para ver las opciones.")
        exit()

    if not isins_to_process:
        print("No hay fondos que procesar. Finalizando.")
        exit()

    print(f"Se encontraron {len(isins_to_process)} ISINs para analizar.")

    filtered_isins = []
    for isin in isins_to_process:
        conn = get_db_connection()
        if not conn:
            print(f"  -> ⚠️ No se pudo conectar a la base de datos para verificar {isin}. Se procederá con el scraping.")
            filtered_isins.append(isin)
            continue

        skip, message = should_skip_fund(conn, isin)
        print(message)

        if skip:
            if isin in request_map:
                update_request_status(conn, request_map[isin], 'processed')
        else:
            filtered_isins.append(isin)

        conn.close()

    isins_to_process = filtered_isins

    if not isins_to_process:
        print("Todos los fondos están actualizados. No se realizará scraping adicional.")
        return

    print(f"Se procesarán {len(isins_to_process)} ISINs tras filtrar los que ya estaban al día.")


    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for isin in isins_to_process:
            print(f"\n--- Procesando {isin} ---")
            fund_data = scrape_fund_data(page, isin)

            conn = get_db_connection()
            if conn and fund_data:
                # 1. Guardar metadatos y precios
                save_fund_data(conn, fund_data['metadata'], fund_data['prices'])

                # 2. CALCULAR Y GUARDAR MÉTRICAS (NUEVO PASO)
                calculate_and_save_metrics(conn, isin, fund_data['prices'])

                # 3. Actualizar estado de la petición (si aplica)
                if isin in request_map:
                    update_request_status(conn, request_map[isin], 'processed')

            elif isin in request_map and conn:
                update_request_status(conn, request_map[isin], 'failed')

            if conn: conn.close()

            if len(isins_to_process) > 1:
                pausa = random.uniform(5, 10)
                print(f"  -> Esperando {pausa:.0f} segundos...")
                time.sleep(pausa)

        browser.close()

    print("\n--- Worker finalizado ---")

if __name__ == "__main__":
    main()
