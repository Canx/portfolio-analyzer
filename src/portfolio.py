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
            self.weights = pd.Series({k: v / total_weight for k, v in weights.items()})

        # Asegurarse de que solo se usan los activos presentes en nav_data
        common_assets = self.weights.index.intersection(nav_data.columns)
        self.navs = nav_data[common_assets]
        self.weights = self.weights[common_assets]

    @property
    def daily_returns(self) -> pd.Series | None:
        """Calcula los retornos diarios ponderados de la cartera."""
        if self.weights.empty or self.navs.empty:
            return None
        
        asset_returns = self.navs.pct_change().dropna()
        
        # Alinear columnas antes de la multiplicación
        aligned_weights = self.weights.reindex(asset_returns.columns).fillna(0)
        
        portfolio_returns = asset_returns.mul(aligned_weights, axis=1).sum(axis=1)
        return portfolio_returns

    @property
    def nav(self) -> pd.Series | None:
        """Reconstruye el Valor Liquidativo (NAV) de la cartera."""
        returns = self.daily_returns
        if returns is None:
            return None
        
        # Normaliza el NAV para empezar en 100
        return (1 + returns).cumprod() * 100

    def calculate_metrics(self) -> dict:
        """Calcula las métricas de la cartera usando el módulo de métricas."""
        metrics = calcular_metricas_desde_rentabilidades(self.daily_returns)
        metrics["nombre"] = "💼 Mi Cartera"
        return metrics