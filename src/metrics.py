import pandas as pd
import numpy as np


import pandas as pd
import numpy as np


# src/metrics.py

import pandas as pd
import numpy as np


def calcular_metricas_desde_rentabilidades(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> dict:
    """
    Calcula las métricas clave, incluyendo la rentabilidad acumulada.
    """
    if daily_returns is None or daily_returns.empty or len(daily_returns) < 2:
        return {
            "annualized_return_%": np.nan,
            "cumulative_return_%": np.nan,
            "volatility_ann_%": np.nan,
            "sharpe_ann": np.nan,
            "max_drawdown_%": np.nan,
            "sortino_ann": np.nan,
            "calmar_ratio": np.nan,
        }

    # --- Cálculos ---
    annualization_factor = 252
    mean_daily_return = daily_returns.mean()
    return_ann = mean_daily_return * annualization_factor

    # --- Rentabilidad Acumulada ---
    nav_series = (1 + daily_returns).cumprod()
    cumulative_return = (nav_series.iloc[-1] / nav_series.iloc[0] - 1)

    # Volatilidad
    vol_ann = daily_returns.std() * np.sqrt(annualization_factor)
    
    # Downside Deviation (usando la tasa libre de riesgo como MAR)
    excess_returns = daily_returns - (risk_free_rate / annualization_factor)
    negative_excess_returns = excess_returns[excess_returns < 0]
    
    if len(negative_excess_returns) > 1:
        downside_deviation = negative_excess_returns.std() * np.sqrt(annualization_factor)
    else:
        downside_deviation = 0

    # --- MÉTRICAS ---
    metrics = {}
    metrics["annualized_return_%"] = return_ann * 100
    metrics["cumulative_return_%"] = cumulative_return * 100
    metrics["volatility_ann_%"] = vol_ann * 100

    # Ratios
    excess_return_ann = return_ann - risk_free_rate

    if vol_ann > 0:
        metrics["sharpe_ann"] = excess_return_ann / vol_ann
    else:
        metrics["sharpe_ann"] = np.nan
        
    if downside_deviation > 0:
        metrics["sortino_ann"] = excess_return_ann / downside_deviation
    elif excess_return_ann > 0: # If no downside deviation and positive excess returns, Sortino is very high
        metrics["sortino_ann"] = 1e9 # A very large number
    else:
        metrics["sortino_ann"] = 0 # If no downside deviation and non-positive excess returns, Sortino is 0

    # Drawdown Máximo
    drawdowns = (nav_series / nav_series.cummax() - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min() if not drawdowns.empty else np.nan

    # Calmar Ratio
    if metrics["max_drawdown_%"] != 0:
        metrics["calmar_ratio"] = metrics["annualized_return_%"] / abs(metrics["max_drawdown_%"])
    else:
        metrics["calmar_ratio"] = np.nan

    return metrics
