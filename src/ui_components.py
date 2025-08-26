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
import plotly.express as px
import plotly.graph_objects as go


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
# En src/ui_components.py

# ... (Las importaciones y la función ajustar_pesos_direccional no cambian) ...

def render_sidebar(mapa_nombre_isin, mapa_isin_nombre):
    """
    Renderiza la barra lateral. El formulario ahora devuelve los datos del nuevo fondo
    en lugar de escribir directamente en el fichero.
    """
    with st.sidebar:
        st.header("Configuración del Análisis")
        horizonte = st.selectbox("Horizonte temporal", ["3m", "6m", "YTD", "1y", "3y", "5y", "max"], key="horizonte")
        st.markdown("---")
        st.header("💼 Mi Cartera")
        # ... (La lógica de gestión de cartera no cambia) ...
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
        pesos_previos = st.session_state.pesos.copy()
        for isin in list(st.session_state.cartera_isines):
            cols = st.columns([5, 2, 1])
            cols[0].markdown(f"**{mapa_isin_nombre.get(isin, isin)}**")
            st.session_state.pesos[isin] = cols[1].slider("Peso %", 0, 100, st.session_state.pesos.get(isin, 0), 1, key=f"peso_{isin}")
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
            st.session_state.pesos = ajustar_pesos_direccional(st.session_state.cartera_isines, st.session_state.pesos, isin_modificado, pesos_previos)
            st.rerun()
        if st.session_state.cartera_isines:
            total_peso = sum(st.session_state.pesos.values())
            st.metric("Suma Total", f"{total_peso}%")
        st.markdown("---")
        st.subheader("⚖️ Optimización (HRP)")
        run_hrp_optimization = st.button("🚀 Optimizar Cartera")

        # --- SECCIÓN MODIFICADA ---
        st.markdown("---")
        new_fund_to_add = None  # Variable que devolveremos
        with st.expander("➕ Añadir nuevo fondo al catálogo"):
            with st.form("form_add_fund"):
                new_isin = st.text_input("ISIN del nuevo fondo").strip().upper()
                new_name = st.text_input("Nombre del nuevo fondo").strip()
                submitted = st.form_submit_button("Añadir")

                if submitted:
                    if not new_isin or not new_name:
                        st.error("Debes rellenar tanto el ISIN como el nombre.")
                    else:
                        # En lugar de escribir el fichero, preparamos los datos para devolverlos
                        new_fund_to_add = {"isin": new_isin, "name": new_name}
        
    # Devolvemos la nueva variable junto a las demás
    return horizonte, run_hrp_optimization, new_fund_to_add


def render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre):
    """Renderiza el contenido principal. Usa Plotly para gráficos interactivos."""
    st.header("Análisis de la Cartera")

    # --- NUEVO: GRÁFICO DE TARTA PARA LA DISTRIBUCIÓN DE LA CARTERA ---
    pesos = st.session_state.get('pesos', {})
    
    # Solo mostrar el gráfico si hay fondos con peso en la cartera
    if pesos and sum(pesos.values()) > 0:
        st.subheader("📊 Distribución de la Cartera")
        df_pie = pd.DataFrame(list(pesos.items()), columns=['ISIN', 'Peso'])
        # Añadimos los nombres de los fondos para que las etiquetas sean claras
        df_pie['Fondo'] = df_pie['ISIN'].map(mapa_isin_nombre)
        
        # Creamos el gráfico de donut con Plotly Express
        fig_pie = px.pie(df_pie,
                         names='Fondo',
                         values='Peso',
                         title='Composición Actual de la Cartera',
                         hole=.3) # El 'hole' lo convierte en un gráfico de donut
        
        fig_pie.update_traces(textposition='inside', textinfo='percent+label', pull=[0.05]*len(df_pie))
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- TABLA DE MÉTRICAS (no cambia) ---
    st.subheader(f"📑 Métricas para el horizonte: {st.session_state.horizonte}")
    if not df_metrics.empty:
        df_display = df_metrics.rename(columns={
            "nombre": "Nombre", "annualized_return_%": "Rent. Anual (%)",
            "volatility_ann_%": "Volatilidad Anual (%)", "sharpe_ann": "Ratio Sharpe",
            "max_drawdown_%": "Caída Máxima (%)"
        }).set_index("Nombre")[["Rent. Anual (%)", "Volatilidad Anual (%)", "Ratio Sharpe", "Caída Máxima (%)"]]
        st.dataframe(df_display.style.format("{:.2f}"))
    
    # --- GRÁFICOS INTERACTIVOS CON PLOTLY ---
    if daily_returns.empty: return

    # --- 1. Gráfico de Rentabilidad Normalizada (no cambia) ---
    st.subheader("📈 Evolución normalizada")
    navs_normalizados = (1 + daily_returns).cumprod()
    navs_normalizados = (navs_normalizados / navs_normalizados.iloc[0]) * 100
    df_plot = navs_normalizados.rename(columns=mapa_isin_nombre).reset_index()
    df_plot = df_plot.melt(id_vars="date", var_name="Fondo", value_name="Valor Normalizado")
    fig_rent = px.line(df_plot, x="date", y="Valor Normalizado", color="Fondo", title="Evolución Normalizada de la Cartera")
    if portfolio and portfolio.nav is not None:
        fig_rent.add_trace(go.Scatter(x=portfolio.nav.index, y=portfolio.nav.values, mode='lines', name='💼 Mi Cartera', line=dict(color='black', width=3, dash='dash')))
    st.plotly_chart(fig_rent, use_container_width=True)

    # --- 2. Gráfico de Volatilidad Rolling (no cambia) ---
    st.subheader("📊 Volatilidad rolling (30d)")
    rolling_vol = daily_returns.rolling(30).std() * (252**0.5) * 100
    df_vol_plot = rolling_vol.rename(columns=mapa_isin_nombre).reset_index()
    df_vol_plot = df_vol_plot.melt(id_vars="date", var_name="Fondo", value_name="Volatilidad Anualizada (%)")
    fig_vol = px.line(df_vol_plot, x="date", y="Volatilidad Anualizada (%)", color="Fondo", title="Volatilidad Anualizada (Rolling 30 días)")
    if portfolio and portfolio.daily_returns is not None:
        portfolio_vol = portfolio.daily_returns.rolling(30).std() * (252**0.5) * 100
        fig_vol.add_trace(go.Scatter(x=portfolio_vol.index, y=portfolio_vol.values, mode='lines', name='💼 Mi Cartera', line=dict(color='black', width=3, dash='dash')))
    st.plotly_chart(fig_vol, use_container_width=True)
    
    # --- 3. Gráfico de Riesgo vs. Retorno (SECCIÓN CORREGIDA) ---
    if not df_metrics.empty:
        st.subheader("🎯 Riesgo vs. Retorno")
        fondos_metrics = df_metrics[df_metrics["nombre"] != "💼 Mi Cartera"]
        
        fig_risk = px.scatter(fondos_metrics,
                              x="volatility_ann_%",
                              y="annualized_return_%",
                              text="nombre",
                              hover_name="nombre",
                              title="Riesgo vs. Retorno de los Fondos")
        
        # --- AQUÍ ESTÁ EL ARREGLO: 'top center' con espacio ---
        fig_risk.update_traces(textposition='top center')
        
        cartera_metrics = df_metrics[df_metrics["nombre"] == "💼 Mi Cartera"]
        if not cartera_metrics.empty:
            fig_risk.add_trace(go.Scatter(x=cartera_metrics["volatility_ann_%"],
                                          y=cartera_metrics["annualized_return_%"],
                                          mode='markers',
                                          marker=dict(color='red', size=15, symbol='star'),
                                          name='💼 Mi Cartera'))

        fig_risk.update_layout(xaxis_title="Volatilidad Anualizada (%)", yaxis_title="Rentabilidad Anualizada (%)")
        st.plotly_chart(fig_risk, use_container_width=True)

    # --- 4. Gráfico de Correlaciones (no cambia) ---
    if len(st.session_state.cartera_isines) > 1:
        st.subheader("🔗 Correlación de la Cartera")
        corr_matrix = daily_returns.corr()
        corr_matrix.columns = [mapa_isin_nombre.get(c, c) for c in corr_matrix.columns]
        corr_matrix.index = [mapa_isin_nombre.get(i, i) for i in corr_matrix.index]
        fig_corr = px.imshow(corr_matrix, text_auto=True, aspect="auto", color_continuous_scale='RdBu_r', range_color=[-1, 1], title="Matriz de Correlación")
        st.plotly_chart(fig_corr, use_container_width=True)
        

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