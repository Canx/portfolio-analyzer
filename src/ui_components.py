# src/ui_components.py

import streamlit as st
import pandas as pd
import json
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go

# --- HELPERS DE UI ---
def ajustar_pesos_direccional(isines_ordenados, pesos_dict, isin_modificado, pesos_previos):
    """
    Ajusta los pesos del resto de activos.
    """
    if not isines_ordenados or len(isines_ordenados) <= 1:
        return
    
    # Asegurarse de que el isin modificado está en la lista para evitar errores
    if isin_modificado not in isines_ordenados:
        return

    index_modificado = isines_ordenados.index(isin_modificado)
    delta = pesos_dict[isin_modificado] - pesos_previos.get(isin_modificado, 0)
    isines_para_ajustar = isines_ordenados[index_modificado + 1:]
    if not isines_para_ajustar:
        isines_para_ajustar = isines_ordenados[:index_modificado]
    if not isines_para_ajustar:
        return
    
    isines_ajustables = [i for i in isines_para_ajustar if (delta > 0 and pesos_dict[i] > 0) or (delta < 0 and pesos_dict[i] < 100)]
    if not isines_ajustables:
        isines_ajustables = [i for i in isines_ordenados if i != isin_modificado]
        if not isines_ajustables: return
        
    suma_ajustable = sum(pesos_dict[i] for i in isines_ajustables)
    for isin in isines_ajustables:
        ratio = pesos_dict[isin] / suma_ajustable if suma_ajustable > 0 else 1 / len(isines_ajustables)
        pesos_dict[isin] -= delta * ratio
    for isin in isines_ajustables:
        pesos_dict[isin] = max(0, min(100, int(round(pesos_dict[isin]))))
    suma_actual = sum(pesos_dict.values())
    if suma_actual != 100 and isines_ajustables:
        pesos_dict[isines_ajustables[0]] += 100 - suma_actual

# En src/ui_components.py

# ... (Las importaciones y la función ajustar_pesos_direccional no cambian) ...

def render_sidebar(mapa_nombre_isin, mapa_isin_nombre):
    """
    Renderiza la barra lateral. Corregido el StreamlitAPIException al crear carteras.
    """
    with st.sidebar:
        st.header("Configuración del Análisis")
        horizonte = st.selectbox("Horizonte temporal", ["1m", "3m", "6m", "YTD", "1y", "3y", "5y", "max"], key="horizonte")
        st.markdown("---")

        st.header("🗂️ Gestor de Carteras")
        lista_carteras = list(st.session_state.carteras.keys())
        
        # --- LÓGICA DEL SELECTBOX MODIFICADA ---
        # Guardamos el índice actual para que el desplegable no se "resete" visualmente
        try:
            indice_actual = lista_carteras.index(st.session_state.cartera_activa)
        except (ValueError, AttributeError):
            indice_actual = 0
            
        # Quitamos el argumento 'key' y gestionamos el cambio manualmente
        cartera_seleccionada = st.selectbox(
            "Cartera Activa",
            lista_carteras,
            index=indice_actual
        )
        
        # Si el usuario cambia la selección, actualizamos el estado y recargamos
        if cartera_seleccionada != st.session_state.cartera_activa:
            st.session_state.cartera_activa = cartera_seleccionada
            st.rerun()

        with st.expander("Opciones de Gestión"):
            with st.form("form_create_portfolio"):
                new_portfolio_name = st.text_input("Nombre de la nueva cartera")
                submitted_create = st.form_submit_button("Crear Cartera")
                if submitted_create and new_portfolio_name:
                    if new_portfolio_name in st.session_state.carteras:
                        st.warning("Ya existe una cartera con ese nombre.")
                    else:
                        st.session_state.carteras[new_portfolio_name] = {"pesos": {}}
                        # Ahora este cambio es seguro porque el selectbox no tiene el control exclusivo
                        st.session_state.cartera_activa = new_portfolio_name
                        st.rerun()

            if st.session_state.cartera_activa:
                if st.button(f"🗑️ Borrar '{st.session_state.cartera_activa}'", type="primary"):
                    del st.session_state.carteras[st.session_state.cartera_activa]
                    st.session_state.cartera_activa = next(iter(st.session_state.carteras), None)
                    st.rerun()
        
        st.markdown("---")

        # ... (El resto de la función sigue exactamente igual) ...
        run_optimization = False
        modelo_optimización = None
        risk_measure = None
        if st.session_state.cartera_activa:
            st.header(f"💼 Composición de '{st.session_state.cartera_activa}'")
            
            pesos_actuales = st.session_state.carteras[st.session_state.cartera_activa]['pesos']
            pesos_previos = pesos_actuales.copy()
            
            isines_ordenados = sorted(pesos_actuales.keys(), key=lambda isin: pesos_actuales.get(isin, 0), reverse=True)

            candidatos = [n for n in mapa_nombre_isin.keys() if mapa_nombre_isin[n] not in isines_ordenados]
            add_sel = st.selectbox("Añadir fondo a la cartera", ["—"] + candidatos, index=0, key=f"add_fund_{st.session_state.cartera_activa}")
            if add_sel != "—" and st.button("➕ Añadir"):
                nuevo_isin = mapa_nombre_isin[add_sel]
                pesos_actuales[nuevo_isin] = 0
                st.rerun()

            for isin in isines_ordenados:
                col_name, col_minus, col_slider, col_plus, col_del = st.columns([4, 1, 4, 1, 1])
                with col_name:
                    st.markdown(f"**{mapa_isin_nombre.get(isin, isin)}**")
                with col_minus:
                    if st.button("➖", key=f"minus_{st.session_state.cartera_activa}_{isin}"):
                        if pesos_actuales[isin] > 0: pesos_actuales[isin] -= 1
                with col_slider:
                    pesos_actuales[isin] = st.slider("Peso %", 0, 100, pesos_actuales.get(isin, 0), 1, key=f"peso_{st.session_state.cartera_activa}_{isin}", label_visibility="collapsed")
                with col_plus:
                    if st.button("➕", key=f"plus_{st.session_state.cartera_activa}_{isin}"):
                        if pesos_actuales[isin] < 100: pesos_actuales[isin] += 1
                with col_del:
                    if st.button("🗑️", key=f"remove_{st.session_state.cartera_activa}_{isin}"):
                        del pesos_actuales[isin]
                        st.rerun()

            isin_modificado = None
            for isin, peso in pesos_actuales.items():
                if peso != pesos_previos.get(isin, 0):
                    isin_modificado = isin
                    break
            
            if isin_modificado:
                ajustar_pesos_direccional(
                    isines_ordenados, pesos_actuales, isin_modificado, pesos_previos
                )
                st.rerun()
            
            if pesos_actuales:
                st.metric("Suma Total", f"{sum(pesos_actuales.values())}%")

            st.markdown("---")
            st.subheader("⚖️ Optimización")
            modelo_optimización = st.selectbox(
                "Selecciona un modelo", ["HRP", "MV", "MSR"],
                format_func=lambda x: {"HRP": "Hierarchical Risk Parity", "MV": "Mínima Volatilidad", "MSR": "Máximo Ratio de Sharpe"}[x],
                key=f"model_{st.session_state.cartera_activa}"
            )
            risk_measure = 'MV'
            if modelo_optimización == 'HRP':
                rms_disponibles = ['MV', 'MAD', 'MSV', 'VaR', 'CVaR', 'CDaR']
                rms_nombres = {'MV': 'Varianza', 'MAD': 'Desviación Absoluta', 'MSV': 'Semi Varianza', 'VaR': 'Valor en Riesgo', 'CVaR': 'VaR Condicional', 'CDaR': 'Drawdown Condicional'}
                risk_measure = st.selectbox("Medida de Riesgo (para HRP)", rms_disponibles, format_func=lambda x: rms_nombres.get(x, x), key=f"rm_{st.session_state.cartera_activa}")
            
            run_optimization = st.button("🚀 Optimizar Cartera")
        else:
            st.warning("Crea o selecciona una cartera para continuar.")
        
    return horizonte, run_optimization, modelo_optimización, risk_measure



def render_main_content(df_metrics, daily_returns, portfolio, mapa_isin_nombre):
    """
    Renderiza el contenido principal.
    Añade una comprobación para mostrar un aviso si no hay suficientes datos para los gráficos.
    """
    st.header("Análisis de la Cartera")

    # Gráfico de Tarta (no cambia)
    pesos = (
        st.session_state.get("carteras", {})
        .get(st.session_state.get("cartera_activa"), {})
        .get("pesos", {})
    )
    if pesos and sum(pesos.values()) > 0:
        st.subheader("📊 Distribución de la Cartera")
        df_pie = pd.DataFrame(list(pesos.items()), columns=["ISIN", "Peso"])
        df_pie["Fondo"] = df_pie["ISIN"].map(mapa_isin_nombre)
        fig_pie = px.pie(
            df_pie,
            names="Fondo",
            values="Peso",
            title="Composición Actual de la Cartera",
            hole=0.3,
        )
        fig_pie.update_traces(
            textposition="inside", textinfo="percent+label", pull=[0.05] * len(df_pie)
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # Tabla de Métricas (no cambia)
    st.subheader(f"📑 Métricas para el horizonte: {st.session_state.horizonte}")
    if not df_metrics.empty:
        df_display = df_metrics.rename(
            columns={
                "nombre": "Nombre",
                "annualized_return_%": "Rent. Anual (%)",
                "volatility_ann_%": "Volatilidad Anual (%)",
                "sharpe_ann": "Ratio Sharpe",
                "max_drawdown_%": "Caída Máxima (%)",
            }
        ).set_index("Nombre")[
            [
                "Rent. Anual (%)",
                "Volatilidad Anual (%)",
                "Ratio Sharpe",
                "Caída Máxima (%)",
            ]
        ]
        st.dataframe(df_display.style.format("{:.2f}"))

    st.markdown("---")

    # --- LÓGICA DE GRÁFICOS CORREGIDA ---
    # Comprobamos si hay al menos 2 filas de datos para poder calcular rentabilidades y volatilidad.
    if daily_returns.empty or len(daily_returns) < 2:
        st.warning(
            "No hay suficientes datos históricos en el periodo seleccionado para generar los gráficos."
        )
        st.info(
            "💡 Prueba a seleccionar un horizonte temporal más largo (ej. '1y' o 'max')."
        )
    else:
        # Si hay datos suficientes, mostramos todos los gráficos.
        # Gráfico de Rentabilidad
        st.subheader("📈 Evolución normalizada")
        navs_normalizados = (1 + daily_returns).cumprod()
        navs_normalizados = (navs_normalizados / navs_normalizados.iloc[0]) * 100
        df_plot = navs_normalizados.rename(columns=mapa_isin_nombre).reset_index()
        df_plot = df_plot.melt(
            id_vars="date", var_name="Fondo", value_name="Valor Normalizado"
        )
        fig_rent = px.line(
            df_plot,
            x="date",
            y="Valor Normalizado",
            color="Fondo",
            title="Evolución Normalizada de la Cartera",
        )
        if portfolio and portfolio.nav is not None:
            fig_rent.add_trace(
                go.Scatter(
                    x=portfolio.nav.index,
                    y=portfolio.nav.values,
                    mode="lines",
                    name="💼 Mi Cartera",
                    line=dict(color="black", width=3, dash="dash"),
                )
            )
        st.plotly_chart(fig_rent, use_container_width=True)

        # Gráfico de Volatilidad
        st.subheader("📊 Volatilidad rolling (30d)")
        rolling_vol = daily_returns.rolling(30).std() * (252**0.5) * 100
        df_vol_plot = rolling_vol.rename(columns=mapa_isin_nombre).reset_index()
        df_vol_plot = df_vol_plot.melt(
            id_vars="date", var_name="Fondo", value_name="Volatilidad Anualizada (%)"
        )
        fig_vol = px.line(
            df_vol_plot,
            x="date",
            y="Volatilidad Anualizada (%)",
            color="Fondo",
            title="Volatilidad Anualizada (Rolling 30 días)",
        )
        if portfolio and portfolio.daily_returns is not None:
            portfolio_vol = portfolio.daily_returns.rolling(30).std() * (252**0.5) * 100
            fig_vol.add_trace(
                go.Scatter(
                    x=portfolio_vol.index,
                    y=portfolio_vol.values,
                    mode="lines",
                    name="💼 Mi Cartera",
                    line=dict(color="black", width=3, dash="dash"),
                )
            )
        st.plotly_chart(fig_vol, use_container_width=True)

        # Gráfico de Riesgo vs. Retorno
        if not df_metrics.empty:
            st.subheader("🎯 Riesgo vs. Retorno")
            fondos_metrics = df_metrics[~df_metrics["nombre"].str.startswith("💼")]
            fig_risk = px.scatter(
                fondos_metrics,
                x="volatility_ann_%",
                y="annualized_return_%",
                text="nombre",
                hover_name="nombre",
                title="Riesgo vs. Retorno de los Fondos",
            )
            fig_risk.update_traces(textposition="top center")
            cartera_metrics = df_metrics[df_metrics["nombre"].str.startswith("💼")]
            if not cartera_metrics.empty:
                fig_risk.add_trace(
                    go.Scatter(
                        x=cartera_metrics["volatility_ann_%"],
                        y=cartera_metrics["annualized_return_%"],
                        mode="markers",
                        marker=dict(color="red", size=15, symbol="star"),
                        name=cartera_metrics.iloc[0]["nombre"],
                    )
                )
            fig_risk.update_layout(
                xaxis_title="Volatilidad Anualizada (%)",
                yaxis_title="Rentabilidad Anualizada (%)",
            )
            st.plotly_chart(fig_risk, use_container_width=True)


def render_update_panel(isines, mapa_isin_nombre):
    """Muestra el panel para forzar la actualización de los datos."""
    st.markdown("---")
    st.subheader("📅 Estado de actualización de los fondos")

    for isin in isines:
        c1, c2, c3 = st.columns([4, 2, 2])
        c1.write(mapa_isin_nombre.get(isin, isin))

        file_path = Path("fondos_data") / f"{isin}.csv"
        if file_path.exists():
            try:
                # --- AQUÍ ESTÁ EL ARREGLO ---
                # 1. Leemos solo la columna de fechas para que sea rápido.
                df_dates = pd.read_csv(file_path, usecols=["date"])
                # 2. Obtenemos el último valor de esa columna.
                last_date = df_dates.iloc[-1, 0]
                c2.write(f"Último dato: {last_date}")
            except (pd.errors.EmptyDataError, IndexError):
                c2.write("Fichero vacío")
        else:
            c2.write("No descargado")

        if c3.button("🔄 Actualizar", key=f"update_{isin}"):
            # 1. Forzamos la actualización de metadatos en fondos.json
            update_fund_details_in_config(isin)
            # 2. Forzamos la actualización del NAV (CSV)
            st.session_state.force_update_isin = isin
            # 3. Limpiamos toda la caché para recargar ambos ficheros y re-ejecutamos
            st.cache_data.clear()
            st.rerun()
