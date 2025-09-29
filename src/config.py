# src/config.py
"""
Fichero central para guardar constantes y configuraciones de la aplicación.
"""
import os

# --- Configuración de Stripe ---
# Carga las claves desde variables de entorno para mayor seguridad
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "pk_test_..._reemplazar_esta_clave")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_..._reemplazar_esta_clave")
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID", "price_..._reemplazar_este_id") # ID del producto de precio para la suscripción
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_..._reemplazar_este_secreto")

# --- Configuración de la Aplicación ---

# Definimos la lista de opciones para el horizonte temporal
HORIZONTE_OPCIONES = ["1m", "3m", "6m", "YTD", "1y", "2y", "3y", "5y", "max"]

# Definimos el índice del valor por defecto ("YTD") para no tener que calcularlo en cada página
try:
    HORIZONTE_DEFAULT_INDEX = HORIZONTE_OPCIONES.index("YTD")
except ValueError:
    HORIZONTE_DEFAULT_INDEX = 3 # Fallback por si 'YTD' no estuviera
