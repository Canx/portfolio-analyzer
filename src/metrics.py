import pandas as pd
import numpy as np


import pandas as pd
import numpy as np


def calcular_metricas_desde_rentabilidades(daily_returns: pd.Series) -> dict:
    """
    Calcula las métricas clave, incluyendo el Ratio de Sortino.
    """
    if daily_returns is None or daily_returns.empty or len(daily_returns) < 2:
        return {
            "annualized_return_%": np.nan,
            "volatility_ann_%": np.nan,
            "sharpe_ann": np.nan,
            "max_drawdown_%": np.nan,
            "sortino_ann": np.nan, # <-- NUEVO
        }

    # --- Cálculos Anualizados ---
    annualization_factor = 252
    mean_daily_return = daily_returns.mean()
    return_ann = mean_daily_return * annualization_factor

    # 1. Volatilidad Anualizada (para el Sharpe)
    vol_ann = daily_returns.std() * np.sqrt(annualization_factor)

    # --- NUEVO: Cálculo de la Volatilidad Negativa (para el Sortino) ---
    negative_returns = daily_returns[daily_returns < 0]
    downside_deviation = negative_returns.std() * np.sqrt(annualization_factor)

    # --- MÉTRICAS ---
    metrics = {}
    metrics["annualized_return_%"] = return_ann * 100
    metrics["volatility_ann_%"] = vol_ann * 100

    # 3. Ratio Sharpe
    if vol_ann > 0:
        metrics["sharpe_ann"] = return_ann / vol_ann
    else:
        metrics["sharpe_ann"] = np.nan
        
    # --- NUEVO: Ratio Sortino ---
    if downside_deviation > 0:
        metrics["sortino_ann"] = return_ann / downside_deviation
    else:
        # Si no hay volatilidad negativa, el ratio es teóricamente infinito.
        # Mostramos NaN o un valor muy alto, según preferencia.
        metrics["sortino_ann"] = np.nan

    # 4. Drawdown Máximo
    nav_series = (1 + daily_returns).cumprod()
    rolling_max = nav_series.cummax()
    drawdowns = (nav_series / rolling_max - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min() if not drawdowns.empty else np.nan

    return metrics
