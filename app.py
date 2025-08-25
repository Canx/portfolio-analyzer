# app.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from streamlit_local_storage import LocalStorage

# Importaciones de los nuevos módulos
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import hrp_allocation
from src.portfolio import Portfolio
from src.ui_components import render_sidebar, render_main_content, render_update_panel

# ==============================
#   CONFIGURACIÓN Y ESTADO
# ==============================
st.set_page_config(page_title="📊 Analizador de Fondos", layout="wide")
st.title("📊 Analizador de Fondos de Inversión")

@st.cache_data
def load_config(config_file="fondos.json"):
    """Carga la configuración de fondos desde un JSON."""
    path = Path(config_file)
    if not path.exists():
        st.error(f"Fichero de configuración '{config_file}' no encontrado.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])

@st.cache_data
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    """Función centralizada y cacheada para cargar todos los datos NAV."""
    with st.spinner(f"Cargando datos de {len(isines)} fondos..."):
        all_navs = {}
        for isin in isines:
            force = (isin == force_update_isin)
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None and 'nav' in df.columns:
                all_navs[isin] = df['nav']
    if not all_navs: return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()

# En app.py, reemplaza las funciones originales con estas:

def initialize_session_state(todos_isines, localS):
    """Inicializa el estado de la sesión leyendo de LocalStorage o con valores por defecto."""
    if 'initialized' not in st.session_state:
        # --- Listado ---
        json_listado = localS.getItem('mi_listado')
        listado_guardado = [] # Default
        if json_listado:
            try:
                listado_guardado = json.loads(json_listado)
            except json.JSONDecodeError:
                st.warning("Formato de listado guardado incorrecto.")
        st.session_state.listado_isines = listado_guardado or todos_isines[:5]

        # --- Cartera ---
        json_cartera = localS.getItem('mi_cartera')
        cartera_guardada = {} # Default
        if json_cartera:
            try:
                # ESTA ES LA LÍNEA CLAVE QUE FALTABA
                cartera_guardada = json.loads(json_cartera)
            except json.JSONDecodeError:
                st.warning("Formato de cartera guardada incorrecto.")

        st.session_state.cartera_isines = cartera_guardada.get('fondos', [])
        st.session_state.pesos = cartera_guardada.get('pesos', {})
        
        st.session_state.initialized = True


# En app.py, reemplaza la función save_state_to_browser
def save_state_to_browser(localS):
    """Guarda el estado actual convirtiéndolo explícitamente a JSON antes."""
    # Guardar listado con su propia clave única
    localS.setItem('mi_listado', json.dumps(st.session_state.listado_isines), key="storage_listado")
    
    # Guardar cartera
    cartera_a_guardar = {
        "fondos": st.session_state.cartera_isines,
        "pesos": st.session_state.pesos
    }
    # Guardar cartera con OTRA clave única
    localS.setItem('mi_cartera', json.dumps(cartera_a_guardar), key="storage_cartera")


# ==============================
#   FLUJO PRINCIPAL DE LA APP
# ==============================

# 1. CARGAR CONFIGURACIÓN Y MAPAS
fondos_config = load_config()
if not fondos_config: st.stop()

todos_isines = [f['isin'] for f in fondos_config]
mapa_isin_nombre = {f['isin']: f['nombre'] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f['isin'] for f in fondos_config}

# 2. INICIALIZAR ESTADO, UI Y OBJETOS
localS = LocalStorage()
initialize_session_state(todos_isines, localS)
data_manager = DataManager()
horizonte, opciones_graficos, run_hrp_opt = render_sidebar(mapa_nombre_isin, mapa_isin_nombre)

# 3. GUARDAR ESTADO ANTES DE POSIBLES RE-RUNS
save_state_to_browser(localS)

# 4. CARGA DE DATOS CENTRALIZADA
isines_a_cargar = tuple(sorted(set(st.session_state.listado_isines + st.session_state.cartera_isines)))
force_update_isin = st.session_state.pop('force_update_isin', None) # Coge y elimina la variable para que no se repita
all_navs_df = load_all_navs(data_manager, isines_a_cargar, force_update_isin=force_update_isin)

if all_navs_df.empty:
    st.warning("No se pudieron cargar datos para los fondos seleccionados.")
    st.stop()

# 5. FILTRADO Y PROCESADO
filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns_listado = filtered_navs.pct_change().dropna()[st.session_state.listado_isines]

# 6. LÓGICA DE OPTIMIZACIÓN
if run_hrp_opt:
    if st.session_state.cartera_isines:
        returns_cartera = filtered_navs.pct_change().dropna()[st.session_state.cartera_isines]
        if not returns_cartera.empty and len(returns_cartera) > 1:
            pesos_opt = hrp_allocation(returns_cartera.cov(), returns_cartera.corr())
            pesos_opt_dict = {isin: int(round(p * 100)) for isin, p in pesos_opt.items()}
            # Ajuste final para que sume 100
            resto = 100 - sum(pesos_opt_dict.values())
            if resto != 0: pesos_opt_dict[pesos_opt.idxmax()] += resto
            st.session_state.pesos = pesos_opt_dict
            st.success("Cartera optimizada con HRP ✅")
            st.rerun()
        else:
            st.warning("No hay suficientes datos para optimizar en este horizonte.")
    else:
        st.warning("Añade fondos a tu cartera para poder optimizarla.")

# 7. CÁLCULO DE MÉTRICAS Y CARTERA
metricas = []
for isin in st.session_state.listado_isines:
    if isin in daily_returns_listado.columns:
        m = calcular_metricas_desde_rentabilidades(daily_returns_listado[isin])
        m["isin"] = isin; m["nombre"] = mapa_isin_nombre.get(isin, isin)
        metricas.append(m)

df_metrics = pd.DataFrame(metricas)

# Crear y calcular la cartera
portfolio = None
if st.session_state.cartera_isines:
    portfolio = Portfolio(filtered_navs, st.session_state.pesos)
    if portfolio and portfolio.nav is not None:
        metricas_cartera = portfolio.calculate_metrics()
        df_metrics = pd.concat([pd.DataFrame([metricas_cartera]), df_metrics], ignore_index=True)

# 8. RENDERIZAR RESULTADOS
render_main_content(opciones_graficos, df_metrics, filtered_navs[st.session_state.listado_isines], daily_returns_listado, portfolio, mapa_isin_nombre)
render_update_panel(isines_a_cargar, mapa_isin_nombre)