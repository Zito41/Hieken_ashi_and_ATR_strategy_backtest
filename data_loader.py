from datetime import datetime, timedelta

import MetaTrader5 as mt5
import numpy as np
import pandas as pd

import indicator_logic as ind


def process_mtf_data_mt5(symbol: str = "XAUUSD", bars_m15: int = 20000) -> pd.DataFrame:
    """Fetches historical M15 and H1 bars directly from MetaTrader 5 across an 8-month range."""
    print(f"Connecting to MetaTrader 5 terminal for {symbol}...")
    if not mt5.initialize():
        raise RuntimeError(f"MT5 Initialization failed: {mt5.last_error()}")

    # 1. Fetch M15 Data by Date Range (Last 240 days / ~8 months)
    utc_to = datetime.now()  # noqa: DTZ005
    utc_from = utc_to - timedelta(days=240)

    print(
        f"Requesting M15 historical range ({utc_from.strftime('%Y-%m-%d')} to"
        f" {utc_to.strftime('%Y-%m-%d')})..."
    )
    rates_m15 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, utc_from, utc_to)

    # Fallback to pos count if range fails
    if rates_m15 is None or len(rates_m15) == 0:
        rates_m15 = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, bars_m15)

    if rates_m15 is None or len(rates_m15) == 0:
        mt5.shutdown()
        raise ValueError(
            f"Failed to fetch M15 data for {symbol}. Ensure symbol is active in MT5"
            " Market Watch."
        )

    df_m15 = pd.DataFrame(rates_m15)
    df_m15["timestamp"] = pd.to_datetime(df_m15["time"], unit="s")
    df_m15 = df_m15.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    df_m15 = df_m15[["timestamp", "Open", "High", "Low", "Close"]]

    start_date = df_m15["timestamp"].min()
    end_date = df_m15["timestamp"].max()
    print(
        f"Successfully retrieved {len(df_m15):,} M15 bars covering"
        f" {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}.\n"
    )

    # 2. Fetch H1 Data covering the exact same timeframe
    h1_from = start_date - timedelta(days=10)
    rates_h1 = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H1, h1_from, utc_to)
    if rates_h1 is None or len(rates_h1) == 0:
        rates_h1 = mt5.copy_rates_from_pos(
            symbol, mt5.TIMEFRAME_H1, 0, int(bars_m15 / 4) + 100
        )

    df_h1 = pd.DataFrame(rates_h1)
    df_h1["timestamp"] = pd.to_datetime(df_h1["time"], unit="s")
    df_h1 = df_h1.rename(
        columns={"open": "Open", "high": "High", "low": "Low", "close": "Close"}
    )
    df_h1 = df_h1[["timestamp", "Open", "High", "Low", "Close"]]

    mt5.shutdown()

    # 3. Indicator Preparation
    df_h1 = ind.prep_data(df_h1, atr_period=14, atr_baseline_period=20)
    df_h1["h1_bias"] = np.where(df_h1["HA_Close"] >= df_h1["HA_Open"], 1, -1)
    df_h1["h1_bias_completed"] = df_h1["h1_bias"].shift(1)

    df_m15 = ind.prep_data(df_m15, atr_period=14, atr_baseline_period=64)

    # 4. Merge H1 Bias
    print("Merging MTF Data...")
    df_merged = pd.merge_asof(
        df_m15,
        df_h1[["timestamp", "h1_bias_completed"]],
        on="timestamp",
        direction="backward",
    )
    df_merged["h1_bias_completed"] = df_merged["h1_bias_completed"].fillna(0)

    return df_merged
