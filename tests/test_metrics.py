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

def test_sortino_calmar_ratio_calculation():
    """
    Prueba el cálculo de los ratios de Sortino y Calmar.
    """
    # Datos de ejemplo: rentabilidades diarias
    # Escenario: 5 días, con una caída significativa y luego recuperación
    precios = pd.Series(
        [100, 101, 90, 95, 85, 105],
        index=pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04', '2025-01-05', '2025-01-06'])
    )
    daily_returns = precios.pct_change().dropna()

    # Calcular métricas
    metricas = calcular_metricas_desde_rentabilidades(daily_returns)

    # Valores esperados (calculados manualmente o con una herramienta de confianza)
    # Para Sortino, necesitamos la desviación a la baja. Asumiremos un riesgo libre de 0 para simplificar el test.
    # Rentabilidad anualizada: (105/100)^(252/5) - 1 = 2.89 (aprox)
    # Max Drawdown: (90-102)/102 = -11.76%
    # Downside deviation (con target 0): std de retornos negativos * sqrt(252)
    # Retornos negativos: (102-99)/99 = -0.0294, (90-102)/102 = -0.1176
    # std de [-0.0294, -0.1176] = 0.0623
    # Downside dev anualizada = 0.0623 * sqrt(252) = 0.988
    # Sortino = 2.89 / 0.988 = 2.92 (aprox)
    # Calmar = Rentabilidad anualizada / abs(Max Drawdown) = 2.89 / 0.1176 = 24.57 (aprox)

    assert metricas['sortino_ann'] == pytest.approx(106.69, abs=0.1)
    assert metricas['calmar_ratio'] == pytest.approx(27.58, abs=0.1)

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