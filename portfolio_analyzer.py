# portfolio_analyzer.py
import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
import mstarpy as ms
import seaborn as sns
import argparse
from datetime import datetime, timedelta

# ==== CONFIGURACIÓN ====
N_DAYS = 90  # por ejemplo, consideramos que los últimos 90 días son suficientes

ISINS = [
    "ES0112231016",  # Avantage Fund
    "ES0140794001",  # Gamma Global FI
    "ES0146309002",  # Horos Value Internacional FI
    "IE00BLP5S460",  # JupiterMerian Glb Eq AbsRt L € H Acc
    "ES0159201013",  # Magallanes Iberian Equity M FI
    "LU2416422751",  # Vontobel Credit Opps HI Hdg EUR Cap
    "IE00B5648R31",  # Man GLG Japan CoreAlpha Equity Class D H EUR
    "LU1896847628",  # Vontobel EM Blend HI H EUR Acc
    "IE00BYX5P602",  # Fidelity MSCI World Index EUR P Acc
    "IE00BFZMJT78",  # Neuberger Berman Short Dur Er Bd EURIAcc
]

HORIZONTES = {
    "1y": 365,
    "3y": 3 * 365,
    "5y": 5 * 365,
    "max": None   # todo el histórico
}

OUTPUT_DIR = "fondos_data"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def ensure_datetime_index(df, date_col="date"):
    """
    Devuelve un DF con índice datetime. Si existe 'date', la usa como índice.
    Si ya es DatetimeIndex, lo devuelve ordenado.
    """
    if isinstance(df.index, pd.DatetimeIndex):
        return df.sort_index()
    if date_col in df.columns:
        out = df.copy()
        out[date_col] = pd.to_datetime(out[date_col])
        out = out.set_index(date_col).sort_index()
        return out
    raise ValueError("El DataFrame no tiene índice datetime ni columna 'date'.")
    

def filtrar_por_horizonte(df, horizonte: str):
    """
    Filtra por horizonte temporal:
      - '1y', '3y', '5y'  -> últimos n años desde el ÚLTIMO dato disponible
      - 'ytd'             -> año en curso desde el 1 de enero del año del ÚLTIMO dato
      - 'max'             -> todo
      - 'YYYY-MM-DD:YYYY-MM-DD' -> rango exacto
    Acepta DF con 'date' + columnas o con DatetimeIndex.
    """
    df = ensure_datetime_index(df)  # asegura DatetimeIndex
    if df.empty:
        return df

    df = df.sort_index()
    anchor = df.index.max()  # último dato disponible del fondo

    if horizonte in ("1y", "3y", "5y"):
        years = int(horizonte[:-1])
        start = anchor - pd.DateOffset(years=years)
        return df.loc[start:anchor]

    if horizonte == "ytd":
        start = pd.Timestamp(year=anchor.year, month=1, day=1)
        return df.loc[start:anchor]

    if horizonte == "max":
        return df

    if ":" in horizonte:
        start_str, end_str = horizonte.split(":")
        start = pd.to_datetime(start_str)
        end = pd.to_datetime(end_str)
        return df.loc[start:end]

    raise ValueError(f"Horizonte no reconocido: {horizonte}")




def procesar_fondo(isin: str):
    file_path = os.path.join(OUTPUT_DIR, f"{isin}.csv")
    today = datetime.today().date()
    recent_limit = today - timedelta(days=N_DAYS)

    if os.path.exists(file_path):
        df = pd.read_csv(file_path, parse_dates=["date"])
        last_date = df["date"].max().date()

        # Solo descargar si el último dato es anterior a recent_limit
        if last_date < recent_limit:
            print(f"🔄 Descargando últimos 12 meses para {isin}...")
            try:
                fund = ms.Funds(isin)
                one_year_ago = today - timedelta(days=365)
                nuevos = pd.DataFrame(fund.nav(start_date=one_year_ago, end_date=today))
            except Exception as e:
                print(f"⚠️ Error descargando {isin}: {e}")
                return df, calcular_metricas(df)

            if not nuevos.empty:
                nav_col = next((c for c in ["nav","accumulatedNav","totalReturn"] if c in nuevos.columns), None)
                if nav_col is None:
                    raise ValueError(f"No se encontró columna NAV válida para {isin}")
                nuevos = nuevos.rename(columns={nav_col:"nav"})[["date","nav"]]
                nuevos["date"] = pd.to_datetime(nuevos["date"])
                df = pd.concat([df,nuevos], ignore_index=True).drop_duplicates(subset="date")
                df = df.sort_values("date")
                df.to_csv(file_path, index=False)
                print(f"✅ Datos de {isin} actualizados (último año)")
            else:
                print(f"📂 No hay datos nuevos para {isin}")
        else:
            print(f"📂 Datos de {isin} cubren los últimos {N_DAYS} días")
    else:
        # Si no existe el CSV, intentar descargar TODOS los datos disponibles
        print(f"🌐 Descargando todos los datos disponibles para {isin}...")
        try:
            fund = ms.Funds(isin)
            start_date = date(1900,1,1)  # inicio muy antiguo
            end_date = today
            df = pd.DataFrame(fund.nav(start_date=start_date, end_date=end_date))
        except Exception as e:
            print(f"⚠️ Error descargando {isin}: {e}")
            return None, None

        if df.empty:
            print(f"⚠️ No se encontraron datos para {isin}")
            return None, None

        nav_col = next((c for c in ["nav","accumulatedNav","totalReturn"] if c in df.columns), None)
        if nav_col is None:
            raise ValueError(f"No se encontró columna NAV válida para {isin}")

        df = df.rename(columns={nav_col:"nav"})[["date","nav"]]
        df["date"] = pd.to_datetime(df["date"])
        df.to_csv(file_path, index=False)
        print(f"✅ Guardado {file_path}")

    metrics = calcular_metricas(df)
    return df, metrics


# ==== FUNCIONES ====
def get_fund_nav(identifier: str):
    """Descarga todo el histórico NAV de un fondo por su identificador (ISIN o ticker)."""
    try:
        fund = ms.Funds(identifier)

        start_date = datetime(1900, 1, 1)
        end_date = datetime.today()

        nav_list = fund.nav(start_date, end_date)
        df = pd.DataFrame(nav_list)

        # Ver qué columnas devuelve
        print(f"Columnas devueltas para {identifier}: {df.columns.tolist()}")

        # Seleccionar solo las necesarias (date, nav)
        if "nav" in df.columns:
            df = df[["date", "nav"]]
        elif "accumulatedNav" in df.columns:
            df = df.rename(columns={"accumulatedNav": "nav"})
            df = df[["date", "nav"]]

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")

        return df

    except Exception as e:
        print(f"No se pudo procesar el identificador {identifier}: {e}")
        return None


def save_fund_csv(isin: str, df: pd.DataFrame):
    """Guarda el DataFrame en CSV"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    file_path = os.path.join(OUTPUT_DIR, f"{isin}.csv")
    df.to_csv(file_path, index=False)
    print(f"✅ Guardado {file_path}")


# ==== FUNCIONES METRICAS ====
def calcular_metricas(df: pd.DataFrame) -> dict:
    df = df.sort_values("date")
    metrics = {}

    # Rentabilidad acumulada (%)
    metrics["cumulative_return"] = (df["nav"].iloc[-1] / df["nav"].iloc[0] - 1) * 100

    # Rentabilidad diaria
    daily_returns = df["nav"].pct_change(fill_method=None).dropna()
    metrics["mean_return"] = daily_returns.mean() * 100
    metrics["volatility"] = daily_returns.std() * (252**0.5)

    # Sharpe ratio (sin tasa libre de riesgo)
    metrics["sharpe"] = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() != 0 else None

    # Drawdown máximo (%)
    rolling_max = df["nav"].cummax()
    drawdowns = (df["nav"] - rolling_max) / rolling_max
    metrics["max_drawdown"] = drawdowns.min() * 100

    return metrics

# ==== FUNCION RESUMEN Y GRAFICOS CON DEPURACION ====
def generar_resumen(isins, horizonte="max"):
    resumen = []
    all_navs = []

    print("🔹 Procesando fondos:")
    for isin in isins:
        res = procesar_fondo(isin)
        if res is None:
            print(f"⚠️ No se pudo procesar {isin}, se salta")
            continue
        df, metrics = res
        if df is None or df.empty:
            print(f"⚠️ {isin} sin datos")
            continue

        # Garantiza índice datetime usando la columna 'date'
        df_idx = ensure_datetime_index(df[["date", "nav"]])

        # Filtra por horizonte
        df_h = filtrar_por_horizonte(df_idx[["nav"]], horizonte)
        if df_h.empty:
            print(f"⚠ Sin datos para {isin} en el horizonte {horizonte}")
            continue

        # Para métricas: tu función original usa columna 'date', así que reseteamos
        df_h_reset = df_h.reset_index().rename(columns={"index": "date"})
        df_h_reset.columns = ["date", "nav"]  # por si el index ya se llama 'date'

        metrics_h = calcular_metricas(df_h_reset)
        metrics_h["isin"] = isin
        resumen.append(metrics_h)

        # Para gráficos/correlación: guardamos con columna renombrada al ISIN
        df_plot = df_h.rename(columns={"nav": isin})
        all_navs.append(df_plot)

        # DEBUG
        print(f"  - {isin}: shape={df_h.shape}, fechas={df_h.index.min().date()} - {df_h.index.max().date()}")

    # Guardar resumen
    if resumen:
        resumen_df = pd.DataFrame(resumen)
        resumen_file = os.path.join(OUTPUT_DIR, f"resumen_metrics_{horizonte}.csv")
        resumen_df.to_csv(resumen_file, index=False)
        print(f"📊 Resumen de métricas guardado en {resumen_file}")
    else:
        print("⚠ No se generó resumen (sin datos tras filtrar).")

    # Gráficos + correlación (si hay al menos 2 fondos)
    if len(all_navs) >= 1:
        generar_graficos(all_navs)            # ya rellena ffill/bfill por dentro
    if len(all_navs) >= 2:
        # tu función de correlación/heatmap
        try:
            plot_correlacion_heatmap(all_navs)
        except Exception as e:
            print(f"⚠ No se pudo generar heatmap de correlación: {e}")


# ==== GRÁFICOS AVANZADOS ====
def generar_graficos(all_navs):
    if not all_navs:
        return

    # Concatenar todos los NAVs por fecha
    combined = pd.concat(all_navs, axis=1).sort_index()
    combined = combined.ffill().bfill()  # rellenar NaN hacia adelante y atrás

    # 1️⃣ Evolución normalizada
    combined_norm = combined / combined.iloc[0] * 100
    plt.figure(figsize=(14,6))
    for col in combined_norm.columns:
        plt.plot(combined_norm.index, combined_norm[col], label=col)
    plt.title("Evolución normalizada de fondos")
    plt.xlabel("Fecha")
    plt.ylabel("NAV normalizado")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 2️⃣ Rentabilidad acumulada (%)
    cum_ret = (combined / combined.iloc[0] - 1) * 100
    plt.figure(figsize=(14,6))
    for col in cum_ret.columns:
        plt.plot(cum_ret.index, cum_ret[col], label=col)
    plt.title("Rentabilidad acumulada de fondos (%)")
    plt.xlabel("Fecha")
    plt.ylabel("Rentabilidad acumulada (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 3️⃣ Drawdown comparativo (%)
    drawdown = (combined / combined.cummax() - 1) * 100
    plt.figure(figsize=(14,6))
    for col in drawdown.columns:
        plt.plot(drawdown.index, drawdown[col], label=col)
    plt.title("Drawdown máximo de fondos (%)")
    plt.xlabel("Fecha")
    plt.ylabel("Drawdown (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # 4️⃣ Volatilidad histórica (rolling 30 días, anualizada %)
    rolling_vol = combined.pct_change().rolling(30).std() * np.sqrt(252) * 100
    plt.figure(figsize=(14,6))
    for col in rolling_vol.columns:
        plt.plot(rolling_vol.index, rolling_vol[col], label=col)
    plt.title("Volatilidad histórica (rolling 30 días, % anualizado)")
    plt.xlabel("Fecha")
    plt.ylabel("Volatilidad (%)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()


def plot_correlacion_heatmap(all_navs):
    combined = pd.concat(all_navs, axis=1).sort_index()
    combined = combined.ffill().bfill()

    daily_returns = combined.pct_change().dropna()
    corr_matrix = daily_returns.corr()

    plt.figure(figsize=(10,8))
    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5)
    plt.title("Heatmap de correlación entre fondos (diaria)")
    plt.tight_layout()
    plt.show()

    # Guardar CSV
    corr_file = os.path.join(OUTPUT_DIR, "correlacion_fondos.csv")
    corr_matrix.to_csv(corr_file)
    print(f"📊 Heatmap y CSV de correlación guardados (CSV: {corr_file})")

    return corr_matrix

# Integración en main
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizonte", type=str, default="max",
                        help="Opciones: 1y, 3y, 5y, ytd, max, o 'YYYY-MM-DD:YYYY-MM-DD'")
    args = parser.parse_args()
    print(f"📅 Usando horizonte temporal: {args.horizonte}")

    generar_resumen(ISINS, horizonte=args.horizonte)
