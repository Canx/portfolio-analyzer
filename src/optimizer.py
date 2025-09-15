# src/optimizer.py

import pandas as pd
import riskfolio as rp
import warnings
import streamlit as st

warnings.filterwarnings("ignore")

def optimize_portfolio(daily_returns: pd.DataFrame, model: str = 'HRP', risk_measure: str = 'MV', target_return: float = 0.0) -> pd.Series | None:
    """
    Función definitiva para optimizar una cartera usando Riskfolio-Lib.
    Utiliza la clase correcta (Portfolio o HCPortfolio) y los parámetros
    correctos para el modelo de optimización.
    """
    if daily_returns.empty or len(daily_returns) < 2:
        return None

    weights_df = None
    try:
        if model == 'HRP':
            port = rp.HCPortfolio(returns=daily_returns)
            weights_df = port.optimization(
                model='HRP',
                codependence='pearson',
                rm=risk_measure,
                linkage='ward'
            )
        
        elif model in ['MV', 'MSR', 'TARGET_RET']:
            port = rp.Portfolio(returns=daily_returns)
            port.assets_stats(method_mu='hist', method_cov='ledoit')
            
            if model == 'MV':
                weights_df = port.optimization(
                    model='Classic',
                    rm='MV',
                    obj='MinRisk'
                )
            elif model == 'MSR':
                weights_df = port.optimization(
                    model='Classic',
                    rm='MV',
                    obj='Sharpe',
                    rf=0.0
                )
            elif model == 'TARGET_RET':
                # Riskfolio espera el retorno objetivo anualizado y en formato decimal
                target_return_decimal_ann = target_return / 100
                weights_df = port.optimization(
                    model='Classic',
                    rm='MV',           # Minimizamos la volatilidad
                    obj='MinRisk',      # El objetivo es minimizar el riesgo
                    t_ret=target_return_decimal_ann # Pasamos el retorno objetivo
                )
        
        else:
            raise ValueError(f"Modelo '{model}' no reconocido.")

        if weights_df is not None and not weights_df.empty:
            return weights_df['weights']
        else:
            return None

    except Exception as e:
        st.error(f"Error durante la optimización con el modelo {model}: {e}")
        return None

def calculate_efficient_frontier(daily_returns: pd.DataFrame, points: int = 20) -> pd.DataFrame | None:
    """
    Calcula los puntos de la frontera eficiente.
    Versión final que usa un estimador robusto y extrae los datos correctamente del índice.
    """
    if daily_returns.empty or len(daily_returns.columns) < 2:
        return None
    
    try:
        port = rp.Portfolio(returns=daily_returns)
        
        port.assets_stats(method_mu='hist', method_cov='ledoit')

        frontier = port.efficient_frontier(model='Classic', points=points)
        
        if frontier is not None and not frontier.empty:
            frontier = frontier.reset_index()
            
            frontier.rename(columns={'Std. Dev.': 'volatility_ann_%', 'Returns': 'annualized_return_%'}, inplace=True)
            
            frontier['volatility_ann_%'] *= 100
            frontier['annualized_return_%'] *= 100
            
            return frontier
        else:
            return None
            
    except Exception as e:
        print(f"Error calculando la frontera eficiente: {e}")
        return None