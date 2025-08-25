import pandas as pd
import numpy as np

def calcular_metricas_desde_rentabilidades(daily_returns: pd.Series) -> dict:
    """
    Calcula las métricas clave. Usa cálculos aritméticos más estables
    para la anualización de la rentabilidad y el Sharpe.
    """
    if daily_returns is None or daily_returns.empty or len(daily_returns) < 2:
        return {
            "annualized_return_%": np.nan,
            "volatility_ann_%": np.nan,
            "sharpe_ann": np.nan,
            "max_drawdown_%": np.nan,
        }
    
    # --- Cálculos Anualizados ---
    annualization_factor = 252
    
    # 1. Volatilidad Anualizada
    vol_ann = daily_returns.std() * np.sqrt(annualization_factor)
    
    # 2. Rentabilidad Anualizada (aritmética simple, más robusta para todos los periodos)
    mean_daily_return = daily_returns.mean()
    return_ann = mean_daily_return * annualization_factor

    # --- MÉTRICAS ---
    metrics = {}
    metrics["annualized_return_%"] = return_ann * 100
    metrics["volatility_ann_%"] = vol_ann * 100
    
    # 3. Ratio Sharpe (clásico: rentabilidad / volatilidad)
    if vol_ann > 0:
        # Usamos los valores anualizados que ya calculamos. Asumimos risk-free = 0.
        metrics["sharpe_ann"] = return_ann / vol_ann
    else:
        metrics["sharpe_ann"] = np.nan
    
    # 4. Drawdown Máximo
    nav_series = (1 + daily_returns).cumprod()
    rolling_max = nav_series.cummax()
    drawdowns = (nav_series / rolling_max - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min() if not drawdowns.empty else np.nan

    return metrics