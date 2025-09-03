# tests/test_metrics.py

import pandas as pd
import pytest
from src.metrics import calcular_metricas_desde_rentabilidades

def test_calculo_metricas_basico():
    """
    Prueba que la función de métricas calcule valores correctos para una serie simple.
    """
    # 1. PREPARAR (Arrange): Usamos los mismos datos de prueba.
    precios = pd.Series(
        [100, 110, 99, 105],
        index=pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04'])
    )
    daily_returns = precios.pct_change().dropna()

    # 2. ACTUAR (Act): Llamamos a la función.
    metricas = calcular_metricas_desde_rentabilidades(daily_returns)

    # 3. VERIFICAR (Assert): Comprobamos con los valores correctos.
    assert isinstance(metricas, dict)
    
    # --- VALORES ESPERADOS CORREGIDOS ---
    assert metricas['volatility_ann_%'] == pytest.approx(168.18, abs=0.1)
    assert metricas['sharpe_ann'] == pytest.approx(3.02, abs=0.1)
    assert metricas['max_drawdown_%'] == pytest.approx(-10.0, abs=0.01)

def test_metricas_con_datos_insuficientes():
    """
    Prueba que la función devuelva NaN si hay muy pocos datos.
    """
    precios = pd.Series([100, 101], index=pd.to_datetime(['2025-01-01', '2025-01-02']))
    daily_returns = precios.pct_change().dropna()
    
    metricas = calcular_metricas_desde_rentabilidades(daily_returns)
    
    # Esta parte ya funcionaba y no necesita cambios
    assert pd.isna(metricas['volatility_ann_%'])
    assert pd.isna(metricas['sharpe_ann'])
    assert pd.isna(metricas['max_drawdown_%'])