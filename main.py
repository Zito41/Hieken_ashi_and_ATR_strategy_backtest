import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import Analytics_dashboard as dash
import backtest_engine as be
import data_loader


def run():
    output_dir = os.path.join(BASE_DIR, "output")

    # 1. Fetch ~8 months of historical data directly from MT5 (~20,000 M15 bars)
    df_mtf = data_loader.process_mtf_data_mt5(symbol="XAUUSD", bars_m15=20000)

    # 2. Configure Strategy Rules
    config = be.StrategyConfig(
        atr_stop_multiplier=1.5,
        atr_spike_threshold=1.10,
        trim_price_distance=5.00,
        trim_size_factor=0.5,
    )

    # 3. Execute Strategy Backtest
    print("\nRunning XAUUSD Backtest Engine...")
    results_long = be.run_directional_backtest(df_mtf, config)
    results_short = be.run_short_directional_backtest(df_mtf, config)

    # 4. Generate Excel Reports, PNG Charts, and Prop Analytics Card
    dash.generate_all_outputs(results_long, results_short, df_mtf, output_dir)


if __name__ == "__main__":
    run()
