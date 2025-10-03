# src/portfolio.py

import pandas as pd
from .metrics import calcular_metricas_desde_rentabilidades

class Portfolio:
    """
    Representa una cartera de activos con pesos específicos.
    Espera un DataFrame de NAVs y un diccionario de pesos.
    """
    def __init__(self, nav_data: pd.DataFrame, weights: dict):
        # Normalizar pesos para que sumen 1
        total_weight = sum(weights.values())
        if total_weight == 0:
            self.weights = pd.Series(dtype=float)
        else:
            # Dividimos por el total (que es 100) para obtener pesos normalizados (0.5, 0.5)
            self.weights = pd.Series({k: v / total_weight for k, v in weights.items()})

        common_assets = self.weights.index.intersection(nav_data.columns)
        self.navs = nav_data[common_assets]
        self.weights = self.weights[common_assets]

    @property
    def daily_returns(self) -> pd.Series | None:
        """Calcula los retornos diarios ponderados de la cartera."""
        if self.weights.empty or self.navs.empty:
            return None
        
        asset_returns = self.navs.pct_change() # No usamos .dropna() aquí
        
        aligned_weights = self.weights.reindex(asset_returns.columns).fillna(0)
        
        portfolio_returns = asset_returns.mul(aligned_weights, axis=1).sum(axis=1)
        return portfolio_returns

    @property
    def nav(self) -> pd.Series | None:
        """Reconstruye el Valor Liquidativo (NAV) de la cartera."""
        returns = self.daily_returns
        if returns is None:
            return None
        
        # --- LÓGICA CORREGIDA ---
        # 1. Reemplazamos el primer NaN por 0, para que el valor inicial no cambie.
        returns.iloc[0] = 0
        
        # 2. Reconstruimos el NAV empezando desde 100.
        return (1 + returns).cumprod() * 100

    def calculate_metrics(self, risk_free_rate: float = 0.0) -> dict:
        """Calcula las métricas de la cartera usando el módulo de métricas."""
        # Nos aseguramos de no incluir el primer NaN/0 en el cálculo de métricas
        returns_for_metrics = self.daily_returns.dropna()
        metrics = calcular_metricas_desde_rentabilidades(returns_for_metrics, risk_free_rate=risk_free_rate)
        # El nombre ahora viene de fuera
        # metrics["nombre"] = "💼 Mi Cartera"
        return metrics
