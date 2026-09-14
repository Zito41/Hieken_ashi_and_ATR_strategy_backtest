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
            "Clean Wins": 0,
            "Flash Whipsaws": 0,
            "Slow Reversals": 0,
            "Standard Losses": 0,
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

    class_counts = (
        trades_df["Classification"].value_counts().to_dict()
        if "Classification" in trades_df.columns
        else {}
    )

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
        "Clean Wins": class_counts.get("CLEAN_WIN", 0),
        "Flash Whipsaws": class_counts.get("FLASH_WHIPSAW", 0),
        "Slow Reversals": class_counts.get("SLOW_REVERSAL", 0),
        "Standard Losses": class_counts.get("STANDARD_LOSS", 0),
    }


def generate_timeframe_breakdown(
    trades_df: pd.DataFrame, period_type: str = "M"
) -> pd.DataFrame:
    """Groups trades by timeframe ('M' for Month, 'Y' for Year) and computes metrics."""
    if trades_df.empty or "Entry Time" not in trades_df.columns:
        return pd.DataFrame()

    df = trades_df.copy()
    col_name = "Year" if period_type == "Y" else "Month"
    df[col_name] = (
        pd.to_datetime(df["Entry Time"]).dt.to_period(period_type).astype(str)
    )

    rows = []
    for period, group in df.groupby(col_name):
        metrics = calculate_advanced_metrics(group)
        metrics_row = {col_name: period}
        metrics_row.update(metrics)
        rows.append(metrics_row)

    return pd.DataFrame(rows)


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

    yearly_breakdown_df = generate_timeframe_breakdown(combined_trades, period_type="Y")
    monthly_breakdown_df = generate_timeframe_breakdown(
        combined_trades, period_type="M"
    )

    excel_path = os.path.join(output_dir, "strategy_results.xlsx")
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Overall Analytics", index=False)

        if not yearly_breakdown_df.empty:
            yearly_breakdown_df.to_excel(
                writer, sheet_name="Yearly Breakdown", index=False
            )

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

    x_indices = np.arange(len(chart_df))
    width = 0.65

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
        width=cl[down],
        color=col_down,
        edgecolor=col_down,
    )

    time_to_idx = {t: i for i, t in enumerate(chart_df["timestamp"])}

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

                cls_label = tr.get("Classification", "")
                ax1.scatter(exit_idx, tr["Exit"], color=exit_color, s=35, zorder=5)
                ax1.annotate(
                    f"{tr['Exit Reason']} ({cls_label})\n${tr['PnL']:.2f}",
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
        label="20-SMA Baseline",
        color="#a855f7",
        linestyle="--",
        linewidth=1.2,
    )
    ax2.set_title(
        "ATR Volatility Gate (20-SMA Baseline)",
        fontsize=10,
        fontweight="bold",
        color="#ffffff",
        pad=8,
    )
    ax2.set_ylabel("ATR ($)", color="#8b949e", fontweight="bold")
    ax2.tick_params(colors="#8b949e")
    ax2.grid(True, linestyle="--", alpha=0.2, color="#8b949e")

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

    df_copy = df.copy()

    # 1. Generate Yearly Price Charts
    yearly_charts_dir = os.path.join(output_dir, "yearly_charts")
    os.makedirs(yearly_charts_dir, exist_ok=True)
    df_copy["year"] = df_copy["timestamp"].dt.to_period("Y")

    for yr, yr_df in df_copy.groupby("year"):
        yr_str = str(yr)
        draw_candlestick_chart(
            yr_df,
            combined_trades,
            is_ha=False,
            title=f"XAUUSD Normal Candlestick Chart ({yr_str} Full Year)",
            filename=os.path.join(yearly_charts_dir, f"normal_chart_{yr_str}.png"),
        )
        draw_candlestick_chart(
            yr_df,
            combined_trades,
            is_ha=True,
            title=f"XAUUSD Heikin-Ashi Candlestick Chart ({yr_str} Full Year)",
            filename=os.path.join(yearly_charts_dir, f"ha_chart_{yr_str}.png"),
        )

    # 2. Generate Monthly Price Charts
    monthly_charts_dir = os.path.join(output_dir, "monthly_charts")
    os.makedirs(monthly_charts_dir, exist_ok=True)
    df_copy["year_month"] = df_copy["timestamp"].dt.to_period("M")

    for ym, month_df in df_copy.groupby("year_month"):
        month_str = str(ym)
        draw_candlestick_chart(
            month_df,
            combined_trades,
            is_ha=False,
            title=f"XAUUSD Normal Candlestick Chart ({month_str})",
            filename=os.path.join(monthly_charts_dir, f"normal_chart_{month_str}.png"),
        )
        draw_candlestick_chart(
            month_df,
            combined_trades,
            is_ha=True,
            title=f"XAUUSD Heikin-Ashi Candlestick Chart ({month_str})",
            filename=os.path.join(monthly_charts_dir, f"ha_chart_{month_str}.png"),
        )

    print(f"Price charts saved into '{yearly_charts_dir}' and '{monthly_charts_dir}'.")


def generate_prop_analytics_card(
    long_trades: pd.DataFrame,
    short_trades: pd.DataFrame,
    filename: str,
    subtitle_context: str = "Overall Strategy",
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
        f"Prop Firm Strategy Performance | {subtitle_context}",
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
        f"+${c_stats['Gross Profit ($)']:.2f} / -${c_stats['Gross Loss ($)']:.2f}",
        "#58a6ff" if c_stats["Total Net PnL ($)"] >= 0 else "#f85149",
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
        "#3fb950" if c_stats["Avg Trade PnL ($)"] >= 0 else "#f85149",
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
        "DIRECTIONAL & WHIPSAW BREAKDOWN",
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
            "Clean Wins / Flash Whip.",
            f"{l_stats['Clean Wins']} CW / {l_stats['Flash Whipsaws']} FW",
            f"{s_stats['Clean Wins']} CW / {s_stats['Flash Whipsaws']} FW",
            f"{c_stats['Clean Wins']} CW / {c_stats['Flash Whipsaws']} FW",
        ),
        (
            "Slow Rev. / Std Loss",
            f"{l_stats['Slow Reversals']} SR / {l_stats['Standard Losses']} SL",
            f"{s_stats['Slow Reversals']} SR / {s_stats['Standard Losses']} SL",
            f"{c_stats['Slow Reversals']} SR / {s_stats['Standard Losses']} SL",
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
            color="#3fb950" if "Win" in r[1] or "CW" in r[1] else "#c9d1d9",
        )
        ax.text(
            x_cols[2],
            y_pos,
            r[2],
            fontsize=9,
            color="#3fb950" if "Win" in r[2] or "CW" in r[2] else "#c9d1d9",
        )
        ax.text(
            x_cols[3],
            y_pos,
            r[3],
            fontsize=9,
            color="#58a6ff" if "Trades" in r[3] or "CW" in r[3] else "#c9d1d9",
        )
        y_pos -= 0.045

    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches="tight")
    plt.close()


def generate_all_outputs(
    long_trades: pd.DataFrame,
    short_trades: pd.DataFrame,
    df_mtf: pd.DataFrame,
    output_dir: str,
):
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nGenerating Strategy Outputs in '{output_dir}/'...")

    # 1. Export Excel Report (Overall + Yearly + Monthly Sheets)
    export_excel_report(long_trades, short_trades, output_dir)

    # 2. Export Price Charts (Yearly & Monthly)
    plot_price_charts(df_mtf, long_trades, short_trades, output_dir)

    # 3. Export Overall Prop Analytics Card
    generate_prop_analytics_card(
        long_trades,
        short_trades,
        filename=os.path.join(output_dir, "prop_analytics_card_overall.png"),
        subtitle_context="All-Time Strategy Performance",
    )

    # 4. Export Yearly Prop Analytics Cards
    yearly_cards_dir = os.path.join(output_dir, "yearly_cards")
    os.makedirs(yearly_cards_dir, exist_ok=True)

    long_trades_yr = long_trades.copy()
    short_trades_yr = short_trades.copy()
    if not long_trades_yr.empty:
        long_trades_yr["Year"] = pd.to_datetime(
            long_trades_yr["Entry Time"]
        ).dt.to_period("Y")
    if not short_trades_yr.empty:
        short_trades_yr["Year"] = pd.to_datetime(
            short_trades_yr["Entry Time"]
        ).dt.to_period("Y")

    all_years = set(long_trades_yr.get("Year", pd.Series(dtype=str))).union(
        set(short_trades_yr.get("Year", pd.Series(dtype=str)))
    )

    for yr in sorted(all_years):
        yr_str = str(yr)
        l_sub = (
            long_trades_yr[long_trades_yr["Year"] == yr]
            if "Year" in long_trades_yr
            else pd.DataFrame()
        )
        s_sub = (
            short_trades_yr[short_trades_yr["Year"] == yr]
            if "Year" in short_trades_yr
            else pd.DataFrame()
        )

        generate_prop_analytics_card(
            l_sub,
            s_sub,
            filename=os.path.join(
                yearly_cards_dir, f"prop_analytics_card_{yr_str}.png"
            ),
            subtitle_context=f"Full Year {yr_str} Performance",
        )

    # 5. Export Monthly Prop Analytics Cards
    monthly_cards_dir = os.path.join(output_dir, "monthly_cards")
    os.makedirs(monthly_cards_dir, exist_ok=True)

    long_trades_m = long_trades.copy()
    short_trades_m = short_trades.copy()
    if not long_trades_m.empty:
        long_trades_m["Month"] = pd.to_datetime(
            long_trades_m["Entry Time"]
        ).dt.to_period("M")
    if not short_trades_m.empty:
        short_trades_m["Month"] = pd.to_datetime(
            short_trades_m["Entry Time"]
        ).dt.to_period("M")

    all_months = set(long_trades_m.get("Month", pd.Series(dtype=str))).union(
        set(short_trades_m.get("Month", pd.Series(dtype=str)))
    )

    for ym in sorted(all_months):
        month_str = str(ym)
        l_sub = (
            long_trades_m[long_trades_m["Month"] == ym]
            if "Month" in long_trades_m
            else pd.DataFrame()
        )
        s_sub = (
            short_trades_m[short_trades_m["Month"] == ym]
            if "Month" in short_trades_m
            else pd.DataFrame()
        )

        generate_prop_analytics_card(
            l_sub,
            s_sub,
            filename=os.path.join(
                monthly_cards_dir, f"prop_analytics_card_{month_str}.png"
            ),
            subtitle_context=f"Monthly Performance ({month_str})",
        )

    print("All strategy outputs successfully exported!\n")
