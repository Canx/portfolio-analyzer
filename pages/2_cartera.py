import streamlit as st
import pandas as pd
import json
from pathlib import Path
from streamlit_local_storage import LocalStorage
from src.utils import load_config, load_all_navs

# Importaciones de los módulos
from src.data_manager import DataManager, filtrar_por_horizonte
from src.metrics import calcular_metricas_desde_rentabilidades
from src.portfolio import Portfolio
from src.state import initialize_session_state  # <-- Importamos la nueva función
from src.optimizer import optimize_portfolio, calculate_efficient_frontier, optimize_for_target_return
from src.ui_components import render_sidebar, render_main_content, render_efficient_frontier

# --- INICIALIZAMOS EL ESTADO AL PRINCIPIO DE LA PÁGINA ---
initialize_session_state()


# --- FUNCIÓN SAVE STATE (Adaptada para la nueva estructura) ---
def save_state_to_browser():
    localS = LocalStorage()
    # Guardamos el diccionario completo de carteras
    localS.setItem(
        "mis_carteras", json.dumps(st.session_state.carteras), key="storage_carteras"
    )


# ==============================
#   FLUJO PRINCIPAL DE LA PÁGINA
# ==============================

# 1. CARGAR CONFIGURACIÓN
st.title("📈 Análisis de Cartera")
fondos_config = load_config()  # Necesitamos una función load_config aquí también
if not fondos_config:
    st.stop()
mapa_isin_nombre = {f["isin"]: f["nombre"] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f["isin"] for f in fondos_config}
data_manager = DataManager()

# 2. RENDERIZAR SIDEBAR Y OBTENER ACCIONES
horizonte, run_optimization, modelo_seleccionado, risk_measure, target_return = render_sidebar(
    mapa_nombre_isin, mapa_isin_nombre
)
save_state_to_browser()  # Guardamos el estado en cada interacción

# 3. VERIFICAR SI HAY UNA CARTERA ACTIVA
if not st.session_state.get("cartera_activa") or not st.session_state.carteras.get(
    st.session_state.cartera_activa
):
    st.info(
        "⬅️ Por favor, crea o selecciona una cartera en la barra lateral para empezar el análisis."
    )
    st.stop()

# 4. OBTENER DATOS DE LA CARTERA ACTIVA
cartera_activa_nombre = st.session_state.cartera_activa
cartera_activa_data = st.session_state.carteras[cartera_activa_nombre]
pesos_cartera_activa = cartera_activa_data["pesos"]
isines_a_cargar = tuple(pesos_cartera_activa.keys())

if not isines_a_cargar:
    st.warning("Tu cartera está vacía. Añade fondos desde la barra lateral.")
    st.stop()

# 5. CARGA DE DATOS Y PROCESADO
force_update_isin = st.session_state.pop("force_update_isin", None)
with st.spinner(f"Cargando datos de precios para {len(isines_a_cargar)} fondos en la cartera..."):
    all_navs_df = load_all_navs(
        data_manager, isines_a_cargar, force_update_isin=force_update_isin
    )
if all_navs_df.empty:
    st.stop()

filtered_navs = filtrar_por_horizonte(all_navs_df, horizonte)
daily_returns = filtered_navs.pct_change().dropna()

# 6. LÓGICA DE OPTIMIZACIÓN
if run_optimization and not daily_returns.empty:
    pesos_opt = None
    if modelo_seleccionado == 'TARGET_RET':
        st.info(f"Buscando cartera de mínimo riesgo para una rentabilidad >= {target_return}%...")
        pesos_opt = optimize_for_target_return(daily_returns, target_return)
    else:
        st.info(f"Ejecutando optimización con el modelo: {modelo_seleccionado}...")
        pesos_opt = optimize_portfolio(daily_returns, model=modelo_seleccionado, risk_measure=risk_measure)

    if pesos_opt is not None:
        pesos_opt_dict = {isin: int(round(p * 100)) for isin, p in pesos_opt.items()}
        resto = 100 - sum(pesos_opt_dict.values())
        if resto != 0 and not pesos_opt.empty:
            pesos_opt_dict[pesos_opt.idxmax()] += resto
        # Actualizamos los pesos de la cartera activa
        st.session_state.carteras[cartera_activa_nombre]["pesos"] = pesos_opt_dict
        st.success(
            f"Cartera '{cartera_activa_nombre}' optimizada con {modelo_seleccionado} ✅"
        )
        st.rerun()
    elif modelo_seleccionado == 'TARGET_RET':
        st.error(f"No se encontró ninguna cartera que cumpla con una rentabilidad objetivo del {target_return}%. Prueba con un valor más bajo.")

# 7. CÁLCULO DE MÉTRICAS Y CARTERA
mapa_datos_fondos = {f["isin"]: f for f in fondos_config}
metricas = []
for isin in daily_returns.columns:
    m = calcular_metricas_desde_rentabilidades(daily_returns[isin])
    datos_fondo = mapa_datos_fondos.get(isin, {})
    m.update(datos_fondo)
    metricas.append(m)
df_metrics = pd.DataFrame(metricas)

portfolio = Portfolio(filtered_navs, pesos_cartera_activa)
portfolio_metrics = {}
if portfolio and portfolio.nav is not None:
    metricas_cartera = portfolio.calculate_metrics()
    metricas_cartera["nombre"] = f"💼 {cartera_activa_nombre}"
    # Guardamos las métricas de la cartera para el gráfico
    portfolio_metrics = metricas_cartera
    df_metrics = pd.concat([pd.DataFrame([metricas_cartera]), df_metrics], ignore_index=True)

# --- NUEVO BLOQUE DE CÓDIGO PARA ORDENAR ---
# Creamos una columna temporal con los pesos para poder ordenar
df_metrics["peso_cartera"] = df_metrics["isin"].map(pesos_cartera_activa).fillna(0)
# La cartera agregada ("Mi Cartera") no tiene ISIN, le damos el peso máximo para que salga arriba
df_metrics.loc[df_metrics["nombre"].str.startswith("💼"), "peso_cartera"] = 101
# Ordenamos el DataFrame por este nuevo peso
df_metrics = df_metrics.sort_values(by="peso_cartera", ascending=False).drop(
    columns=["peso_cartera"]
)


# 8. RENDERIZAR RESULTADOS
render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre)


# Opcional: El panel de actualización puede seguir aquí o moverse al explorador
# render_update_panel(isines_a_cargar, mapa_isin_nombre)


# Necesitas añadir estas funciones aquí si no están en un módulo importado
@st.cache_data
def load_config(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])


@st.cache_data
def load_all_navs(_data_manager, isines: tuple, force_update_isin: str = None):
    with st.spinner("Cargando datos..."):
        all_navs = {}
        for isin in isines:
            force = isin == force_update_isin
            df = _data_manager.get_fund_nav(isin, force_to_today=force)
            if df is not None:
                all_navs[isin] = df["nav"]
    if not all_navs:
        return pd.DataFrame()
    return pd.concat(all_navs, axis=1).ffill()
