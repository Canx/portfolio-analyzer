# portfolio_analyzer.py
import os
import argparse
from datetime import datetime, timedelta, date

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

import mstarpy as ms


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
    

# En portfolio_analyzer.py

def filtrar_por_horizonte(df, horizonte: str):
    """
    Filtra por horizonte temporal. Ahora con soporte para meses ('m').
    """
    df = ensure_datetime_index(df)
    if df.empty:
        return df

    df = df.sort_index()
    anchor = df.index.max()

    # --- NUEVO BLOQUE PARA MESES ---
    if horizonte.endswith('m'):
        try:
            months = int(horizonte[:-1])
            start = anchor - pd.DateOffset(months=months)
            return df.loc[start:anchor]
        except (ValueError, TypeError):
            pass # Dejar que falle al final si el formato es incorrecto
    # --------------------------------

    if horizonte.endswith('d'):
        try:
            days = int(horizonte[:-1])
            start = anchor - pd.DateOffset(days=days)
            return df.loc[start:anchor]
        except (ValueError, TypeError):
            pass

    if horizonte in ("1y", "3y", "5y"):
        years = int(horizonte[:-1])
        start = anchor - pd.DateOffset(years=years)
        return df.loc[start:anchor]

    if horizonte.lower() == "ytd": # Usamos lower() para que sea insensible a mayúsculas
        start = pd.Timestamp(year=anchor.year, month=1, day=1)
        return df.loc[start:anchor]

    if horizonte.lower() == "max":
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
        df = df.sort_values("date").drop_duplicates(subset="date")
        last_date = df["date"].max().date()

        if last_date < recent_limit:
            # Descarga exacta de huecos: desde el día siguiente al último dato hasta hoy
            start_date = last_date + timedelta(days=1)
            if start_date <= today:
                print(f"🔄 Actualizando {isin} desde {start_date} a {today}...")
                try:
                    fund = ms.Funds(isin)
                    nuevos = pd.DataFrame(fund.nav(start_date=start_date, end_date=today))
                except Exception as e:
                    print(f"⚠️ Error descargando {isin}: {e}")
                    # devuelve lo que tenemos
                    return df, calcular_metricas(df)

                if not nuevos.empty:
                    nav_col = next((c for c in ["nav","accumulatedNav","totalReturn"] if c in nuevos.columns), None)
                    if nav_col is None:
                        print(f"⚠️ No se encontró columna NAV válida para {isin}")
                        return df, calcular_metricas(df)
                    nuevos = nuevos.rename(columns={nav_col:"nav"})[["date","nav"]]
                    nuevos["date"] = pd.to_datetime(nuevos["date"])
                    df = pd.concat([df, nuevos], ignore_index=True).drop_duplicates(subset="date")
                    df = df.sort_values("date")
                    df.to_csv(file_path, index=False)
                    print(f"✅ {isin} actualizado")
                else:
                    print(f"📂 No hay datos nuevos para {isin}")
            else:
                print(f"📂 {isin} ya está al día")
        else:
            print(f"📂 Datos de {isin} cubren los últimos {N_DAYS} días")
    else:
        # CSV no existe → intentamos todo el histórico disponible
        print(f"🌐 Descargando todo el histórico disponible para {isin}...")
        try:
            fund = ms.Funds(isin)
            start_date = date(1900, 1, 1)
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
            print(f"⚠️ No se encontró columna NAV válida para {isin}")
            return None, None

        df = df.rename(columns={nav_col:"nav"})[["date","nav"]]
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates(subset="date")
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


# En portfolio_analyzer.py (puedes añadirla después de la función calcular_metricas existente)

def calcular_metricas_desde_rentabilidades(daily_returns: pd.Series) -> dict:
    """Calcula las métricas clave a partir de una serie de rentabilidades diarias."""
    if daily_returns.empty or len(daily_returns) < 2:
        return {}
        
    metrics = {}
    
    # --- MÉTRICAS DE RENTABILIDAD ---
    # Rentabilidad Anualizada (CAGR)
    cumulative_return = (1 + daily_returns).prod() - 1
    num_days = (daily_returns.index[-1] - daily_returns.index[0]).days
    if num_days > 0:
        annualization_factor = 365.25 / num_days
        metrics["annualized_return_%"] = (((1 + cumulative_return) ** annualization_factor) - 1) * 100
    else:
        metrics["annualized_return_%"] = np.nan
        
    # --- MÉTRICAS DE RIESGO ---
    # Volatilidad Anualizada
    metrics["volatility_ann_%"] = daily_returns.std() * np.sqrt(252) * 100
    
    # Ratio de Sharpe
    mean_ann = daily_returns.mean() * 252
    vol_ann = metrics["volatility_ann_%"] / 100
    metrics["sharpe_ann"] = (mean_ann / vol_ann) if vol_ann > 0 else np.nan
    
    # Drawdown Máximo (requiere reconstruir el NAV)
    nav_series = (1 + daily_returns).cumprod() * 100
    rolling_max = nav_series.cummax()
    drawdowns = (nav_series / rolling_max - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min()

    return metrics

def calcular_metricas(df: pd.DataFrame) -> dict:
    df = df.sort_values("date").dropna(subset=["nav"])
    if len(df) < 2:
        return {} # No se pueden calcular métricas con menos de 2 puntos
        
    metrics = {}

    # --- MÉTRICAS DE RENTABILIDAD ---
    # 1. Rentabilidad acumulada para el periodo (%)
    cumulative_return = (df["nav"].iloc[-1] / df["nav"].iloc[0] - 1)
    metrics["cumulative_return_%"] = cumulative_return * 100

    # 2. Rentabilidad Anualizada (TAE/CAGR) (%) (NUEVO)
    num_days = (df["date"].iloc[-1] - df["date"].iloc[0]).days
    if num_days > 0:
        annualization_factor = 365.25 / num_days
        annualized_return = ((1 + cumulative_return) ** annualization_factor) - 1
        metrics["annualized_return_%"] = annualized_return * 100
    else:
        # Si el periodo es muy corto, la anualización no tiene sentido
        metrics["annualized_return_%"] = np.nan

    # --- MÉTRICAS DE RIESGO ---
    # Rentabilidades diarias
    daily_returns = df["nav"].pct_change(fill_method=None).dropna()

    # Volatilidad anualizada (%)
    metrics["volatility_ann_%"] = (daily_returns.std() * np.sqrt(252)) * 100

    # Sharpe (anualizado, sin rf)
    mean_ann = daily_returns.mean() * 252
    vol_ann = metrics["volatility_ann_%"] / 100
    metrics["sharpe_ann"] = (mean_ann / vol_ann) if vol_ann > 0 else np.nan

    # Drawdown máximo (%)
    rolling_max = df["nav"].cummax()
    drawdowns = (df["nav"] / rolling_max - 1) * 100
    metrics["max_drawdown_%"] = drawdowns.min()

    return metrics


def generar_resumen(isins, horizonte="max", plots=("norm","cumret","drawdown","vol"), corr=True, save_dir=None, show=True):
    """
    plots: tupla/lista con cualquiera de:
      - "norm", "cumret", "drawdown", "vol"
    corr: bool → dibujar heatmap de correlación
    save_dir: carpeta para guardar PNGs (None = no guardar)
    show: mostrar en pantalla (False = no mostrar)
    """
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

        # index datetime
        df_idx = ensure_datetime_index(df[["date", "nav"]])

        # filtrar por horizonte
        df_h = filtrar_por_horizonte(df_idx[["nav"]], horizonte)
        if df_h.empty:
            print(f"⚠ Sin datos para {isin} en el horizonte {horizonte}")
            continue

        # métricas en el horizonte (tu función espera columna 'date')
        df_h_reset = df_h.reset_index().rename(columns={"index": "date"})
        df_h_reset.columns = ["date", "nav"]

        metrics_h = calcular_metricas(df_h_reset)
        metrics_h["isin"] = isin
        resumen.append(metrics_h)

        # para combinados/gráficos
        df_plot = df_h.rename(columns={"nav": isin})
        all_navs.append(df_plot)

        print(f"  - {isin}: shape={df_h.shape}, fechas={df_h.index.min().date()} - {df_h.index.max().date()}")

    # resumen CSV
    if resumen:
        resumen_df = pd.DataFrame(resumen)
        resumen_file = os.path.join(OUTPUT_DIR, f"resumen_metrics_{horizonte}.csv")
        resumen_df.to_csv(resumen_file, index=False)
        print(f"📊 Resumen de métricas guardado en {resumen_file}")
    else:
        print("⚠ No se generó resumen (sin datos tras filtrar).")

    # gráficos opcionales
    if not all_navs:
        return

    combined = build_combined(all_navs)

    if "norm" in plots:
        plot_evolucion_normalizada(combined, save_dir=save_dir, show=show)
    if "cumret" in plots:
        plot_rentabilidad_acumulada(combined, save_dir=save_dir, show=show)
    if "drawdown" in plots:
        plot_drawdown(combined, save_dir=save_dir, show=show)
    if "vol" in plots:
        plot_rolling_vol(combined, window=30, save_dir=save_dir, show=show)

    if corr and combined.shape[1] >= 2:
        csv_name = f"correlacion_fondos_{horizonte}.csv"
        plot_correlacion_heatmap_from_combined(combined, save_dir=save_dir, show=show, csv_name=csv_name)


def _save_or_show(fig, name, save_dir=None, show=True):
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, f"{name}.png")
        fig.savefig(path, dpi=140, bbox_inches="tight")
        print(f"💾 Guardado: {path}")
    if show:
        plt.show()
    plt.close(fig)

def build_combined(all_navs):
    combined = pd.concat(all_navs, axis=1).sort_index()
    return combined.ffill().bfill()

def plot_evolucion_normalizada(combined, save_dir=None, show=True):
    combined_norm = combined / combined.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(14,6))
    for col in combined_norm.columns:
        ax.plot(combined_norm.index, combined_norm[col], label=col)
    ax.set_title("Evolución normalizada de fondos (100=fecha inicial)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("Índice (base 100)"); ax.legend(); ax.grid(True)
    _save_or_show(fig, "evolucion_normalizada", save_dir, show)

def plot_rentabilidad_acumulada(combined, save_dir=None, show=True):
    cum_ret = (combined / combined.iloc[0] - 1) * 100
    fig, ax = plt.subplots(figsize=(14,6))
    for col in cum_ret.columns:
        ax.plot(cum_ret.index, cum_ret[col], label=col)
    ax.set_title("Rentabilidad acumulada (%)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("%"); ax.legend(); ax.grid(True)
    _save_or_show(fig, "rentabilidad_acumulada", save_dir, show)

def plot_drawdown(combined, save_dir=None, show=True):
    drawdown = (combined / combined.cummax() - 1) * 100
    fig, ax = plt.subplots(figsize=(14,6))
    for col in drawdown.columns:
        ax.plot(drawdown.index, drawdown[col], label=col)
    ax.set_title("Drawdown (%)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("%"); ax.legend(); ax.grid(True)
    _save_or_show(fig, "drawdown", save_dir, show)

def plot_rolling_vol(combined, window=30, save_dir=None, show=True):
    rolling_vol = combined.pct_change().rolling(window).std() * np.sqrt(252) * 100
    fig, ax = plt.subplots(figsize=(14,6))
    for col in rolling_vol.columns:
        ax.plot(rolling_vol.index, rolling_vol[col], label=col)
    ax.set_title(f"Volatilidad rolling {window} días (% anualizado)")
    ax.set_xlabel("Fecha"); ax.set_ylabel("%"); ax.legend(); ax.grid(True)
    _save_or_show(fig, f"volatilidad_rolling_{window}d", save_dir, show)

def plot_correlacion_heatmap_from_combined(combined, save_dir=None, show=True, csv_name="correlacion_fondos.csv"):
    daily_returns = combined.pct_change().dropna()
    corr_matrix = daily_returns.corr()

    fig, ax = plt.subplots(figsize=(10,8))
    sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", fmt=".2f", linewidths=0.5, ax=ax)
    ax.set_title("Correlación diaria")
    _save_or_show(fig, "correlacion_heatmap", save_dir, show)

    # CSV
    csv_file = os.path.join(OUTPUT_DIR, csv_name)
    corr_matrix.to_csv(csv_file)
    print(f"📊 CSV de correlación guardado: {csv_file}")
    return corr_matrix


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

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizonte", type=str, default="max",
                        help="1y, 3y, 5y, ytd, max o 'YYYY-MM-DD:YYYY-MM-DD'")
    parser.add_argument("--plots", type=str, default="all",
                        help="Coma-separado entre: norm,cumret,drawdown,vol,none,all")
    parser.add_argument("--no-corr", action="store_true", help="No generar correlación")
    parser.add_argument("--savefig", type=str, default=None, help="Carpeta para guardar PNGs")
    parser.add_argument("--no-show", action="store_true", help="No mostrar ventanas de gráficos")
    args = parser.parse_args()

    print(f"📅 Usando horizonte temporal: {args.horizonte}")

    # parse plots
    p = args.plots.lower().strip()
    if p in ("none", "off"):
        plots = tuple()
    elif p in ("all", "todo"):
        plots = ("norm","cumret","drawdown","vol")
    else:
        plots = tuple(s.strip() for s in p.split(",") if s.strip() in {"norm","cumret","drawdown","vol"})

    generar_resumen(
        ISINS,
        horizonte=args.horizonte,
        plots=plots,
        corr=(not args.no_corr),
        save_dir=args.savefig,
        show=(not args.no_show),
    )
