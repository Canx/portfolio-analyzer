import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import json
from pathlib import Path
import datetime
from streamlit_local_storage import LocalStorage
from portfolio_analyzer import procesar_fondo, filtrar_por_horizonte, calcular_metricas_desde_rentabilidades

# ==============================
#   CONFIGURACIÓN INICIAL
# ==============================
st.set_page_config(page_title="📊 Analizador de Fondos", layout="wide")
st.title("📊 Analizador de Fondos de Inversión")

# ------------------------------
#   HELPERS (carga y estado)
# ------------------------------
@st.cache_data
def cargar_fondos(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists():
        st.error(f"Fichero de configuración '{config_file}' no encontrado.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fondos", [])

@st.cache_data
def cargar_y_filtrar_datos(isines, horizonte_seleccionado):
    dfs_filtrados = {}
    for isin in isines:
        df, _ = procesar_fondo(isin)  # lectura/descarga si no existe
        if df is not None:
            df_indexed = df.set_index("date")
            df_filtrado = filtrar_por_horizonte(df_indexed.reset_index(), horizonte_seleccionado)
            if not df_filtrado.empty:
                dfs_filtrados[isin] = df_filtrado
    return dfs_filtrados

# LocalStorage (lado cliente) para persistir la cartera
localS = LocalStorage()

def leer_cartera_guardada():
    cartera_guardada = None
    json_cartera = localS.getItem('mi_cartera')
    if json_cartera and json_cartera != 'null':
        try:
            cartera_guardada = json.loads(json_cartera)
        except json.JSONDecodeError:
            st.error("No se pudo cargar la cartera guardada. El formato es incorrecto.")
            cartera_guardada = None
    return cartera_guardada or {"fondos": [], "pesos": {}}

# Estado de fichero local de un fondo
def ultima_fecha_disponible(isin: str):
    file_path = Path("fondos_data") / f"{isin}.csv"
    if not file_path.exists():
        return None
    try:
        df = pd.read_csv(file_path, parse_dates=["date"])
        if df.empty:
            return None
        return df["date"].max().date()
    except Exception:
        return None

# ==============================
#   CARGA DE CONFIGURACIÓN
# ==============================
fondos_config = cargar_fondos()
if not fondos_config:
    st.stop()

# Mapeos útiles
todos_isines = [f['isin'] for f in fondos_config]
mapa_isin_nombre = {f['isin']: f['nombre'] for f in fondos_config}
mapa_nombre_isin = {f"{f['nombre']} ({f['isin']})": f['isin'] for f in fondos_config}

# ==============================
#   ESTADO INICIAL (SESSION)
# ==============================
cartera_guardada = leer_cartera_guardada()

# Cartera: lista de isins + pesos
if 'cartera_isines' not in st.session_state:
    st.session_state.cartera_isines = [i for i in cartera_guardada.get('fondos', []) if i in todos_isines]

if 'pesos' not in st.session_state:
    pesos_guardados = {k: int(v) for k, v in cartera_guardada.get('pesos', {}).items() if k in st.session_state.cartera_isines}
    if st.session_state.cartera_isines and not pesos_guardados:
        base = int(100/len(st.session_state.cartera_isines))
        pesos_guardados = {i: base for i in st.session_state.cartera_isines}
        pesos_guardados[st.session_state.cartera_isines[0]] += 100 - sum(pesos_guardados.values())
    st.session_state.pesos = pesos_guardados

# Listado guardado
json_listado = localS.getItem('mi_listado')
if json_listado and json_listado != 'null':
    try:
        listado_guardado = json.loads(json_listado)
    except json.JSONDecodeError:
        st.error("No se pudo cargar el listado guardado. Formato incorrecto.")
        listado_guardado = []
else:
    listado_guardado = []

# Listado (fondos a analizar)
if 'listado_isines' not in st.session_state:
    st.session_state.listado_isines = listado_guardado or todos_isines.copy()

# ------------------------------
#   UTILIDAD: ajustar pesos (direccional)
# ------------------------------
def ajustar_pesos_direccional(isines_ordenados, pesos_dict, isin_modificado, pesos_previos):
    index_modificado = isines_ordenados.index(isin_modificado)
    delta = pesos_dict[isin_modificado] - pesos_previos.get(isin_modificado, 0)
    isines_para_ajustar = isines_ordenados[index_modificado + 1:]
    if not isines_para_ajustar:
        isines_para_ajustar = isines_ordenados[:index_modificado]
    if not isines_para_ajustar:
        return pesos_dict
    isines_ajustables = [i for i in isines_para_ajustar if (delta > 0 and pesos_dict[i] > 0) or (delta < 0 and pesos_dict[i] < 100)]
    if not isines_ajustables:
        return pesos_dict
    suma_ajustable = sum(pesos_dict[i] for i in isines_ajustables)
    for isin in isines_ajustables:
        ratio = pesos_dict[isin] / suma_ajustable if suma_ajustable > 0 else 1/len(isines_ajustables)
        pesos_dict[isin] -= delta * ratio
    for isin in isines_ajustables:
        pesos_dict[isin] = max(0, min(100, int(round(pesos_dict[isin]))))
    suma_actual = sum(pesos_dict.values())
    if suma_actual != 100 and isines_ajustables:
        pesos_dict[isines_ajustables[0]] += 100 - suma_actual
    return pesos_dict

# ==============================
#   BARRA LATERAL (SIDEBAR)
# ==============================
with st.sidebar:
    st.header("Configuración del Análisis")
    st.subheader("📋 Listado de fondos (para análisis)")
    fondos_nombres = list(mapa_nombre_isin.keys())
    default_selection = [n for n in fondos_nombres if mapa_nombre_isin[n] in st.session_state.listado_isines]
    seleccionados_listado_nombres = st.multiselect("Selecciona fondos a mostrar", fondos_nombres, default=default_selection, key="multiselect_listado")
    st.session_state.listado_isines = [mapa_nombre_isin[n] for n in seleccionados_listado_nombres]
    horizonte = st.selectbox("Horizonte temporal", ["3m", "6m", "YTD", "1y", "3y", "5y", "max"], key="horizonte")
    opciones = st.multiselect("Selecciona visualizaciones:", ["Rentabilidad", "Volatilidad", "Riesgo vs. Retorno", "Correlaciones"], default=["Rentabilidad", "Volatilidad", "Riesgo vs. Retorno", "Correlaciones"], key="opciones_graficos")
    st.markdown("---")
    st.subheader("💼 Mi Cartera")
    candidatos = [n for n in fondos_nombres if mapa_nombre_isin[n] not in st.session_state.cartera_isines]
    add_sel = st.selectbox("Añadir fondo a la cartera", ["—"] + candidatos, index=0)
    if add_sel != "—" and st.button("➕ Añadir a cartera"):
        nuevo_isin = mapa_nombre_isin[add_sel]
        st.session_state.cartera_isines.append(nuevo_isin)
        if nuevo_isin not in st.session_state.pesos:
            if st.session_state.pesos:
                for k in st.session_state.pesos:
                    st.session_state.pesos[k] = max(0, int(round(st.session_state.pesos[k] * (len(st.session_state.cartera_isines)-1)/len(st.session_state.cartera_isines))))
                st.session_state.pesos[nuevo_isin] = 100 - sum(st.session_state.pesos.values())
            else:
                st.session_state.pesos[nuevo_isin] = 100
        st.rerun()
    for isin in list(st.session_state.cartera_isines):
        cols = st.columns([5, 2, 1])
        cols[0].markdown(f"**{mapa_isin_nombre.get(isin, isin)}**\n\n<small>{isin}</small>", unsafe_allow_html=True)
        peso_prev = st.session_state.pesos.get(isin, 0)
        st.session_state.pesos[isin] = cols[1].slider("Peso %", 0, 100, peso_prev, 1, key=f"peso_{isin}")
        if cols[2].button("🗑️", key=f"remove_{isin}"):
            st.session_state.cartera_isines.remove(isin)
            st.session_state.pesos.pop(isin, None)
            st.rerun()
    if st.session_state.cartera_isines:
        pesos_previos = getattr(st.session_state, 'pesos_previos', st.session_state.pesos.copy())
        mod = None
        for i in st.session_state.cartera_isines:
            if st.session_state.pesos.get(i, 0) != pesos_previos.get(i, 0):
                mod = i
                break
        if mod:
            st.session_state.pesos = ajustar_pesos_direccional(st.session_state.cartera_isines, st.session_state.pesos, mod, pesos_previos)
            st.session_state.pesos_previos = st.session_state.pesos.copy()
            st.rerun()
        else:
            st.session_state.pesos_previos = st.session_state.pesos.copy()
    total_peso = sum(st.session_state.pesos.values()) if st.session_state.pesos else 0
    st.metric("Suma Total", f"{total_peso}%")
    st.markdown("---")
    st.subheader("Gestionar Cartera")
    if st.button("💾 Guardar Cartera"):
        if total_peso == 100 or total_peso == 0:
            cartera_a_guardar = {"fondos": st.session_state.cartera_isines, "pesos": st.session_state.pesos}
            localS.setItem('mi_cartera', json.dumps(cartera_a_guardar))
            st.success("¡Cartera guardada!")
        else:
            st.error("La suma de los pesos debe ser 100%.")
    if st.button("🗑️ Borrar Cartera Guardada"):
        localS.setItem('mi_cartera', None)
        st.session_state.cartera_isines = []
        st.session_state.pesos = {}
        st.success("Cartera eliminada.")
        st.rerun()
    st.markdown("---")
    st.subheader("Gestionar Listado")
    if st.button("💾 Guardar Listado"):
        listado_a_guardar = st.session_state.listado_isines
        localS.setItem('mi_listado', json.dumps(listado_a_guardar))
        st.success("¡Listado guardado!")
    if st.button("🗑️ Borrar Listado Guardado"):
        localS.setItem('mi_listado', None)
        st.session_state.listado_isines = todos_isines.copy()
        st.success("Listado eliminado.")
        st.rerun()

# ==============================
#   PROCESADO Y MÉTRICAS
# ==============================
listado_isines = st.session_state.listado_isines
cartera_isines = st.session_state.cartera_isines

if not listado_isines and not cartera_isines:
    st.warning("Selecciona fondos en el Listado o añade fondos a tu Cartera para empezar.")
    st.stop()

# Carga datos del Listado
dfs_listado = cargar_y_filtrar_datos(tuple(listado_isines), st.session_state.horizonte)

if not dfs_listado and not cartera_isines:
    st.warning(f"No se encontraron datos para el horizonte seleccionado: {st.session_state.horizonte}")
    st.stop()

# Returns diarios para el listado
aligned_daily_returns_listado = None
if dfs_listado:
    aligned_daily_returns_listado = pd.concat(
        {isin: df["nav"].pct_change(fill_method=None) for isin, df in dfs_listado.items()}, axis=1
    ).dropna()

# Métricas por fondo (del listado)
metricas_fondos = []
if aligned_daily_returns_listado is not None and not aligned_daily_returns_listado.empty:
    for isin in aligned_daily_returns_listado.columns:
        metrics = calcular_metricas_desde_rentabilidades(aligned_daily_returns_listado[isin])
        metrics["isin"] = isin
        metrics["nombre"] = mapa_isin_nombre.get(isin, isin)
        metricas_fondos.append(metrics)

df_metrics = pd.DataFrame(metricas_fondos) if metricas_fondos else pd.DataFrame()

# --- Cartera: métricas y NAV ---
portfolio_nav, portfolio_daily_returns = None, None
if cartera_isines and sum(st.session_state.pesos.values()) > 0:
    # Asegurarnos de tener datos de todos los fondos de la cartera (pueden no estar en el listado)
    faltan = [i for i in cartera_isines if i not in (dfs_listado.keys() if dfs_listado else [])]
    dfs_cartera_extra = cargar_y_filtrar_datos(tuple(faltan), st.session_state.horizonte) if faltan else {}

    dfs_cartera = {**dfs_listado, **dfs_cartera_extra} if dfs_listado else dfs_cartera_extra

    if dfs_cartera:
        aligned_daily_returns_cartera = pd.concat(
            {isin: df["nav"].pct_change(fill_method=None) for isin, df in dfs_cartera.items() if isin in cartera_isines}, axis=1
        ).dropna()
        if not aligned_daily_returns_cartera.empty:
            pesos_normalizados = {isin: st.session_state.pesos.get(isin, 0) / 100 for isin in cartera_isines if isin in aligned_daily_returns_cartera.columns}
            isines_con_peso = [i for i, p in pesos_normalizados.items() if p > 0]
            if isines_con_peso:
                portfolio_daily_returns = aligned_daily_returns_cartera[isines_con_peso].mul(pd.Series(pesos_normalizados), axis=1).sum(axis=1)
                metrics_cartera = calcular_metricas_desde_rentabilidades(portfolio_daily_returns)
                if metrics_cartera:
                    metrics_cartera["nombre"] = "💼 Mi Cartera"
                    df_metrics = pd.concat([pd.DataFrame([metrics_cartera]), df_metrics], ignore_index=True)
                portfolio_nav = (1 + portfolio_daily_returns).cumprod() * 100

# ==============================
#   VISUALIZACIÓN DE RESULTADOS
# ==============================
st.header("Resultados del Análisis")

# --- Tabla de Métricas ---
st.subheader(f"📑 Métricas resumidas para el horizonte: {st.session_state.horizonte}")
nombres_nuevos = {
    "annualized_return_%": "Rent. Anual (%)",
    "volatility_ann_%": "Volatilidad Anual (%)",
    "sharpe_ann": "Ratio Sharpe",
    "max_drawdown_%": "Caída Máxima (%)"
}
columnas_a_mostrar = ["nombre", "annualized_return_%", "volatility_ann_%", "sharpe_ann", "max_drawdown_%"]
if not df_metrics.empty:
    columnas_existentes = [col for col in columnas_a_mostrar if col in df_metrics.columns]
    df_display = df_metrics[columnas_existentes].rename(columns=nombres_nuevos)
    num_rows = len(df_display)
    altura_dinamica = (num_rows + 1) * 35 + 3
    st.dataframe(df_display.set_index("nombre"), height=altura_dinamica)
else:
    st.info("No hay métricas para el listado actual.")

# --- Gráficos ---
if aligned_daily_returns_listado is not None and not aligned_daily_returns_listado.empty:
    if "Rentabilidad" in st.session_state.opciones_graficos:
        st.subheader("📈 Evolución normalizada")
        combined = pd.concat({isin: df["nav"] for isin, df in dfs_listado.items()}, axis=1).bfill().ffill()
        combined_norm = combined.apply(lambda x: x / x.iloc[0]) * 100
        fig, ax = plt.subplots(figsize=(10, 5))
        for col in combined_norm.columns:
            ax.plot(combined_norm.index, combined_norm[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
        if portfolio_nav is not None and not portfolio_nav.empty:
            portfolio_norm = portfolio_nav / portfolio_nav.iloc[0] * 100
            ax.plot(portfolio_norm.index, portfolio_norm.values, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
        ax.legend()
        ax.set_title(f"Evolución normalizada - Horizonte: {st.session_state.horizonte}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate(rotation=45)
        ax.grid(True)
        st.pyplot(fig)

    if "Volatilidad" in st.session_state.opciones_graficos:
        st.subheader(f"📊 Volatilidad rolling (30d) para el horizonte: {st.session_state.horizonte}")
        rolling_vol_funds = aligned_daily_returns_listado.rolling(30).std() * (252**0.5)
        fig, ax = plt.subplots(figsize=(10, 5))
        for col in rolling_vol_funds.columns:
            ax.plot(rolling_vol_funds.index, rolling_vol_funds[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
        if portfolio_daily_returns is not None and not portfolio_daily_returns.empty:
            portfolio_rolling_vol = portfolio_daily_returns.rolling(30).std() * (252**0.5)
            ax.plot(portfolio_rolling_vol.index, portfolio_rolling_vol.values, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
        ax.legend()
        ax.set_title(f"Volatilidad anualizada (rolling 30d) - Horizonte: {st.session_state.horizonte}")
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        fig.autofmt_xdate(rotation=45)
        ax.grid(True)
        st.pyplot(fig)

    if "Riesgo vs. Retorno" in st.session_state.opciones_graficos and not df_metrics.empty:
        st.subheader("📊 Rentabilidad vs. Volatilidad")
        fig, ax = plt.subplots(figsize=(10, 6))
        df_fondos_solo = df_metrics[df_metrics["nombre"] != "💼 Mi Cartera"]
        if not df_fondos_solo.empty:
            x_fondos, y_fondos = df_fondos_solo["volatility_ann_%"], df_fondos_solo["annualized_return_%"]
            ax.scatter(x_fondos, y_fondos, s=100, alpha=0.6, edgecolors="k", label="Fondos Individuales")
            for i, txt in enumerate(df_fondos_solo["nombre"]):
                ax.annotate(txt, (x_fondos.iloc[i], y_fondos.iloc[i]), xytext=(5,5), textcoords='offset points')
            ax.axvline(x_fondos.mean(), color='gray', linestyle='--', linewidth=0.8)
            ax.axhline(y_fondos.mean(), color='gray', linestyle='--', linewidth=0.8)

        if not df_metrics[df_metrics["nombre"] == "💼 Mi Cartera"].empty:
            cartera_metrics = df_metrics[df_metrics["nombre"] == "💼 Mi Cartera"].iloc[0]
            x_cartera, y_cartera = cartera_metrics["volatility_ann_%"], cartera_metrics["annualized_return_%"]
            ax.scatter(x_cartera, y_cartera, s=300, c="red", marker="*", edgecolors="black", label="💼 Mi Cartera", zorder=5)
            ax.annotate("Mi Cartera", (x_cartera, y_cartera), xytext=(5,5), textcoords='offset points', weight='bold')
        ax.set_xlabel(f"Volatilidad Anualizada (%) - Periodo: {st.session_state.horizonte}")
        ax.set_ylabel(f"Rentabilidad Anualizada (%) - Periodo: {st.session_state.horizonte}")
        ax.set_title("Riesgo vs. Retorno de los Fondos y la Cartera")
        ax.grid(True, linestyle=':', alpha=0.6)
        ax.legend()
        st.pyplot(fig)
        st.info("""**Cómo interpretar el gráfico:**\n* **Busca la estrella (⭐):** Esa es tu cartera. Idealmente, más a la izquierda (menos riesgo) y más arriba (más retorno) que la media de los fondos.""")

    if "Correlaciones" in st.session_state.opciones_graficos and aligned_daily_returns_listado.shape[1] > 1:
        st.subheader("🔗 Correlación entre fondos (Listado)")
        corr_matrix = aligned_daily_returns_listado.corr()
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5, ax=ax)
        ax.set_title(f"Correlación de rentabilidades diarias - Horizonte: {st.session_state.horizonte}")
        st.pyplot(fig)

# ==============================
#   PANEL DE ACTUALIZACIÓN
# ==============================
st.markdown("---")
st.subheader("📅 Estado de actualización de los fondos")

hoy = datetime.date.today()

def render_estado_tabla(isines, titulo, boton_todos_key):
    st.markdown(f"#### {titulo}")
    # Cabecera
    head = st.columns([3, 2, 2, 2])
    head[0].markdown("**Fondo**")
    head[1].markdown("**ISIN**")
    head[2].markdown("**Última fecha**")
    head[3].markdown("**Acción**")

    desactualizados = []
    for isin in isines:
        nombre = mapa_isin_nombre.get(isin, isin)
        ufd = ultima_fecha_disponible(isin)
        al_dia = (ufd == hoy)
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(nombre)
        c2.write(isin)
        c3.write(ufd if ufd else "—")
        if c4.button("🔄 Actualizar", key=f"update_{titulo}_{isin}"):
            # Forzar actualización hasta hoy
            procesar_fondo(isin, force_to_today=True)  # requiere parámetro en portfolio_analyzer
            st.cache_data.clear()
            st.success(f"✅ {nombre} actualizado")
            st.rerun()
        if not al_dia:
            desactualizados.append(isin)

    if st.button("🔄 Actualizar desactualizados", key=boton_todos_key):
        if not desactualizados:
            st.info("Todos los fondos ya están al día.")
        else:
            for isin in desactualizados:
                procesar_fondo(isin, force_to_today=True)
            st.cache_data.clear()
            st.success(f"✅ Actualizados: {len(desactualizados)} fondos")
            st.rerun()

# Tablas separadas: Listado y Cartera
if listado_isines:
    render_estado_tabla(listado_isines, "Listado", "btn_update_listado")
if cartera_isines:
    render_estado_tabla(cartera_isines, "Cartera", "btn_update_cartera")