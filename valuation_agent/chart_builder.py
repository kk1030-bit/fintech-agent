"""統一產生股票分析圖表的 matplotlib 工具模組。"""

from __future__ import annotations

import re
import os
from pathlib import Path
from typing import Iterable, Sequence

MODULE_DIR = Path(__file__).resolve().parent
os.environ.setdefault("MPLCONFIGDIR", str(MODULE_DIR / ".matplotlib"))
PROJECT_ROOT = MODULE_DIR.parent

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Microsoft JhengHei"
plt.rcParams["axes.unicode_minus"] = False

PRIMARY_BLUE = "#0F6B8F"
SECONDARY_TEAL = "#20A486"
LIGHT_TEAL = "#BFEDE3"
DEEP_GREEN = "#087F6F"
NEGATIVE_CORAL = "#E76F51"
GRID_COLOR = "#D8E8EA"
TEXT_COLOR = "#173B45"

CHART_DIR = PROJECT_ROOT / "output" / "charts"


def _as_list(values: Iterable) -> list:
    return list(values)


def _validate_same_length(series: Sequence[Sequence], names: Sequence[str]) -> None:
    lengths = [len(item) for item in series]
    if len(set(lengths)) != 1:
        detail = ", ".join(f"{name}={length}" for name, length in zip(names, lengths))
        raise ValueError(f"輸入資料長度必須一致：{detail}")
    if lengths and lengths[0] == 0:
        raise ValueError("輸入資料不可為空。")


def _safe_filename(stock_name: str, chart_type: str) -> str:
    safe_name = re.sub(r'[<>:"/\\|?*\s]+', "_", str(stock_name).strip())
    safe_name = safe_name.strip("_") or "stock"
    return f"{safe_name}_{chart_type}.png"


def _prepare_axes(ax: plt.Axes) -> None:
    ax.set_facecolor("white")
    ax.grid(True, axis="y", color=GRID_COLOR, linewidth=0.9)
    ax.tick_params(colors=TEXT_COLOR)
    for spine in ax.spines.values():
        spine.set_color("#A9C7CC")


def _save_figure(fig: plt.Figure, filename: str) -> str:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    output_path = CHART_DIR / filename
    fig.savefig(output_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return str(output_path)


def plot_stock_price(dates, prices, stock_name):
    """繪製股價走勢折線圖，並回傳 PNG 檔案路徑。"""

    dates = _as_list(dates)
    prices = _as_list(prices)
    _validate_same_length([dates, prices], ["dates", "prices"])

    fig, ax = plt.subplots(figsize=(10, 5.5))
    _prepare_axes(ax)

    x_positions = list(range(len(dates)))
    ax.plot(
        x_positions,
        prices,
        color=PRIMARY_BLUE,
        linewidth=2.6,
        marker="o",
        markersize=5,
        markerfacecolor=SECONDARY_TEAL,
        markeredgecolor="white",
        markeredgewidth=1,
    )
    ax.fill_between(x_positions, prices, min(prices), color=LIGHT_TEAL, alpha=0.35)

    ax.set_title(f"{stock_name} 股價走勢圖", fontsize=18, color=TEXT_COLOR, pad=16)
    ax.set_xlabel("日期", fontsize=12, color=TEXT_COLOR)
    ax.set_ylabel("股價", fontsize=12, color=TEXT_COLOR)
    ax.set_xticks(x_positions)
    ax.set_xticklabels(dates, rotation=35, ha="right")

    fig.tight_layout()
    return _save_figure(fig, _safe_filename(stock_name, "stock_price"))


def plot_financial_ratios(years, pe_list, pb_list, stock_name):
    """繪製 P/E 與 P/B 雙軸圖，並回傳 PNG 檔案路徑。"""

    years = _as_list(years)
    pe_list = _as_list(pe_list)
    pb_list = _as_list(pb_list)
    _validate_same_length([years, pe_list, pb_list], ["years", "pe_list", "pb_list"])

    fig, ax_pe = plt.subplots(figsize=(10, 5.5))
    _prepare_axes(ax_pe)

    pe_line = ax_pe.plot(
        years,
        pe_list,
        color=PRIMARY_BLUE,
        marker="o",
        linewidth=2.5,
        label="P/E 本益比",
    )
    ax_pe.set_ylabel("P/E 本益比", fontsize=12, color=PRIMARY_BLUE)
    ax_pe.tick_params(axis="y", labelcolor=PRIMARY_BLUE)
    ax_pe.set_xlabel("年度", fontsize=12, color=TEXT_COLOR)

    ax_pb = ax_pe.twinx()
    pb_line = ax_pb.plot(
        years,
        pb_list,
        color=SECONDARY_TEAL,
        marker="s",
        linewidth=2.5,
        label="P/B 股價淨值比",
    )
    ax_pb.set_ylabel("P/B 股價淨值比", fontsize=12, color=SECONDARY_TEAL)
    ax_pb.tick_params(axis="y", labelcolor=SECONDARY_TEAL)
    ax_pb.spines["right"].set_color("#A9C7CC")

    lines = pe_line + pb_line
    labels = [line.get_label() for line in lines]
    ax_pe.legend(lines, labels, loc="upper left", frameon=True, facecolor="white")

    ax_pe.set_title(f"{stock_name} P/E 與 P/B 財務比率", fontsize=18, color=TEXT_COLOR, pad=16)
    fig.tight_layout()
    return _save_figure(fig, _safe_filename(stock_name, "financial_ratios"))


def plot_dcf_waterfall(components, values, stock_name):
    """繪製 DCF 估值瀑布圖，並回傳 PNG 檔案路徑。"""

    components = _as_list(components)
    values = _as_list(values)
    _validate_same_length([components, values], ["components", "values"])

    cumulative = [0]
    for value in values:
        cumulative.append(cumulative[-1] + value)

    fig, ax = plt.subplots(figsize=(11, 6))
    _prepare_axes(ax)

    x_positions = list(range(len(values)))
    for idx, value in enumerate(values):
        start = cumulative[idx]
        end = cumulative[idx + 1]
        bottom = min(start, end)
        height = abs(value)
        color = SECONDARY_TEAL if value >= 0 else NEGATIVE_CORAL

        ax.bar(idx, height, bottom=bottom, color=color, edgecolor="white", linewidth=1.2)
        label_y = end + (max(abs(max(cumulative)), abs(min(cumulative)), 1) * 0.025)
        ax.text(
            idx,
            label_y,
            f"{value:+,.0f}",
            ha="center",
            va="bottom",
            fontsize=10,
            color=TEXT_COLOR,
        )

        if idx < len(values) - 1:
            ax.plot([idx + 0.38, idx + 0.62], [end, end], color="#8CBBC2", linewidth=1.2)

    total = cumulative[-1]
    total_index = len(values)
    ax.bar(
        total_index,
        total,
        color=PRIMARY_BLUE if total >= 0 else DEEP_GREEN,
        edgecolor="white",
        linewidth=1.2,
    )
    ax.text(
        total_index,
        total + (max(abs(max(cumulative)), abs(min(cumulative)), 1) * 0.025),
        f"{total:,.0f}",
        ha="center",
        va="bottom",
        fontsize=11,
        fontweight="bold",
        color=TEXT_COLOR,
    )

    ax.axhline(0, color="#789CA3", linewidth=1)
    ax.set_xticks(x_positions + [total_index])
    ax.set_xticklabels(components + ["估值總計"], rotation=20, ha="right")
    ax.set_ylabel("價值", fontsize=12, color=TEXT_COLOR)
    ax.set_title(f"{stock_name} DCF 估值瀑布圖", fontsize=18, color=TEXT_COLOR, pad=16)

    fig.tight_layout()
    return _save_figure(fig, _safe_filename(stock_name, "dcf_waterfall"))


if __name__ == "__main__":
    demo_dates = [f"2024-{month:02d}" for month in range(1, 13)]
    demo_prices = [590, 610, 628, 640, 662, 701, 745, 776, 812, 836, 858, 880]

    demo_years = [2020, 2021, 2022, 2023, 2024]
    demo_pe = [23.5, 26.1, 18.8, 21.4, 24.2]
    demo_pb = [5.4, 6.1, 4.8, 5.6, 6.3]

    demo_components = ["五年 FCF 現值", "終值現值", "淨現金", "風險折價"]
    demo_values = [8600, 28500, 3000, -2200]

    paths = [
        plot_stock_price(demo_dates, demo_prices, "台積電"),
        plot_financial_ratios(demo_years, demo_pe, demo_pb, "台積電"),
        plot_dcf_waterfall(demo_components, demo_values, "台積電"),
    ]

    for path in paths:
        print(path)
