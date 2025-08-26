# app.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
from streamlit_local_storage import LocalStorage

# ... (el resto de las importaciones no cambian) ...
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.optimizer import hrp_allocation
from src.portfolio import Portfolio
from src.ui_components import render_sidebar, render_main_content, render_update_panel

# ... (la función load_config no cambia) ...
# ... (la función load_all_navs no cambia) ...
# ... (la función initialize_session_state no cambia) ...
# ... (la función save_state_to_browser no cambia) ...

# --- NUEVA FUNCIÓN HELPER ---
def add_fund_to_config(new_isin, new_name):
    """Abre fondos.json, añade el nuevo fondo y lo guarda."""
    config_file = Path("fondos.json")
    if config_file.exists():
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"fondos": []}
    
    if any(f["isin"] == new_isin for f in data["fondos"]):
        st.warning(f"El ISIN {new_isin} ya existe en el catálogo.")
        return False
    
    data["fondos"].append({"isin": new_isin, "nombre": new_name})
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    st.success(f"¡Fondo '{new_name}' añadido! La app se recargará.")
    return True

# ==============================
#   FLUJO PRINCIPAL DE LA APP
# ==============================

# 1. CARGAR CONFIGURACIÓN
# ... (sin cambios)
st.set_page_config(page_title="📊 Analizador de Carteras", layout="wide")
st.title("📊 Analizador de Carteras de Fondos")

@st.cache_data
def load_config(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists(): return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])

@st.cache_data
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    with st.spinner(f"Cargando datos de {len(isines)} fondos..."):
        all_navs = {}
        for isin in isines:
            force = (isin == force_update_isin)
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None and 'nav' in df.columns:
                all_navs[isin] = df['nav']
    if not all_navs: return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()

def initialize_session_state(localS):
    """Inicializa solo el estado de la cartera."""
    if 'initialized' not in st.session_state:
        json_cartera = localS.getItem('mi_cartera')
        cartera_guardada = {}
        if json_cartera:
            try:
                cartera_guardada = json.loads(json_cartera)
            except json.JSONDecodeError:
                st.warning("Formato de cartera guardada incorrecto.")
        st.session_state.cartera_isines = cartera_guardada.get('fondos', [])
        st.session_state.pesos = cartera_guardada.get('pesos', {})
        st.session_state.initialized = True

def save_state_to_browser(localS):
    """Guarda solo el estado de la cartera."""
    cartera_a_guardar = {
        "fondos": st.session_state.cartera_isines,
        "pesos": st.session_state.pesos
    }
    localS.setItem('mi_cartera', json.dumps(cartera_a_guardar), key="storage_cartera")


fondos_config = load_config()
if not fondos_config:
    # Si no hay config, creamos uno vacío para poder añadir fondos
    Path("fondos.json").write_text('{"fondos": []}', encoding="utf-8")

mapa_isin_nombre = {f['isin']: f['nombre'] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f['isin'] for f in fondos_config}

# 2. INICIALIZAR ESTADO Y UI
localS = LocalStorage()
initialize_session_state(localS)
data_manager = DataManager()

# --- LÍNEA MODIFICADA ---
horizonte, run_hrp_opt, new_fund_details = render_sidebar(mapa_nombre_isin, mapa_isin_nombre)
save_state_to_browser(localS)

# --- NUEVO BLOQUE DE LÓGICA ---
# Si la sidebar nos ha devuelto un fondo para añadir, lo procesamos.
if new_fund_details:
    if add_fund_to_config(new_fund_details['isin'], new_fund_details['name']):
        st.cache_data.clear() # Limpiamos la caché
        st.rerun()           # y recargamos la app

# El resto del flujo principal no cambia...
# 3. VERIFICAR SI HAY FONDOS EN LA CARTERA
if not st.session_state.cartera_isines:
    st.info("⬅️ Comienza por añadir fondos a tu cartera en la barra lateral.")
    st.stop()

# ... (el resto del fichero app.py sigue igual)
# 4. CARGA DE DATOS (SOLO DE LA CARTERA)
isines_a_cargar = tuple(sorted(set(st.session_state.cartera_isines)))
force_update_isin = st.session_state.pop('force_update_isin', None)
all_navs_df = load_all_navs(data_manager, isines_a_cargar, force_update_isin=force_update_isin)

if all_navs_df.empty:
    st.warning("No se pudieron cargar datos para los fondos de la cartera.")
    st.stop()

# 5. FILTRADO Y PROCESADO
filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns = filtered_navs.pct_change().dropna()

# 6. LÓGICA DE OPTIMIZACIÓN
if run_hrp_opt and not daily_returns.empty:
    pesos_opt = hrp_allocation(daily_returns.cov(), daily_returns.corr())
    pesos_opt_dict = {isin: int(round(p * 100)) for isin, p in pesos_opt.items()}
    resto = 100 - sum(pesos_opt_dict.values())
    if resto != 0 and pesos_opt.size > 0:
        pesos_opt_dict[pesos_opt.idxmax()] += resto
    st.session_state.pesos = pesos_opt_dict
    st.success("Cartera optimizada con HRP ✅")
    st.rerun()

# 7. CÁLCULO DE MÉTRICAS Y CARTERA
metricas = []
for isin in daily_returns.columns:
    m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
    m["isin"] = isin
    m["nombre"] = mapa_isin_nombre.get(isin, isin)
    metricas.append(m)
df_metrics = pd.DataFrame(metricas)

portfolio = Portfolio(filtered_navs, st.session_state.pesos)
if portfolio and portfolio.nav is not None:
    metricas_cartera = portfolio.calculate_metrics()
    df_metrics = pd.concat([pd.DataFrame([metricas_cartera]), df_metrics], ignore_index=True)

# 8. RENDERIZAR RESULTADOS
render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre)
render_update_panel(isines_a_cargar, mapa_isin_nombre)