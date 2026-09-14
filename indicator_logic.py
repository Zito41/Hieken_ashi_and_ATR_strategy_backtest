import numpy as np
import pandas as pd


def resample_ohlc(
    df: pd.DataFrame, rule: str = "15min", timestamp_col: str | None = None
) -> pd.DataFrame:
    df = df.copy()
    if timestamp_col is not None:
        df[timestamp_col] = pd.to_datetime(df[timestamp_col])
        df = df.set_index(timestamp_col)
    elif not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("df must have a DatetimeIndex or pass timestamp_col.")

    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last"}
    if "Volume" in df.columns:
        agg["Volume"] = "sum"

    resampled = df.resample(rule).agg(agg)
    resampled = resampled.dropna(subset=["Open", "High", "Low", "Close"])
    return resampled.reset_index()


def bars_for_hours(hours: float, timeframe_minutes: float) -> int:
    return round(hours * 60 / timeframe_minutes)


def prep_data(
    df: pd.DataFrame, atr_period: int = 14, atr_baseline_period: int = 20
) -> pd.DataFrame:
    required_cols = {"Open", "High", "Low", "Close"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"df is missing required columns: {missing}")

    df = df.copy()

    df["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4

    open_vals = df["Open"].to_numpy()
    close_vals = df["Close"].to_numpy()
    ha_close_vals = df["HA_Close"].to_numpy()
    n = len(df)

    ha_open_vals = np.empty(n)
    ha_open_vals[0] = (open_vals[0] + close_vals[0]) / 2
    for i in range(1, n):
        ha_open_vals[i] = (ha_open_vals[i - 1] + ha_close_vals[i - 1]) / 2
    df["HA_Open"] = ha_open_vals

    df["HA_High"] = df[["High", "HA_Open", "HA_Close"]].max(axis=1)
    df["HA_Low"] = df[["Low", "HA_Open", "HA_Close"]].min(axis=1)

    df["TR"] = np.maximum(
        df["High"] - df["Low"],
        np.maximum(
            abs(df["High"] - df["Close"].shift(1)),
            abs(df["Low"] - df["Close"].shift(1)),
        ),
    )
    df["ATR"] = df["TR"].rolling(window=atr_period).mean()
    df["ATR_SMA"] = df["ATR"].rolling(window=atr_baseline_period).mean()

    return df.dropna().reset_index(drop=True)
