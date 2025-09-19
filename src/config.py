# src/config.py
"""
Fichero central para guardar constantes y configuraciones de la aplicación.
"""

# Definimos la lista de opciones para el horizonte temporal
HORIZONTE_OPCIONES = ["1m", "3m", "6m", "YTD", "1y", "2y", "3y", "5y", "max"]

# Definimos el índice del valor por defecto ("YTD") para no tener que calcularlo en cada página
try:
    HORIZONTE_DEFAULT_INDEX = HORIZONTE_OPCIONES.index("YTD")
except ValueError:
    HORIZONTE_DEFAULT_INDEX = 3 # Fallback por si 'YTD' no estuviera
