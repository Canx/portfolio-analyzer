# app.py (VERSIÓN FINAL Y CORREGIDA)

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import json
from pathlib import Path
from portfolio_analyzer import procesar_fondo, filtrar_por_horizonte, calcular_metricas_desde_rentabilidades

# ==============================
#   CONFIGURACIÓN INICIAL Y CARGA DE DATOS
# ==============================
st.set_page_config(page_title="📊 Analizador de Fondos", layout="wide")
st.title("📊 Analizador de Fondos de Inversión")

@st.cache_data
def cargar_fondos(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists():
        st.error(f"Fichero de configuración '{config_file}' no encontrado.")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("fondos", [])

fondos_config = cargar_fondos()
if not fondos_config:
    st.stop()

mapa_isin_nombre = {f["isin"]: f["nombre"] for f in fondos_config}

# ==============================
#   BARRA LATERAL (SIDEBAR)
# ==============================
with st.sidebar:
    st.header("Configuración del Análisis")

    fondos_nombres = [f"{f['nombre']} ({f['isin']})" for f in fondos_config]
    seleccionados_nombres = st.multiselect("Selecciona fondos", fondos_nombres, default=fondos_nombres)
    seleccionados_isin = [f["isin"] for f in fondos_config if f"{f['nombre']} ({f['isin']})" in seleccionados_nombres]

    horizonte = st.selectbox("Horizonte temporal", ["3m", "6m", "YTD", "1y", "3y", "5y", "max"])
    
    opciones = st.multiselect(
        "Selecciona visualizaciones:",
        ["Rentabilidad", "Volatilidad", "Riesgo vs. Retorno", "Correlaciones"],
        default=["Rentabilidad", "Volatilidad", "Riesgo vs. Retorno", "Correlaciones"]
    )

    with st.expander("⚖️ Asignación de Pesos (%)", expanded=True):
        if 'pesos' not in st.session_state or set(st.session_state.pesos.keys()) != set(seleccionados_isin):
            st.session_state.pesos = {isin: int(100 / len(seleccionados_isin)) for isin in seleccionados_isin} if seleccionados_isin else {}
            if seleccionados_isin:
                st.session_state.pesos[seleccionados_isin[0]] += 100 - sum(st.session_state.pesos.values())

        pesos_anteriores = st.session_state.pesos.copy()
        for isin in seleccionados_isin:
            st.session_state.pesos[isin] = st.slider(mapa_isin_nombre.get(isin, isin), 0, 100, st.session_state.pesos.get(isin, 0), 1)

        if st.session_state.pesos != pesos_anteriores:
            isin_modificado = [isin for isin in seleccionados_isin if st.session_state.pesos.get(isin) != pesos_anteriores.get(isin)][0]
            delta = st.session_state.pesos[isin_modificado] - pesos_anteriores[isin_modificado]
            otros_isines = [isin for isin in seleccionados_isin if isin != isin_modificado]
            isines_ajustables = [i for i in otros_isines if (delta > 0 and st.session_state.pesos[i] > 0) or (delta < 0 and st.session_state.pesos[i] < 100)]
            
            if isines_ajustables:
                suma_ajustable = sum(st.session_state.pesos[i] for i in isines_ajustables)
                for isin in isines_ajustables:
                    ratio = st.session_state.pesos[isin] / suma_ajustable if suma_ajustable > 0 else 1 / len(isines_ajustables)
                    st.session_state.pesos[isin] -= delta * ratio
                for isin in isines_ajustables:
                    st.session_state.pesos[isin] = max(0, min(100, int(round(st.session_state.pesos[isin]))))
                
                suma_actual = sum(st.session_state.pesos.values())
                if suma_actual != 100 and isines_ajustables:
                    st.session_state.pesos[isines_ajustables[0]] += 100 - suma_actual
            
            st.rerun()

        pesos = st.session_state.pesos
        total_peso = sum(pesos.values())
        st.metric("Suma Total", f"{total_peso}%")

# ==============================
#   PROCESADO Y CÁLCULO DE DATOS
# ==============================

@st.cache_data
def cargar_y_filtrar_datos(isines, horizonte_seleccionado):
    dfs_filtrados = {}
    for isin in isines:
        df, _ = procesar_fondo(isin)
        if df is not None:
            df_indexed = df.set_index("date")
            df_filtrado = filtrar_por_horizonte(df_indexed.reset_index(), horizonte_seleccionado)
            if not df_filtrado.empty:
                dfs_filtrados[isin] = df_filtrado
    return dfs_filtrados

if not seleccionados_isin:
    st.warning("Por favor, selecciona al menos un fondo en la barra lateral.")
    st.stop()

dfs_filtrados = cargar_y_filtrar_datos(tuple(seleccionados_isin), horizonte)

if not dfs_filtrados:
    st.warning(f"No se encontraron datos para el horizonte temporal seleccionado: {horizonte}")
    st.stop()

# --- Cálculo de Métricas Unificado ---
aligned_daily_returns = pd.concat(
    {isin: df["nav"].pct_change(fill_method=None) for isin, df in dfs_filtrados.items()}, axis=1
).dropna()

if aligned_daily_returns.empty:
    st.warning("No hay datos superpuestos para los fondos y el horizonte seleccionados.")
    st.stop()

metricas_fondos = []
for isin in aligned_daily_returns.columns:
    metrics = calcular_metricas_desde_rentabilidades(aligned_daily_returns[isin])
    metrics["isin"] = isin
    metrics["nombre"] = mapa_isin_nombre.get(isin, isin)
    metricas_fondos.append(metrics)
df_metrics = pd.DataFrame(metricas_fondos)

portfolio_nav, portfolio_daily_returns = None, None
if seleccionados_isin and total_peso > 0:
    pesos_normalizados = {isin: peso / total_peso for isin, peso in pesos.items()}
    isines_con_peso = [isin for isin in pesos_normalizados.keys() if isin in aligned_daily_returns.columns]
    
    portfolio_daily_returns = aligned_daily_returns[isines_con_peso].mul(pd.Series(pesos_normalizados), axis=1).sum(axis=1)
    metrics_cartera = calcular_metricas_desde_rentabilidades(portfolio_daily_returns)
    
    if metrics_cartera:
        metrics_cartera["nombre"] = "💼 Mi Cartera"
        df_metrics_cartera = pd.DataFrame([metrics_cartera])
        df_metrics = pd.concat([df_metrics_cartera, df_metrics], ignore_index=True)
    portfolio_nav = (1 + portfolio_daily_returns).cumprod() * 100

# ==============================
#   VISUALIZACIÓN DE RESULTADOS
# ==============================
st.header("Resultados del Análisis")

# --- Tabla de Métricas ---
st.subheader(f"📑 Métricas resumidas para el horizonte: {horizonte}")
nombres_nuevos = {
    "annualized_return_%": "Rent. Anual (%)", "volatility_ann_%": "Volatilidad Anual (%)",
    "sharpe_ann": "Ratio Sharpe", "max_drawdown_%": "Caída Máxima (%)"
}
columnas_a_mostrar = ["nombre", "annualized_return_%", "volatility_ann_%", "sharpe_ann", "max_drawdown_%"]
columnas_existentes = [col for col in columnas_a_mostrar if col in df_metrics.columns]
df_display = df_metrics[columnas_existentes].rename(columns=nombres_nuevos)
st.dataframe(df_display.set_index("nombre"))

# --- Gráficos ---
# ... (El código de los gráficos que sigue es el mismo que ya tenías y es correcto)
if "Rentabilidad" in opciones:
    st.subheader("📈 Evolución normalizada")
    combined = pd.concat({isin: df["nav"] for isin, df in dfs_filtrados.items()}, axis=1).bfill().ffill()
    combined_norm = combined.apply(lambda x: x / x.iloc[0]) * 100
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in combined_norm.columns:
        ax.plot(combined_norm.index, combined_norm[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
    if portfolio_nav is not None and not portfolio_nav.empty:
        portfolio_norm = portfolio_nav / portfolio_nav.iloc[0] * 100
        ax.plot(portfolio_norm.index, portfolio_norm.values, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
    ax.legend()
    ax.set_title(f"Evolución normalizada - Horizonte: {horizonte}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate(rotation=45)
    ax.grid(True)
    st.pyplot(fig)

if "Volatilidad" in opciones:
    st.subheader(f"📊 Volatilidad rolling (30d) para el horizonte: {horizonte}")
    # Usamos aligned_daily_returns como base para consistencia
    rolling_vol_funds = aligned_daily_returns.rolling(30).std() * (252**0.5)
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in rolling_vol_funds.columns:
        ax.plot(rolling_vol_funds.index, rolling_vol_funds[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
    if portfolio_daily_returns is not None and not portfolio_daily_returns.empty:
        portfolio_rolling_vol = portfolio_daily_returns.rolling(30).std() * (252**0.5)
        ax.plot(portfolio_rolling_vol.index, portfolio_rolling_vol.values, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
    ax.legend()
    ax.set_title(f"Volatilidad anualizada (rolling 30d) - Horizonte: {horizonte}")
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    fig.autofmt_xdate(rotation=45)
    ax.grid(True)
    st.pyplot(fig)

if "Riesgo vs. Retorno" in opciones:
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
    
    ax.set_xlabel(f"Volatilidad Anualizada (%) - Periodo: {horizonte}")
    ax.set_ylabel(f"Rentabilidad Anualizada (%) - Periodo: {horizonte}")
    ax.set_title("Riesgo vs. Retorno de los Fondos y la Cartera")
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend()
    st.pyplot(fig)
    st.info("""**Cómo interpretar el gráfico:**\n* **Busca la estrella (⭐):** Esa es tu cartera. ¿Está en un cuadrante mejor que los fondos individuales? Idealmente, debería estar más a la izquierda (menos riesgo) y más arriba (más retorno) que la media de tus fondos.""")

if "Correlaciones" in opciones and len(seleccionados_isin) > 1:
    st.subheader("🔗 Correlación entre fondos")
    corr_matrix = aligned_daily_returns.corr()
    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5, ax=ax)
    ax.set_title(f"Correlación de rentabilidades diarias - Horizonte: {horizonte}")
    st.pyplot(fig)