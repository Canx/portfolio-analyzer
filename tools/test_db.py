# test_db.py
import psycopg2
import yaml

print("Intentando conectar a la base de datos PostgreSQL...")

try:
    with open('config.yaml') as file:
        config = yaml.safe_load(file)
    db_config = config['postgres']
    
    conn = psycopg2.connect(**db_config)
    cursor = conn.cursor()
    
    print("✅ ¡Conexión exitosa!")
    
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print(f"Versión de la base de datos: {db_version[0]}")
    
    cursor.close()
    conn.close()
    print("Conexión cerrada correctamente.")

except Exception as e:
    print(f"❌ Error al conectar a la base de datos: {e}")
