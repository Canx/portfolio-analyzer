import pandas as pd
import numpy as np


import pandas as pd
import numpy as np


# src/metrics.py

import pandas as pd
import numpy as np


def calcular_metricas_desde_rentabilidades(daily_returns: pd.Series) -> dict:
    """
    Calcula las métricas clave, incluyendo la rentabilidad acumulada.
    """
    if daily_returns is None or daily_returns.empty or len(daily_returns) < 2:
        return {
            "annualized_return_%": np.nan,
            "cumulative_return_%": np.nan, # <-- NUEVO
            "volatility_ann_%": np.nan,
            "sharpe_ann": np.nan,
            "max_drawdown_%": np.nan,
            "sortino_ann": np.nan,
        }

    # --- Cálculos ---
    annualization_factor = 252
    mean_daily_return = daily_returns.mean()
    return_ann = mean_daily_return * annualization_factor

    # --- NUEVO: Rentabilidad Acumulada ---
    # Reconstruimos el NAV para obtener el rendimiento total del periodo exacto
    nav_series = (1 + daily_returns).cumprod()
    cumulative_return = (nav_series.iloc[-1] / nav_series.iloc[0] - 1)

    # Volatilidad
    vol_ann = daily_returns.std() * np.sqrt(annualization_factor)
    negative_returns = daily_returns[daily_returns < 0]
    downside_deviation = negative_returns.std() * np.sqrt(annualization_factor)

    # --- MÉTRICAS ---
    metrics = {}
    metrics["annualized_return_%"] = return_ann * 100
    metrics["cumulative_return_%"] = cumulative_return * 100 # <-- NUEVO
    metrics["volatility_ann_%"] = vol_ann * 100

    # Ratios
    if vol_ann > 0:
        metrics["sharpe_ann"] = return_ann / vol_ann
    else:
        metrics["sharpe_ann"] = np.nan
        
    if downside_deviation > 0:
        metrics["sortino_ann"] = return_ann / downside_deviation
    else:
        metrics["sortino_ann"] = np.nan

    # Drawdown Máximo
    drawdowns = (nav_series / nav_series.cummax() - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min() if not drawdowns.empty else np.nan

    return metrics
