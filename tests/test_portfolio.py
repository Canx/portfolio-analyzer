# tests/test_portfolio.py

import pandas as pd
import pytest
from src.portfolio import Portfolio

def test_calculo_nav_cartera_simple():
    """
    Prueba que el NAV de una cartera 50/50 se calcule correctamente.
    """
    # 1. PREPARAR (Arrange): Creamos datos de dos fondos y los pesos.
    fechas = pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03'])
    
    navs_df = pd.DataFrame({
        'FONDO_A': [100, 110, 120], # Sube un 10% y luego un 9.09%
        'FONDO_B': [100, 100, 90],  # Se mantiene y luego baja un 10%
    }, index=fechas)
    
    pesos = {'FONDO_A': 50, 'FONDO_B': 50}

    # 2. ACTUAR (Act): Creamos el objeto Portfolio y calculamos su NAV.
    cartera = Portfolio(nav_data=navs_df, weights=pesos)
    nav_cartera = cartera.nav

    # 3. VERIFICAR (Assert): Comprobamos que los valores del NAV son los esperados.
    # Día 1: Ambos fondos valen 100, la cartera empieza en 100.
    assert nav_cartera.iloc[0] == 100.0
    
    # Día 2: Rentabilidad A: +10%, Rentabilidad B: 0%. La media es +5%.
    # NAV esperado = 100 * 1.05 = 105
    assert nav_cartera.iloc[1] == pytest.approx(105.0)
    
    # Día 3: Rentabilidad A: +9.09%, Rentabilidad B: -10%. La media es -0.455%.
    # NAV esperado = 105 * (1 - 0.004545...) = 104.5227
    assert nav_cartera.iloc[2] == pytest.approx(104.52, abs=0.01)