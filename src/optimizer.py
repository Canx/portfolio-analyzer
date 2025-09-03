# src/optimizer.py

import pandas as pd
import riskfolio as rp
import warnings
import streamlit as st

# Suprimimos avisos de la librería para una salida más limpia
warnings.filterwarnings("ignore")


def optimize_portfolio(
    daily_returns: pd.DataFrame, model: str = "HRP", risk_measure: str = "MV"
) -> pd.Series | None:
    """
    Función definitiva para optimizar una cartera usando Riskfolio-Lib.
    Ahora acepta un parámetro 'risk_measure' para el modelo HRP.
    """
    if daily_returns.empty or len(daily_returns) < 2:
        return None

    weights_df = None
    try:
        if model == "HRP":
            port = rp.HCPortfolio(returns=daily_returns)

            # --- LÍNEA MODIFICADA ---
            # Usamos el parámetro 'risk_measure' que nos pasan
            weights_df = port.optimization(
                model="HRP",
                codependence="pearson",
                rm=risk_measure,  # <-- Aquí está el cambio
                linkage="ward",
            )

        elif model in ["MV", "MSR"]:
            # ... (esta parte no cambia)
            port = rp.Portfolio(returns=daily_returns)
            port.assets_stats(method_mu="hist", method_cov="hist")
            port.fix_cov_matrix(method="full")

            if model == "MV":
                weights_df = port.optimization(model="MV", obj="MinRisk")
            elif model == "MSR":
                weights_df = port.optimization(model="Classic", obj="MaxSharpe")

        else:
            raise ValueError(f"Modelo '{model}' no reconocido.")

        if weights_df is not None and not weights_df.empty:
            return weights_df["weights"]
        else:
            return None

    except Exception as e:
        st.error(f"Error durante la optimización con el modelo {model}: {e}")
        return None
