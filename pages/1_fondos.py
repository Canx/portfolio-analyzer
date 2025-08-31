import streamlit as st
import pandas as pd
import json
from pathlib import Path
import numpy as np

# Importamos las funciones que usamos en esta página
from src.data_manager import find_and_add_fund_by_isin, update_fund_details_in_config

st.set_page_config(
    page_title="Explorador de Fondos",
    page_icon="🔎",
    layout="wide"
)

@st.cache_data
def load_config(config_file="fondos.json"):
    path = Path(config_file)
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("fondos", [])

# --- Lógica de la Página ---

st.title("🔎 Explorador de Fondos del Catálogo")
st.write("Aquí puedes ver, filtrar, actualizar, añadir nuevos fondos al catálogo y añadirlos a tu cartera.")

with st.expander("➕ Añadir nuevo fondo al catálogo por ISIN"):
    with st.form("form_add_fund_explorer"):
        new_isin = st.text_input("Introduce un ISIN para buscarlo", placeholder="Ej: IE00B4L5Y983").strip().upper()
        submitted = st.form_submit_button("Buscar y Añadir")

        if submitted and new_isin:
            if find_and_add_fund_by_isin(new_isin):
                st.cache_data.clear()
                st.rerun()

fondos_config = load_config()

if not fondos_config:
    st.warning("Aún no has añadido ningún fondo a tu catálogo.")
    st.stop()

df = pd.DataFrame(fondos_config)
df['ter'] = pd.to_numeric(df['ter'], errors='coerce')

# --- Controles de Filtro en la Barra Lateral ---
st.sidebar.header("Filtros del Explorador")
gestoras = sorted(df["gestora"].dropna().unique())
selected_gestoras = st.sidebar.multiselect("Filtrar por Gestora", gestoras, default=[])
domicilios = sorted(df["domicilio"].dropna().unique())
selected_domicilios = st.sidebar.multiselect("Filtrar por Domicilio", domicilios, default=[])
max_ter_value = df['ter'].max() if not df['ter'].dropna().empty else 10.0
selected_max_ter = st.sidebar.slider(
    "TER Máximo (%)", 0.0, float(np.ceil(max_ter_value)),
    value=float(np.ceil(max_ter_value)), step=0.1
)
search_term = st.sidebar.text_input("Buscar por nombre")

# --- Lógica de Filtrado ---
df_filtered = df
if selected_gestoras:
    df_filtered = df_filtered[df_filtered["gestora"].isin(selected_gestoras)]
if selected_domicilios:
    df_filtered = df_filtered[df_filtered["domicilio"].isin(selected_domicilios)]
df_filtered = df_filtered[(df_filtered["ter"] <= selected_max_ter) | (df_filtered["ter"].isna())]
if search_term:
    df_filtered = df_filtered[df_filtered["nombre"].str.contains(search_term, case=False)]

st.markdown("---")

# --- Visualización de la Lista Dinámica con Botones ---
st.write(f"Mostrando **{len(df_filtered)}** de **{len(df)}** fondos.")

# Cabecera de la tabla - Añadimos una columna más
header_cols = st.columns((3, 2, 1, 1, 2, 1, 2, 2))
header_cols[0].markdown("**Nombre**")
header_cols[1].markdown("**ISIN**")
header_cols[2].markdown("**TER (%)**")
header_cols[3].markdown("**SRRI**")
header_cols[4].markdown("**Gestora**")
header_cols[5].markdown("**Domicilio**")
header_cols[6].markdown("**Refrescar Datos**")
header_cols[7].markdown("**Añadir a Cartera**")

# Iteramos sobre los fondos filtrados
for index, row in df_filtered.iterrows():
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns((3, 2, 1, 1, 2, 1, 2, 2))
    with col1:
        st.markdown(f"**{row.get('nombre', 'N/A')}**")
        st.caption(f"{row.get('nombre_legal', '')}")
    with col2:
        st.code(row.get('isin', 'N/A'))
    with col3:
        ter_value = row.get('ter')
        st.write(f"{ter_value:.2f}" if pd.notna(ter_value) else "N/A")
    with col4:
        st.write(f"{row.get('srri', 'N/A')}")
    with col5:
        st.write(row.get('gestora', 'N/A'))
    with col6:
        st.write(row.get('domicilio', 'N/A'))
    with col7:
        if st.button("🔄 Refrescar", key=f"update_explorer_{row['isin']}"):
            update_fund_details_in_config(row['isin'])
            st.session_state.force_update_isin = row['isin']
            st.cache_data.clear()
            st.rerun()
    
    # --- LÓGICA DEL NUEVO BOTÓN ---
    with col8:
        # Comprobamos si el fondo ya está en la cartera
        if row['isin'] in st.session_state.cartera_isines:
            st.success("En cartera ✔️")
        else:
            # Si no está, mostramos el botón de añadir
            if st.button("➕ Añadir", key=f"add_explorer_{row['isin']}"):
                # 1. Añadimos el ISIN a la lista de la cartera
                st.session_state.cartera_isines.append(row['isin'])

                # 2. Rebalanceamos los pesos de forma equitativa
                num_fondos = len(st.session_state.cartera_isines)
                peso_base = 100 // num_fondos
                st.session_state.pesos = {isin: peso_base for isin in st.session_state.cartera_isines}
                
                # 3. Asignamos el resto para que la suma sea 100
                if num_fondos > 0:
                    resto = 100 - sum(st.session_state.pesos.values())
                    st.session_state.pesos[st.session_state.cartera_isines[0]] += resto
                
                # 4. Mostramos una notificación y recargamos la página
                st.toast(f"'{row['nombre']}' añadido a la cartera!")
                st.rerun()