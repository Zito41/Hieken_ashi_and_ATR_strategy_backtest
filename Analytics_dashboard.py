import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch


def calculate_advanced_metrics(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {
            "Total Trades": 0,
            "Win Rate (%)": 0.0,
            "Profit Factor": 0.0,
            "Total Net PnL ($)": 0.0,
            "Gross Profit ($)": 0.0,
            "Gross Loss ($)": 0.0,
            "Avg Trade PnL ($)": 0.0,
            "Expectancy ($)": 0.0,
            "Max Drawdown ($)": 0.0,
        }

    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df["PnL"] > 0]
    losing_trades = trades_df[trades_df["PnL"] < 0]

    num_wins = len(winning_trades)
    num_losses = len(losing_trades)
    win_rate = (num_wins / total_trades) * 100 if total_trades > 0 else 0.0

    gross_profit = winning_trades["PnL"].sum()
    gross_loss = abs(losing_trades["PnL"].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else np.inf

    total_pnl = trades_df["PnL"].sum()
    avg_trade = trades_df["PnL"].mean()
    expectancy = (
        win_rate / 100 * winning_trades["PnL"].mean() if num_wins > 0 else 0
    ) + ((1 - win_rate / 100) * losing_trades["PnL"].mean() if num_losses > 0 else 0)

    cumulative_pnl = trades_df["PnL"].cumsum()
    peak = cumulative_pnl.cummax()
    drawdown = cumulative_pnl - peak
    max_drawdown = abs(drawdown.min()) if not drawdown.empty else 0.0

    return {
        "Total Trades": total_trades,
        "Win Rate (%)": round(win_rate, 2),
        "Profit Factor": round(profit_factor, 2) if profit_factor != np.inf else "Inf",
        "Total Net PnL ($)": round(total_pnl, 2),
        "Gross Profit ($)": round(gross_profit, 2),
        "Gross Loss ($)": round(gross_loss, 2),
        "Avg Trade PnL ($)": round(avg_trade, 2),
        "Expectancy ($)": round(expectancy, 2),
        "Max Drawdown ($)": round(max_drawdown, 2),
    }


def generate_monthly_breakdown(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Groups trades by Year-Month and computes quantitative performance metrics for each month."""
    if trades_df.empty or "Entry Time" not in trades_df.columns:
        return pd.DataFrame()

    df = trades_df.copy()
    df["Month"] = pd.to_datetime(df["Entry Time"]).dt.to_period("M").astype(str)

    monthly_rows = []
    for month, group in df.groupby("Month"):
        metrics = calculate_advanced_metrics(group)
        metrics_row = {"Month": month}
        metrics_row.update(metrics)
        monthly_rows.append(metrics_row)

    return pd.DataFrame(monthly_rows)


def export_excel_report(
    long_trades: pd.DataFrame, short_trades: pd.DataFrame, output_dir: str
):
    combined_trades = (
        pd.concat([long_trades, short_trades]).sort_index()
        if not (long_trades.empty and short_trades.empty)
        else pd.DataFrame()
    )

    long_stats = pd.DataFrame(
        list(calculate_advanced_metrics(long_trades).items()),
        columns=["Metric", "Long Position"],
    )
    short_stats = pd.DataFrame(
        list(calculate_advanced_metrics(short_trades).items()),
        columns=["Metric", "Short Position"],
    )
    combined_stats = pd.DataFrame(
        list(calculate_advanced_metrics(combined_trades).items()),
        columns=["Metric", "Overall Combined"],
    )

    summary_df = combined_stats.merge(long_stats, on="Metric").merge(
        short_stats, on="Metric"
    )

    # 1. Build Monthly Performance Summary Table
    monthly_breakdown_df = generate_monthly_breakdown(combined_trades)

    excel_path = os.path.join(output_dir, "strategy_results.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Combined Analytics", index=False)

        # 2. Add Dedicated Monthly Breakdown Sheet
        if not monthly_breakdown_df.empty:
            monthly_breakdown_df.to_excel(
                writer, sheet_name="Monthly Breakdown", index=False
            )

        combined_trades.to_excel(writer, sheet_name="Combined Trade Log", index=False)
        long_stats.to_excel(writer, sheet_name="Long Analytics", index=False)
        long_trades.to_excel(writer, sheet_name="Long Trade Log", index=False)
        short_stats.to_excel(writer, sheet_name="Short Analytics", index=False)
        short_trades.to_excel(writer, sheet_name="Short Trade Log", index=False)

    print(f"Excel report saved successfully to: '{excel_path}'")


def draw_candlestick_chart(
    df: pd.DataFrame,
    trades_df: pd.DataFrame,
    is_ha: bool = False,
    title: str = "",
    filename: str = "",
):
    """Renders OHLC / Heikin-Ashi Candlestick chart for a full monthly slice without weekend gaps."""
    chart_df = df.copy().reset_index(drop=True)
    if chart_df.empty:
        return

    _fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(16, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor="#0d1117",
    )
    ax1.set_facecolor("#161b22")
    ax2.set_facecolor("#161b22")

    op = chart_df["HA_Open"] if is_ha else chart_df["Open"]
    hi = chart_df["HA_High"] if is_ha else chart_df["High"]
    lo = chart_df["HA_Low"] if is_ha else chart_df["Low"]
    cl = chart_df["HA_Close"] if is_ha else chart_df["Close"]

    up = cl >= op
    down = cl < op

    col_up = "#26a69a"
    col_down = "#ef5350"

    # Use index positions to eliminate weekend gaps completely
    x_indices = np.arange(len(chart_df))
    width = 0.65

    # 1. Candlestick Wicks & Bodies
    ax1.vlines(x_indices, lo, hi, color="#8b949e", linewidth=0.8, alpha=0.7)

    heights = abs(cl - op)
    heights_abs = np.maximum(heights, 0.05)

    ax1.bar(
        x_indices[up],
        heights_abs[up],
        bottom=op[up],
        width=width,
        color=col_up,
        edgecolor=col_up,
    )
    ax1.bar(
        x_indices[down],
        heights_abs[down],
        bottom=cl[down],
        width=width,
        color=col_down,
        edgecolor=col_down,
    )

    # Map timestamps to index positions for clean trade markers
    time_to_idx = {t: i for i, t in enumerate(chart_df["timestamp"])}

    # 2. Overlay Trade Entry, Initial SL, and Exit Markers
    if not trades_df.empty and "Entry Time" in trades_df.columns:
        min_time = chart_df["timestamp"].min()
        max_time = chart_df["timestamp"].max()

        visible_trades = trades_df[
            (trades_df["Entry Time"] >= min_time)
            & (trades_df["Entry Time"] <= max_time)
        ].reset_index(drop=True)

        for trade_idx, tr in visible_trades.iterrows():
            is_long = tr["Direction"] == "LONG"
            entry_color = "#00f2fe" if is_long else "#ff4b5c"

            entry_idx = time_to_idx.get(tr["Entry Time"])
            exit_idx = time_to_idx.get(tr["Exit Time"])

            stagger = (trade_idx % 4) * 6.0

            if entry_idx is not None:
                candle_high = chart_df["High"].iloc[entry_idx]
                candle_low = chart_df["Low"].iloc[entry_idx]

                y_anchor = candle_low if is_long else candle_high
                y_text = (
                    (candle_low - (12.0 + stagger))
                    if is_long
                    else (candle_high + (12.0 + stagger))
                )

                ax1.annotate(
                    f"{tr['Direction']} @ {tr['Entry']:.2f}",
                    xy=(entry_idx, y_anchor),
                    xytext=(entry_idx, y_text),
                    arrowprops={
                        "facecolor": entry_color,
                        "edgecolor": entry_color,
                        "shrink": 0.05,
                        "width": 0.8,
                        "headwidth": 3,
                    },
                    fontsize=6.5,
                    color="#ffffff",
                    fontweight="bold",
                    ha="center",
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "fc": "#161b22",
                        "ec": entry_color,
                        "lw": 0.8,
                        "alpha": 0.85,
                    },
                )

                end_idx = exit_idx if exit_idx is not None else len(chart_df) - 1
                ax1.hlines(
                    y=tr["Initial SL"],
                    xmin=entry_idx,
                    xmax=end_idx,
                    colors="#f85149",
                    linestyles="--",
                    linewidth=1,
                    alpha=0.7,
                )

            if exit_idx is not None:
                exit_color = "#3fb950" if tr["PnL"] > 0 else "#f85149"
                exit_high = chart_df["High"].iloc[exit_idx]
                exit_low = chart_df["Low"].iloc[exit_idx]

                exit_y_text = (
                    (exit_high + (10.0 + stagger))
                    if is_long
                    else (exit_low - (10.0 + stagger))
                )

                ax1.scatter(exit_idx, tr["Exit"], color=exit_color, s=35, zorder=5)
                ax1.annotate(
                    f"{tr['Exit Reason']}\n${tr['PnL']:.2f}",
                    xy=(exit_idx, tr["Exit"]),
                    xytext=(exit_idx, exit_y_text),
                    fontsize=6.5,
                    color="#c9d1d9",
                    ha="center",
                    bbox={
                        "boxstyle": "round,pad=0.2",
                        "fc": "#0d1117",
                        "ec": exit_color,
                        "lw": 0.6,
                        "alpha": 0.85,
                    },
                )

    ax1.set_title(title, fontsize=12, fontweight="bold", color="#ffffff", pad=10)
    ax1.set_ylabel("Price ($)", color="#8b949e", fontweight="bold")
    ax1.tick_params(colors="#8b949e")
    ax1.grid(True, linestyle="--", alpha=0.2, color="#8b949e")

    # 3. ATR Subplot
    ax2.plot(
        x_indices,
        chart_df["ATR"],
        label="14-ATR",
        color="#ff7f0e",
        linewidth=1.2,
    )
    ax2.plot(
        x_indices,
        chart_df["ATR_SMA"],
        label="ATR Baseline",
        color="#a855f7",
        linestyle="--",
        linewidth=1.2,
    )
    ax2.set_title(
        "ATR Volatility Gate",
        fontsize=10,
        fontweight="bold",
        color="#ffffff",
        pad=8,
    )
    ax2.set_ylabel("ATR ($)", color="#8b949e", fontweight="bold")
    ax2.tick_params(colors="#8b949e")
    ax2.grid(True, linestyle="--", alpha=0.2, color="#8b949e")

    # Format X-axis Ticks evenly across the month
    tick_step = max(1, len(chart_df) // 10)
    tick_positions = x_indices[::tick_step]
    tick_labels = [
        chart_df["timestamp"].iloc[i].strftime("%b %d %H:%M") for i in tick_positions
    ]

    ax2.set_xticks(tick_positions)
    ax2.set_xticklabels(tick_labels, rotation=30, ha="right")

    legend = ax2.legend(loc="upper left", facecolor="#161b22", edgecolor="#30363d")
    plt.setp(legend.get_texts(), color="#c9d1d9")

    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()


def plot_price_charts(
    df: pd.DataFrame,
    long_trades: pd.DataFrame,
    short_trades: pd.DataFrame,
    output_dir: str,
):
    combined_trades = (
        pd.concat([long_trades, short_trades]).sort_index()
        if not (long_trades.empty and short_trades.empty)
        else pd.DataFrame()
    )

    monthly_charts_dir = os.path.join(output_dir, "monthly_charts")
    os.makedirs(monthly_charts_dir, exist_ok=True)

    df_copy = df.copy()
    df_copy["year_month"] = df_copy["timestamp"].dt.to_period("M")
    grouped = df_copy.groupby("year_month")

    print(
        f"Generating monthly price charts for {len(grouped)} months in"
        f" '{monthly_charts_dir}'..."
    )

    for ym, month_df in grouped:
        month_str = str(ym)
        start_t = month_df["timestamp"].min().strftime("%b %d %H:%M")
        end_t = month_df["timestamp"].max().strftime("%b %d %H:%M")
        print(
            f" -> Plotting {month_str}: {len(month_df):,} M15 candles ({start_t} to"
            f" {end_t})"
        )

        normal_path = os.path.join(monthly_charts_dir, f"normal_chart_{month_str}.png")
        ha_path = os.path.join(monthly_charts_dir, f"ha_chart_{month_str}.png")

        draw_candlestick_chart(
            month_df,
            combined_trades,
            is_ha=False,
            title=f"XAUUSD Normal Candlestick Chart ({month_str})",
            filename=normal_path,
        )
        draw_candlestick_chart(
            month_df,
            combined_trades,
            is_ha=True,
            title=f"XAUUSD Heikin-Ashi Candlestick Chart ({month_str})",
            filename=ha_path,
        )

    print(f"All monthly charts successfully saved to '{monthly_charts_dir}/'!\n")


def generate_prop_analytics_card(
    long_trades: pd.DataFrame, short_trades: pd.DataFrame, output_dir: str
):
    combined_trades = (
        pd.concat([long_trades, short_trades]).sort_index()
        if not (long_trades.empty and short_trades.empty)
        else pd.DataFrame()
    )

    c_stats = calculate_advanced_metrics(combined_trades)
    l_stats = calculate_advanced_metrics(long_trades)
    s_stats = calculate_advanced_metrics(short_trades)

    fig = plt.figure(figsize=(12, 8), facecolor="#0d1117")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#0d1117")
    ax.axis("off")

    ax.text(
        0.04,
        0.92,
        "XAUUSD HA/ATR QUANT DASHBOARD",
        fontsize=22,
        fontweight="bold",
        color="#ffffff",
    )
    ax.text(
        0.04,
        0.87,
        "Prop Firm Strategy Performance | M15 Execution + H1 MTF Bias",
        fontsize=11,
        color="#8b949e",
    )

    def add_kpi(ax, x, y, w, h, title, value, subtext="", text_color="#3fb950"):
        box = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.02",
            facecolor="#161b22",
            edgecolor="#30363d",
            mutation_scale=1,
        )
        ax.add_patch(box)
        ax.text(
            x + w * 0.5,
            y + h * 0.72,
            title,
            fontsize=9,
            color="#8b949e",
            ha="center",
            va="center",
            fontweight="bold",
        )
        ax.text(
            x + w * 0.5,
            y + h * 0.42,
            value,
            fontsize=18,
            color=text_color,
            ha="center",
            va="center",
            fontweight="bold",
        )
        if subtext:
            ax.text(
                x + w * 0.5,
                y + h * 0.18,
                subtext,
                fontsize=8,
                color="#6e7681",
                ha="center",
                va="center",
            )

    add_kpi(
        ax,
        0.04,
        0.62,
        0.28,
        0.20,
        "NET PROFIT",
        f"${c_stats['Total Net PnL ($)']:.2f}",
        f"+${c_stats['Gross Profit ($)']:.2f} Profit / -${c_stats['Gross Loss ($)']:.2f} Loss",
        "#58a6ff",
    )
    add_kpi(
        ax,
        0.36,
        0.62,
        0.28,
        0.20,
        "WIN RATE",
        f"{c_stats['Win Rate (%)']}%",
        f"{len(combined_trades[combined_trades['PnL'] > 0])} Wins / {len(combined_trades[combined_trades['PnL'] < 0])} Losses",
        "#3fb950",
    )
    add_kpi(
        ax,
        0.68,
        0.62,
        0.28,
        0.20,
        "PROFIT FACTOR",
        f"{c_stats['Profit Factor']}",
        "High Expectancy Model",
        "#58a6ff",
    )

    add_kpi(
        ax,
        0.04,
        0.38,
        0.28,
        0.20,
        "TOTAL TRADES",
        f"{c_stats['Total Trades']}",
        f"{l_stats['Total Trades']} Long / {s_stats['Total Trades']} Short",
        "#f0f6fc",
    )
    add_kpi(
        ax,
        0.36,
        0.38,
        0.28,
        0.20,
        "AVG TRADE PnL",
        f"${c_stats['Avg Trade PnL ($)']:.2f}",
        f"Expectancy: ${c_stats['Expectancy ($)']:.2f}",
        "#3fb950",
    )
    add_kpi(
        ax,
        0.68,
        0.38,
        0.28,
        0.20,
        "MAX DRAWDOWN",
        f"${c_stats['Max Drawdown ($)']:.2f}",
        "Controlled Equity Dip",
        "#f85149",
    )

    box_detail = FancyBboxPatch(
        (0.04, 0.06),
        0.92,
        0.26,
        boxstyle="round,pad=0.01,rounding_size=0.02",
        facecolor="#161b22",
        edgecolor="#30363d",
        mutation_scale=1,
    )
    ax.add_patch(box_detail)

    ax.text(
        0.07,
        0.27,
        "DIRECTIONAL BREAKDOWN",
        fontsize=11,
        color="#ffffff",
        fontweight="bold",
    )
    headers = ["Metric", "Long Position", "Short Position", "Overall Combined"]
    x_cols = [0.07, 0.32, 0.57, 0.82]

    for x, h in zip(x_cols, headers):
        ax.text(x, 0.22, h, fontsize=10, color="#8b949e", fontweight="bold")

    rows = [
        (
            "Trades & Win Rate",
            f"{l_stats['Total Trades']} Trades ({l_stats['Win Rate (%)']}% Win)",
            f"{s_stats['Total Trades']} Trades ({s_stats['Win Rate (%)']}% Win)",
            f"{c_stats['Total Trades']} Trades ({c_stats['Win Rate (%)']}% Win)",
        ),
        (
            "Net Profit / Factor",
            f"${l_stats['Total Net PnL ($)']:.2f} PnL (PF: {l_stats['Profit Factor']})",
            f"${s_stats['Total Net PnL ($)']:.2f} PnL (PF: {s_stats['Profit Factor']})",
            f"${c_stats['Total Net PnL ($)']:.2f} PnL (PF: {c_stats['Profit Factor']})",
        ),
        (
            "Max Drawdown",
            f"${l_stats['Max Drawdown ($)']:.2f} DD",
            f"${s_stats['Max Drawdown ($)']:.2f} DD",
            f"${c_stats['Max Drawdown ($)']:.2f} DD",
        ),
    ]

    y_pos = 0.17
    for r in rows:
        ax.text(x_cols[0], y_pos, r[0], fontsize=9, color="#c9d1d9")
        ax.text(
            x_cols[1],
            y_pos,
            r[1],
            fontsize=9,
            color="#3fb950" if "PnL" in r[1] or "Win" in r[1] else "#c9d1d9",
        )
        ax.text(
            x_cols[2],
            y_pos,
            r[2],
            fontsize=9,
            color="#3fb950" if "PnL" in r[2] or "Win" in r[2] else "#c9d1d9",
        )
        ax.text(
            x_cols[3],
            y_pos,
            r[3],
            fontsize=9,
            color="#58a6ff" if "PnL" in r[3] else "#c9d1d9",
        )
        y_pos -= 0.045

    plt.tight_layout()
    card_path = os.path.join(output_dir, "prop_analytics_card.png")
    plt.savefig(card_path, dpi=300, bbox_inches="tight")
    plt.close()

    print(f"Prop Analytics Card saved to '{card_path}'")


def generate_all_outputs(
    long_trades: pd.DataFrame,
    short_trades: pd.DataFrame,
    df_mtf: pd.DataFrame,
    output_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nGenerating Strategy Outputs in '{output_dir}/'...")

    export_excel_report(long_trades, short_trades, output_dir)
    plot_price_charts(df_mtf, long_trades, short_trades, output_dir)
    generate_prop_analytics_card(long_trades, short_trades, output_dir)
    print("All strategy outputs successfully exported!\n")
