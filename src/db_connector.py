# src/db_connector.py

import psycopg2
import yaml
from psycopg2.extras import execute_values

def get_db_connection():
    """
    Establece y devuelve una conexión a la base de datos PostgreSQL.
    """
    try:
        with open('config.yaml') as file:
            config = yaml.safe_load(file)
        db_config = config['postgres']
        conn = psycopg2.connect(**db_config)
        return conn
    except Exception as e:
        print(f"❌ Error al conectar a PostgreSQL: {e}")
        return None