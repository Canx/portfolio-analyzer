# tools/catalog_manager.py

import sys
import os
import json
import argparse
from playwright.sync_api import sync_playwright
import pandas as pd
import time
import random

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.catalog_operations import scrape_fund_data
from src.db_connector import get_db_connection
from psycopg2.extras import execute_values

# --- Lógica de Base de Datos ---
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
    with conn.cursor() as cursor:
        # 1. Insertar o actualizar los metadatos en la tabla 'funds'
        cursor.execute(
            """
            INSERT INTO funds (isin, performance_id, name)
            VALUES (%s, %s, %s)
            ON CONFLICT (isin) DO UPDATE SET
                performance_id = EXCLUDED.performance_id,
                name = EXCLUDED.name,
                last_updated_metadata = NOW();
            """,
            (metadata['isin'], metadata['performance_id'], metadata['name'])
        )
        # 2. Insertar los precios históricos
        data_to_insert = [(metadata['isin'], row['date'].date(), row['nav']) for _, row in prices_df.iterrows()]
        execute_values(
            cursor,
            "INSERT INTO historical_prices (isin, date, nav) VALUES %s ON CONFLICT (isin, date) DO NOTHING",
            data_to_insert
        )
        conn.commit()
        print(f"  -> ✅ Datos de {metadata['isin']} guardados en la base de datos.")

# --- Lógica Principal del Worker ---
def main():
    parser = argparse.ArgumentParser(description="Worker maestro para gestionar el catálogo de fondos.")
    parser.add_argument('--source-json', type=str, help="Ruta a un fichero JSON con una lista de ISINs para añadir/actualizar.")
    parser.add_argument('--process-requests', action='store_true', help="Procesa las peticiones pendientes de la tabla asset_requests.")
    parser.add_argument('--update-existing', action='store_true', help="Refresca los datos de todos los fondos existentes en el catálogo.")
    args = parser.parse_args()

    conn = get_db_connection()
    if not conn: exit()

    isins_to_process = []
    request_map = {} # Para mapear ISIN a ID de petición

    if args.source_json:
        print(f"Cargando ISINs desde {args.source_json}...")
        with open(args.source_json) as f:
            isins_to_process = json.load(f)
    elif args.process_requests:
        print("Buscando peticiones de fondos pendientes...")
        requests = get_pending_requests(conn)
        for req in requests:
            isins_to_process.append(req['isin'])
            request_map[req['isin']] = req['id']
    elif args.update_existing:
        print("Buscando todos los fondos existentes para actualizar...")
        isins_to_process = get_existing_funds(conn)
    else:
        print("No se especificó ninguna tarea. Usa --help para ver las opciones.")
        exit()
    
    conn.close()

    if not isins_to_process:
        print("No hay fondos que procesar. Finalizando.")
        exit()

    print(f"Se procesarán {len(isins_to_process)} ISINs.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        # --- LÍNEA CORREGIDA ---
        # Llamamos a new_page() desde el objeto 'browser', no desde 'p'
        page = browser.new_page()

        for isin in isins_to_process:
            print(f"\n--- Procesando {isin} ---")
            fund_data = scrape_fund_data(page, isin)
            
            conn = get_db_connection()
            if conn and fund_data:
                save_fund_data(conn, fund_data['metadata'], fund_data['prices'])
                if isin in request_map:
                    update_request_status(conn, request_map[isin], 'processed')
            elif isin in request_map:
                update_request_status(conn, request_map[isin], 'failed')
            
            if conn: conn.close()
            pausa = random.uniform(5, 10)
            print(f"  -> Esperando {pausa:.0f} segundos...")
            time.sleep(pausa)

        browser.close()

    print("\n--- Worker finalizado ---")

if __name__ == "__main__":
    main()