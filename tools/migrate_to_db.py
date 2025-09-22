# tools/migrate_to_db.py

import sys
import os
import json
import pandas as pd

# Añadimos el directorio raíz al path para poder importar desde 'src'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.db_connector import get_db_connection
from psycopg2.extras import execute_values

print("--- Iniciando migración de fondos.json a PostgreSQL ---")

# 1. Cargar datos del JSON
try:
    with open('fondos.json') as file:
        fondos_data = json.load(file).get('fondos', [])
    print(f"✅ Se encontraron {len(fondos_data)} fondos en 'fondos.json'.")
except Exception as e:
    print(f"❌ Error al cargar 'fondos.json': {e}"); exit()

# 2. Conectar a la BD
conn = get_db_connection()
if not conn:
    exit()

# 3. Preparar los datos para la inserción
data_to_insert = []
for fondo in fondos_data:
    # Aseguramos que los campos numéricos sean válidos o None
    ter = pd.to_numeric(fondo.get('ter'), errors='coerce')
    ter = None if pd.isna(ter) else ter
    srri = pd.to_numeric(fondo.get('srri'), errors='coerce')
    srri = None if pd.isna(srri) else srri

    data_to_insert.append((
        fondo.get('isin'),
        fondo.get('performanceID'),
        fondo.get('securityID'),
        fondo.get('nombre'),
        fondo.get('nombre_legal'),
        ter,
        fondo.get('morningstarCategory'),
        fondo.get('gestora'),
        fondo.get('domicilio'),
        srri
    ))

# 4. Insertar los datos en la tabla 'funds'
try:
    with conn.cursor() as cursor:
        execute_values(
            cursor,
            """
            INSERT INTO funds (isin, performance_id, security_id, name, nombre_legal, ter, morningstar_category, gestora, domicilio, srri)
            VALUES %s
            ON CONFLICT (isin) DO UPDATE SET
                performance_id = EXCLUDED.performance_id,
                security_id = EXCLUDED.security_id,
                name = EXCLUDED.name,
                nombre_legal = EXCLUDED.nombre_legal,
                ter = EXCLUDED.ter,
                morningstar_category = EXCLUDED.morningstar_category,
                gestora = EXCLUDED.gestora,
                domicilio = EXCLUDED.domicilio,
                srri = EXCLUDED.srri,
                last_updated_metadata = NOW();
            """,
            data_to_insert
        )
        conn.commit()
        print(f"✅ ¡Migración completada! {cursor.rowcount} filas afectadas.")
except Exception as e:
    print(f"❌ Error durante la inserción en la base de datos: {e}")
finally:
    if conn:
        conn.close()