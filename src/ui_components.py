# src/ui_components.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from streamlit_local_storage import LocalStorage

# --- HELPERS DE UI ---
def ajustar_pesos_direccional(isines_ordenados, pesos_dict, isin_modificado, pesos_previos):
    """Ajusta los pesos del resto de activos para que la suma total sea 100."""
    if not isines_ordenados or len(isines_ordenados) <= 1:
        return pesos_dict
    index_modificado = isines_ordenados.index(isin_modificado)
    delta = pesos_dict[isin_modificado] - pesos_previos.get(isin_modificado, 0)
    isines_para_ajustar = isines_ordenados[index_modificado + 1:]
    if not isines_para_ajustar:
        isines_para_ajustar = isines_ordenados[:index_modificado]
    if not isines_para_ajustar:
        return pesos_dict
    isines_ajustables = [i for i in isines_para_ajustar if (delta > 0 and pesos_dict[i] > 0) or (delta < 0 and pesos_dict[i] < 100)]
    if not isines_ajustables:
        isines_ajustables = [i for i in isines_ordenados if i != isin_modificado]
        if not isines_ajustables: return pesos_dict
    suma_ajustable = sum(pesos_dict[i] for i in isines_ajustables)
    for isin in isines_ajustables:
        ratio = pesos_dict[isin] / suma_ajustable if suma_ajustable > 0 else 1 / len(isines_ajustables)
        pesos_dict[isin] -= delta * ratio
    for isin in isines_ajustables:
        pesos_dict[isin] = max(0, min(100, int(round(pesos_dict[isin]))))
    suma_actual = sum(pesos_dict.values())
    if suma_actual != 100 and isines_ajustables:
        pesos_dict[isines_ajustables[0]] += 100 - suma_actual
    return pesos_dict

# --- COMPONENTES PRINCIPALES ---
def render_sidebar(mapa_nombre_isin, mapa_isin_nombre):
    """
    Renderiza la barra lateral.
    Reincorpora el formulario para añadir nuevos fondos al catálogo.
    """
    with st.sidebar:
        st.header("Configuración del Análisis")

        horizonte = st.selectbox("Horizonte temporal", ["3m", "6m", "YTD", "1y", "3y", "5y", "max"], key="horizonte")
        st.markdown("---")

        st.header("💼 Mi Cartera")
        st.info("Los fondos que añadas aquí serán los que se analicen y muestren en los gráficos.")

        fondos_nombres = list(mapa_nombre_isin.keys())
        candidatos = [n for n in fondos_nombres if mapa_nombre_isin[n] not in st.session_state.cartera_isines]
        add_sel = st.selectbox("Añadir fondo a la cartera", ["—"] + candidatos, index=0)

        if add_sel != "—" and st.button("➕ Añadir a cartera"):
            nuevo_isin = mapa_nombre_isin[add_sel]
            st.session_state.cartera_isines.append(nuevo_isin)
            num_fondos = len(st.session_state.cartera_isines)
            peso_base = 100 // num_fondos
            st.session_state.pesos = {isin: peso_base for isin in st.session_state.cartera_isines}
            if num_fondos > 0:
                resto = 100 - sum(st.session_state.pesos.values())
                st.session_state.pesos[st.session_state.cartera_isines[0]] += resto
            st.rerun()

        if not st.session_state.cartera_isines:
            st.warning("Añade fondos para empezar el análisis.")

        # El resto de la lógica de la cartera (sliders, etc.) no cambia...
        pesos_previos = st.session_state.pesos.copy()
        for isin in list(st.session_state.cartera_isines):
            cols = st.columns([5, 2, 1])
            cols[0].markdown(f"**{mapa_isin_nombre.get(isin, isin)}**")
            st.session_state.pesos[isin] = cols[1].slider(
                "Peso %", 0, 100, st.session_state.pesos.get(isin, 0), 1, key=f"peso_{isin}"
            )
            if cols[2].button("🗑️", key=f"remove_{isin}"):
                st.session_state.cartera_isines.remove(isin)
                st.session_state.pesos.pop(isin, None)
                st.rerun()
        
        isin_modificado = None
        for isin, peso in st.session_state.pesos.items():
            if peso != pesos_previos.get(isin, 0):
                isin_modificado = isin
                break
        
        if isin_modificado:
            st.session_state.pesos = ajustar_pesos_direccional(
                st.session_state.cartera_isines, st.session_state.pesos, isin_modificado, pesos_previos
            )
            st.rerun()

        if st.session_state.cartera_isines:
            total_peso = sum(st.session_state.pesos.values())
            st.metric("Suma Total", f"{total_peso}%")

        st.markdown("---")
        st.subheader("⚖️ Optimización (HRP)")
        run_hrp_optimization = st.button("🚀 Optimizar Cartera")

        # --- AQUÍ SE AÑADE DE NUEVO EL FORMULARIO ---
        st.markdown("---")
        with st.expander("➕ Añadir nuevo fondo al catálogo"):
            with st.form("form_add_fund"):
                new_isin = st.text_input("ISIN del nuevo fondo").strip().upper()
                new_name = st.text_input("Nombre del nuevo fondo").strip()
                submitted = st.form_submit_button("Añadir")

                if submitted:
                    if not new_isin or not new_name:
                        st.error("Debes rellenar tanto el ISIN como el nombre.")
                    else:
                        config_file = Path("fondos.json")
                        if config_file.exists():
                            with open(config_file, "r", encoding="utf-8") as f:
                                data = json.load(f)
                        else:
                            data = {"fondos": []}
                        
                        if any(f["isin"] == new_isin for f in data["fondos"]):
                            st.warning(f"El ISIN {new_isin} ya existe en el catálogo.")
                        else:
                            data["fondos"].append({"isin": new_isin, "nombre": new_name})
                            with open(config_file, "w", encoding="utf-8") as f:
                                json.dump(data, f, indent=2, ensure_ascii=False)
                            st.success(f"¡Fondo '{new_name}' añadido! La app se recargará.")
                            st.cache_data.clear() # Limpiar caché para recargar el JSON
                            st.rerun()

    return horizonte, run_hrp_optimization

def render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre):
    """Renderiza el contenido principal. Muestra todos los gráficos siempre."""
    st.header("Análisis de la Cartera")

    # --- TABLA DE MÉTRICAS ---
    st.subheader(f"📑 Métricas para el horizonte: {st.session_state.horizonte}")
    if not df_metrics.empty:
        df_display = df_metrics.rename(columns={
            "nombre": "Nombre", "annualized_return_%": "Rent. Anual (%)",
            "volatility_ann_%": "Volatilidad Anual (%)", "sharpe_ann": "Ratio Sharpe",
            "max_drawdown_%": "Caída Máxima (%)"
        }).set_index("Nombre")[["Rent. Anual (%)", "Volatilidad Anual (%)", "Ratio Sharpe", "Caída Máxima (%)"]]
        st.dataframe(df_display.style.format("{:.2f}"))
    
    # --- GRÁFICOS ---
    if daily_returns.empty: return

    navs_normalizados = (1 + daily_returns).cumprod()
    navs_normalizados = (navs_normalizados / navs_normalizados.iloc[0]) * 100

    # Gráfico de Rentabilidad
    st.subheader("📈 Evolución normalizada")
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in navs_normalizados.columns:
        ax.plot(navs_normalizados.index, navs_normalizados[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
    if portfolio and portfolio.nav is not None:
         ax.plot(portfolio.nav.index, portfolio.nav, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
    ax.legend(); ax.grid(True, linestyle='--', alpha=0.6)
    st.pyplot(fig)

    # Gráfico de Volatilidad
    st.subheader("📊 Volatilidad rolling (30d)")
    rolling_vol = daily_returns.rolling(30).std() * (252**0.5) * 100
    fig, ax = plt.subplots(figsize=(10, 5))
    for col in rolling_vol.columns:
        ax.plot(rolling_vol.index, rolling_vol[col], label=mapa_isin_nombre.get(col, col), alpha=0.6)
    if portfolio and portfolio.daily_returns is not None:
        portfolio_vol = portfolio.daily_returns.rolling(30).std() * (252**0.5) * 100
        ax.plot(portfolio_vol.index, portfolio_vol, label="💼 Mi Cartera", color="black", linewidth=2.5, linestyle="--")
    ax.legend(); ax.grid(True, linestyle='--', alpha=0.6)
    st.pyplot(fig)

    # Gráfico de Riesgo vs. Retorno
    if not df_metrics.empty:
        st.subheader("🎯 Riesgo vs. Retorno")
        fig, ax = plt.subplots(figsize=(10, 6))
        cartera_metrics = df_metrics[df_metrics["nombre"] == "💼 Mi Cartera"]
        fondos_metrics = df_metrics[df_metrics["nombre"] != "💼 Mi Cartera"]
        sns.scatterplot(data=fondos_metrics, x="volatility_ann_%", y="annualized_return_%", s=100, alpha=0.7, ax=ax, label="Fondos Individuales")
        for i, row in fondos_metrics.iterrows():
            ax.text(row["volatility_ann_%"]+0.1, row["annualized_return_%"], row["nombre"], fontsize=9)
        if not cartera_metrics.empty:
            ax.scatter(cartera_metrics["volatility_ann_%"], cartera_metrics["annualized_return_%"], marker='*', s=300, c='red', zorder=5, label="Mi Cartera")
        ax.set_xlabel("Volatilidad Anualizada (%)"); ax.set_ylabel("Rentabilidad Anualizada (%)"); ax.grid(True, linestyle=':', alpha=0.6); ax.legend()
        st.pyplot(fig)
        
    # Gráfico de Correlaciones
    if len(st.session_state.cartera_isines) > 1:
        st.subheader("🔗 Correlación de la Cartera")
        corr_matrix = daily_returns.corr()
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", ax=ax, annot_kws={"size": 8})
        st.pyplot(fig)

def render_update_panel(isines, mapa_isin_nombre):
    """Muestra el panel para forzar la actualización de los datos."""
    st.markdown("---")
    st.subheader("📅 Estado de actualización de los fondos")
    
    for isin in isines:
        c1, c2, c3 = st.columns([4, 2, 2])
        c1.write(mapa_isin_nombre.get(isin, isin))
        
        file_path = Path("fondos_data") / f"{isin}.csv"
        if file_path.exists():
            last_date = pd.read_csv(file_path, usecols=['date']).iloc[-1, 0]
            c2.write(f"Último dato: {last_date}")
        else:
            c2.write("No descargado")

        if c3.button("🔄 Actualizar", key=f"update_{isin}"):
            st.session_state.force_update_isin = isin
            st.rerun()