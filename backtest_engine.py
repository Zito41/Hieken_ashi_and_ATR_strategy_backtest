from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class StrategyConfig:
    atr_stop_multiplier: float = 1.5
    atr_spike_threshold: float = 1.10
    trim_price_distance: float = 5.00
    trim_size_factor: float = 0.5


def run_backtest(
    df: pd.DataFrame, direction: str = "long", config: StrategyConfig = None
) -> pd.DataFrame:
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")

    cfg = config or StrategyConfig()
    is_long = direction == "long"

    timestamps = df["timestamp"].to_numpy()
    close = df["Close"].to_numpy()
    high = df["High"].to_numpy()
    low = df["Low"].to_numpy()
    atr = df["ATR"].to_numpy()
    atr_sma = df["ATR_SMA"].to_numpy()
    ha_close = df["HA_Close"].to_numpy()
    ha_open = df["HA_Open"].to_numpy()
    ha_high = df["HA_High"].to_numpy()
    ha_low = df["HA_Low"].to_numpy()
    h1_bias = df["h1_bias_completed"].to_numpy()

    n = len(df)
    in_trade = False
    trade_log = []

    entry_price = 0.0
    entry_time = None
    initial_sl = 0.0
    stop_loss = 0.0
    position_size = 1.0
    trimmed_this_trade = False
    trim_price = np.nan
    trimmed_size = 0.0

    for i in range(1, n):
        # PHASE 1: ENTRY LOGIC
        if not in_trade:
            volatility_gate = (atr[i] > atr_sma[i]) and (atr[i - 1] <= atr_sma[i - 1])

            if is_long:
                signal_candle = (
                    (ha_close[i] > ha_open[i])
                    and (ha_low[i] == ha_open[i])
                    and (h1_bias[i] == 1)
                )
            else:
                signal_candle = (
                    (ha_close[i] < ha_open[i])
                    and (ha_high[i] == ha_open[i])
                    and (h1_bias[i] == -1)
                )

            if volatility_gate and signal_candle:
                in_trade = True
                entry_price = close[i]
                entry_time = timestamps[i]
                initial_sl = (
                    entry_price - cfg.atr_stop_multiplier * atr[i]
                    if is_long
                    else entry_price + cfg.atr_stop_multiplier * atr[i]
                )
                stop_loss = initial_sl
                position_size = 1.0
                trimmed_this_trade = False
                trim_price = np.nan
                trimmed_size = 0.0

        # PHASE 2: ACTIVE TRADE MANAGEMENT
        else:
            floating_pnl = (
                (close[i] - entry_price) if is_long else (entry_price - close[i])
            )
            price_distance = abs(close[i] - entry_price)

            # Directional Trimming
            atr_spike = atr[i] > (atr[i - 1] * cfg.atr_spike_threshold)
            if atr_spike and not trimmed_this_trade:  # noqa: SIM102
                if floating_pnl < 0 and price_distance < cfg.trim_price_distance:
                    trimmed_size = position_size * (1 - cfg.trim_size_factor)
                    trim_price = close[i]
                    position_size *= cfg.trim_size_factor
                    trimmed_this_trade = True

            # Trailing Stop Ratchet
            if is_long:
                new_potential_sl = high[i] - cfg.atr_stop_multiplier * atr[i]
                stop_loss = max(stop_loss, new_potential_sl)
            else:
                new_potential_sl = low[i] + cfg.atr_stop_multiplier * atr[i]
                stop_loss = min(stop_loss, new_potential_sl)

            # PHASE 3: EXIT LOGIC
            if is_long:
                hit_sl = low[i] <= stop_loss
                loss_of_momentum = ha_close[i] < ha_open[i]
                opposing_wick = ha_low[i] < ha_open[i]
            else:
                hit_sl = high[i] >= stop_loss
                loss_of_momentum = ha_close[i] > ha_open[i]
                opposing_wick = ha_high[i] > ha_open[i]

            if hit_sl or loss_of_momentum or opposing_wick:
                exit_price = stop_loss if hit_sl else close[i]
                exit_time = timestamps[i]

                if trimmed_this_trade:
                    realized_trim = (
                        (trim_price - entry_price) * trimmed_size
                        if is_long
                        else (entry_price - trim_price) * trimmed_size
                    )
                else:
                    realized_trim = 0.0

                realized_remainder = (
                    (exit_price - entry_price) * position_size
                    if is_long
                    else (entry_price - exit_price) * position_size
                )

                pnl = realized_trim + realized_remainder
                exit_reason = (
                    "Stop Loss"
                    if hit_sl
                    else ("Momentum Flip" if loss_of_momentum else "Opposing Wick")
                )

                trade_log.append(
                    {
                        "Direction": "LONG" if is_long else "SHORT",
                        "Entry Time": entry_time,
                        "Entry": entry_price,
                        "Initial SL": initial_sl,
                        "Exit Time": exit_time,
                        "Exit": exit_price,
                        "Trimmed": trimmed_this_trade,
                        "Trim Price": trim_price,
                        "Trimmed Size": trimmed_size,
                        "Final Size": position_size,
                        "Realized PnL (Trim)": realized_trim,
                        "Realized PnL (Remainder)": realized_remainder,
                        "PnL": pnl,
                        "Exit Reason": exit_reason,
                    }
                )
                in_trade = False

    return pd.DataFrame(trade_log)


def run_directional_backtest(
    df: pd.DataFrame, config: StrategyConfig = None
) -> pd.DataFrame:
    return run_backtest(df, direction="long", config=config)


def run_short_directional_backtest(
    df: pd.DataFrame, config: StrategyConfig = None
) -> pd.DataFrame:
    return run_backtest(df, direction="short", config=config)
