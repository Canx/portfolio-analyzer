# src/optimizer.py

import pandas as pd
import riskfolio as rp
import warnings
import streamlit as st

warnings.filterwarnings("ignore")

def optimize_portfolio(daily_returns: pd.DataFrame, model: str = 'HRP', risk_measure: str = 'MV') -> pd.Series | None:
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
        
        elif model in ['MV', 'MSR']:
            port = rp.Portfolio(returns=daily_returns)
            port.assets_stats(method_mu='hist', method_cov='ledoit')
            
            # --- LÓGICA CORREGIDA ---
            if model == 'MV':
                weights_df = port.optimization(
                    model='Classic',   # El modelo siempre es 'Classic'
                    rm='MV',           # La medida de riesgo es Varianza
                    obj='MinRisk'      # El objetivo es Minimizar el Riesgo
                )
            elif model == 'MSR':
                weights_df = port.optimization(
                    model='Classic',
                    rm='MV',
                    obj='Sharpe', # El objetivo correcto es 'Sharpe'
                    rf=0.0      # Tasa libre de riesgo, fundamental para el cálculo
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
        
        # Usamos 'ledoit' para que la matriz de covarianza sea siempre robusta
        port.assets_stats(method_mu='hist', method_cov='ledoit')

        # Calculamos la frontera. El rm por defecto es 'MV' (Varianza/Std. Dev.)
        frontier = port.efficient_frontier(model='Classic', points=points)
        
        if frontier is not None and not frontier.empty:
            # --- CORRECCIÓN DEFINITIVA ---
            # Los datos de riesgo y retorno están en el índice.
            # Lo "reseteamos" para convertirlos en columnas.
            frontier = frontier.reset_index()
            
            # Renombramos las nuevas columnas a los nombres que nuestra app espera.
            # La librería nombra las columnas del índice 'Std. Dev.' y 'Returns'
            frontier.rename(columns={'Std. Dev.': 'volatility_ann_%', 'Returns': 'annualized_return_%'}, inplace=True)
            
            # Convertimos a porcentaje
            frontier['volatility_ann_%'] *= 100
            frontier['annualized_return_%'] *= 100
            
            return frontier
        else:
            return None
            
    except Exception as e:
        # Imprimimos el error en la consola para depuración
        print(f"Error calculando la frontera eficiente: {e}")
        return None
    
def optimize_for_target_return(daily_returns: pd.DataFrame, target_return: float) -> pd.Series | None:
    """
    Encuentra la cartera de mínima volatilidad que cumple con una rentabilidad objetivo.
    """
    # 1. Calculamos la frontera completa
    frontier = calculate_efficient_frontier(daily_returns)
    if frontier is None:
        return None

    # 2. Buscamos las carteras que cumplen o superan la rentabilidad objetivo
    # La rentabilidad objetivo viene en %, la de la frontera en decimal
    valid_portfolios = frontier[frontier['Returns'] >= (target_return / 100)]

    if valid_portfolios.empty:
        # Si ninguna cartera llega a esa rentabilidad, no hay solución
        return None
    
    # 3. De esas, elegimos la que tiene la menor volatilidad ('Std. Dev.')
    best_portfolio_weights = valid_portfolios.sort_values(by='Std. Dev.').iloc[0]

    # 4. Devolvemos los pesos
    return best_portfolio_weights