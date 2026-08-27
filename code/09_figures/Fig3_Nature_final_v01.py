#!/usr/bin/env python3
"""Render the five-panel Figure 3 redesign from frozen, panel-ready CSV files.

This script performs plotting only. It does not fit models, recompute events, or
alter any source table. The four input files are fixed by TASK
FIG3_REDESIGN_PYTHON_GRID_001.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch


SOURCE_DIR = Path(os.environ["NEE_RELEASE_DATA_ROOT"]) / "figure_inputs" / "Fig3"
OUTPUT_DIR = Path(os.environ.get("NEE_OUTPUT_ROOT", Path(__file__).resolve().parents[2] / "outputs"))
OUTPUT_STEM = "Fig3_Nature_final_v01"

INPUTS = {
    "roles": SOURCE_DIR / "FIG3_panel_b_feature_roles.csv",
    "rmse": SOURCE_DIR / "FIG3_panel_c_RMSE.csv",
    "r2": SOURCE_DIR / "FIG3_panel_d_temporal_R2.csv",
    "hazard": SOURCE_DIR / "FIG3_panel_e_hazard_metrics.csv",
}

BLUE = "#1769AA"
BLUE_DARK = "#0B4F82"
BLUE_LIGHT = "#E7F1F8"
ORANGE = "#D97706"
ORANGE_DARK = "#A65300"
ORANGE_LIGHT = "#FFF0DE"
INK = "#172126"
MID = "#66747D"
LIGHT = "#D8E0E5"
PALE = "#F4F7F9"
WHITE = "#FFFFFF"

SCALES = ["SPEI-1", "SPEI-3", "SPEI-6"]
RULES = ["P1", "P2"]


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "DejaVu Sans"],
            "font.size": 7.4,
            "axes.titlesize": 9.0,
            "axes.titleweight": "bold",
            "axes.labelsize": 7.4,
            "axes.labelcolor": INK,
            "axes.edgecolor": MID,
            "axes.linewidth": 0.7,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "xtick.color": INK,
            "ytick.color": INK,
            "legend.fontsize": 6.5,
            "legend.frameon": False,
            "figure.facecolor": WHITE,
            "axes.facecolor": WHITE,
            "savefig.facecolor": WHITE,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def read_inputs() -> dict[str, pd.DataFrame]:
    missing = [str(path) for path in INPUTS.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing frozen Figure 3 source file(s): " + ", ".join(missing))

    frames = {key: pd.read_csv(path) for key, path in INPUTS.items()}
    required_columns = {
        "roles": {"feature_name", "role", "leakage_status", "information_time"},
        "rmse": {"spei_timescale", "prospective_rmse", "retrospective_rmse"},
        "r2": {"spei_timescale", "persistence_rule", "r2", "test_period"},
        "hazard": {"spei_timescale", "persistence_rule", "roc_auc", "test_period"},
    }
    for key, columns in required_columns.items():
        absent = columns.difference(frames[key].columns)
        if absent:
            raise ValueError(f"{INPUTS[key].name} is missing columns: {sorted(absent)}")

    if list(frames["rmse"]["spei_timescale"]) != SCALES:
        raise ValueError("Panel c SPEI scale order/content differs from the frozen design.")
    for key in ("r2", "hazard"):
        observed = set(zip(frames[key]["spei_timescale"], frames[key]["persistence_rule"]))
        expected = {(scale, rule) for scale in SCALES for rule in RULES}
        if observed != expected:
            raise ValueError(f"Panel {key} scale/rule combinations differ from the frozen design.")
        if set(frames[key]["test_period"].astype(str)) != {"2021-2023"}:
            raise ValueError(f"Panel {key} test period is not uniformly 2021-2023.")
    return frames


def panel_heading(ax: mpl.axes.Axes, label: str, title: str, *, y: float = 1.08) -> None:
    ax.text(
        -0.075,
        y,
        label,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.5,
        fontweight="bold",
        color=INK,
        clip_on=False,
    )
    ax.set_title(title, loc="left", color=INK, pad=12)


def clean_axes(ax: mpl.axes.Axes, grid_axis: str = "x") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(LIGHT)
    ax.spines["bottom"].set_color(LIGHT)
    ax.tick_params(length=3, width=0.6, pad=2.5)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=LIGHT, lw=0.65, alpha=0.72)


def rounded_stage(
    ax: mpl.axes.Axes,
    x: float,
    y: float,
    width: float,
    height: float,
    text: str,
    edge: str,
    fill: str,
    *,
    fontsize: float = 7.1,
) -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            width,
            height,
            boxstyle="round,pad=0.35,rounding_size=1.5",
            facecolor=fill,
            edgecolor=edge,
            linewidth=1.15,
            zorder=3,
        )
    )
    ax.text(
        x + width / 2,
        y + height / 2,
        text,
        ha="center",
        va="center",
        color=edge,
        fontsize=fontsize,
        fontweight="bold",
        linespacing=1.15,
        zorder=4,
    )


def arrow(
    ax: mpl.axes.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    color: str,
    *,
    connectionstyle: str = "arc3",
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start,
            end,
            arrowstyle="-|>",
            mutation_scale=9,
            linewidth=1.15,
            color=color,
            connectionstyle=connectionstyle,
            zorder=2,
        )
    )


def draw_panel_a(ax: mpl.axes.Axes) -> None:
    panel_heading(ax, "a", "Information boundaries determine apparent prediction skill", y=1.02)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    boundary_x = 21.0
    ax.axvspan(0, boundary_x, color=BLUE_LIGHT, alpha=0.48, zorder=0)
    ax.axvspan(boundary_x, 100, color=PALE, alpha=0.50, zorder=0)
    ax.plot([boundary_x, boundary_x], [8, 90], color=INK, lw=1.1, ls=(0, (3, 2)), zorder=5)
    ax.text(
        boundary_x,
        93,
        "DROUGHT-END INFORMATION BOUNDARY",
        ha="center",
        va="bottom",
        fontsize=6.4,
        fontweight="bold",
        color=INK,
    )

    ax.text(2.5, 84, "AVAILABLE BY DROUGHT END", color=BLUE_DARK, fontsize=6.4, fontweight="bold")
    ax.text(28, 84, "PROSPECTIVE PIPELINE", color=BLUE_DARK, fontsize=6.4, fontweight="bold")
    ax.text(28, 37, "FUTURE INFORMATION - DIAGNOSTIC USE ONLY", color=ORANGE_DARK, fontsize=6.4, fontweight="bold")

    rounded_stage(ax, 2.5, 51, 14.0, 22, "Observed\ndrought event", BLUE, BLUE_LIGHT)
    rounded_stage(ax, 27, 55, 16.5, 18, "Prospective\nfeature set", BLUE, BLUE_LIGHT)
    rounded_stage(ax, 50, 55, 13.0, 18, "Frozen\nmodel", BLUE, BLUE_LIGHT)
    rounded_stage(ax, 70, 55, 22.0, 18, "Spatial-block /\ntime validation", BLUE, BLUE_LIGHT)

    rounded_stage(ax, 29, 10, 21.0, 17, "Post-drought\nclimate + fire", ORANGE, ORANGE_LIGHT)
    rounded_stage(ax, 59, 10, 25.0, 17, "Retrospective\nassociation diagnostic", ORANGE, ORANGE_LIGHT)

    arrow(ax, (16.5, 62), (20.4, 62), BLUE)
    ax.add_patch(Circle((boundary_x, 62), radius=1.25, facecolor=WHITE, edgecolor=INK, lw=1.0, zorder=6))
    arrow(ax, (22.3, 64), (27, 64), BLUE)
    arrow(ax, (43.5, 64), (50, 64), BLUE)
    arrow(ax, (63, 64), (70, 64), BLUE)
    arrow(ax, (22.1, 58.5), (29, 18.5), ORANGE, connectionstyle="arc3,rad=0.12")
    arrow(ax, (50, 18.5), (59, 18.5), ORANGE)

    ax.text(81, 47, "Prediction", color=BLUE_DARK, fontsize=6.2, ha="center")
    ax.text(71.5, 5.2, "Association, not a prospective forecast", color=ORANGE_DARK, fontsize=6.2, ha="center")


def draw_panel_b(ax: mpl.axes.Axes, roles: pd.DataFrame) -> None:
    panel_heading(ax, "b", "Audited feature roles")
    mapping = [
        ("KNOWN_AT_DROUGHT_END", "Known at\ndrought end", BLUE),
        ("POST_DROUGHT_INFORMATION", "Post-drought", ORANGE),
        ("FUTURE_INFORMATION", "Future interval", ORANGE),
        ("EXCLUDED_FROM_PROSPECTIVE_FEATURE_SET", "Excluded", MID),
    ]
    counts = roles["leakage_status"].value_counts()
    labels = [label for _, label, _ in mapping]
    values = [int(counts.get(status, 0)) for status, _, _ in mapping]
    colors = [color for _, _, color in mapping]
    y = np.arange(len(mapping))[::-1]

    bars = ax.barh(y, values, color=colors, height=0.52, edgecolor=WHITE, linewidth=0.5)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Number of audited features")
    ax.set_xlim(0, max(values) * 1.23)
    ax.set_xticks([0, 5, 10, 15, 20])
    clean_axes(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    for bar, value, color in zip(bars, values, colors):
        ax.text(
            value + 0.40,
            bar.get_y() + bar.get_height() / 2,
            f"{value}",
            ha="left",
            va="center",
            fontsize=7.3,
            fontweight="bold",
            color=color,
        )
    ax.text(
        0.99,
        -0.25,
        f"n = {len(roles)} audited features",
        transform=ax.transAxes,
        ha="right",
        va="top",
        color=MID,
        fontsize=6.4,
    )


def draw_panel_c(ax: mpl.axes.Axes, rmse: pd.DataFrame) -> None:
    panel_heading(ax, "c", "Spatial-block RMSE")
    ordered = rmse.set_index("spei_timescale").loc[SCALES]
    y = np.arange(len(SCALES))[::-1]
    prospective = ordered["prospective_rmse"].to_numpy(float)
    retrospective = ordered["retrospective_rmse"].to_numpy(float)

    for idx, (yi, pro, retro) in enumerate(zip(y, prospective, retrospective)):
        ax.plot([retro, pro], [yi, yi], color=LIGHT, lw=3.0, solid_capstyle="round", zorder=1)
        ax.scatter(pro, yi, s=38, color=BLUE, edgecolor=WHITE, linewidth=0.6, zorder=3)
        ax.scatter(retro, yi, s=38, marker="s", color=ORANGE, edgecolor=WHITE, linewidth=0.6, zorder=3)
        ax.text(pro + 0.018, yi - 0.16, f"{pro:.2f}", color=BLUE_DARK, ha="left", va="top", fontsize=6.3)
        ax.text(retro - 0.018, yi - 0.16, f"{retro:.2f}", color=ORANGE_DARK, ha="right", va="top", fontsize=6.3)
        ax.text(
            (pro + retro) / 2,
            yi + 0.17,
            f"Delta {retro - pro:+.2f}",
            color=ORANGE_DARK,
            ha="center",
            va="bottom",
            fontsize=6.2,
            fontweight="bold",
        )

    ax.set_yticks(y, SCALES)
    ax.set_xlabel("RMSE (months)")
    ax.set_xlim(1.08, 1.58)
    ax.set_ylim(-0.50, 2.48)
    clean_axes(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [
        Line2D([], [], marker="o", ms=5, linestyle="none", color=BLUE, label="Prospective"),
        Line2D([], [], marker="s", ms=5, linestyle="none", color=ORANGE, label="Retrospective"),
    ]
    ax.legend(handles=handles, ncol=2, loc="upper center", bbox_to_anchor=(0.58, 1.03), columnspacing=1.2, handletextpad=0.4)
    ax.text(
        0.5,
        -0.25,
        "5-fold, 5-degree spatial blocks",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=6.4,
        color=MID,
    )


def draw_panel_d(ax: mpl.axes.Axes, r2: pd.DataFrame) -> None:
    panel_heading(ax, "d", "Fixed 2021-2023 exact-duration $R^2$")
    x = np.arange(len(SCALES), dtype=float)
    width = 0.28
    colors = {"P1": BLUE, "P2": ORANGE}
    offsets = {"P1": -width / 2, "P2": width / 2}

    for rule in RULES:
        sub = r2[r2["persistence_rule"].eq(rule)].set_index("spei_timescale").loc[SCALES]
        values = sub["r2"].to_numpy(float)
        xx = x + offsets[rule]
        bars = ax.bar(xx, values, width=width, color=colors[rule], label=rule, zorder=3)
        for bar, value in zip(bars, values):
            offset = 0.0019 if value >= 0 else -0.0019
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + offset,
                f"{value:.3f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                color=colors[rule],
                fontsize=6.1,
                fontweight="bold",
            )

    ax.axhline(0, color=MID, lw=0.8, zorder=2)
    ax.set_xticks(x, SCALES)
    ax.set_ylabel("$R^2$")
    ax.set_ylim(-0.032, 0.030)
    ax.set_yticks([-0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03])
    clean_axes(ax, "y")
    ax.legend(ncol=2, loc="upper right", handlelength=1.3, columnspacing=1.0)
    ax.text(
        0.01,
        -0.24,
        "Training: 2001-2020",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6.4,
        color=MID,
    )


def draw_panel_e(ax: mpl.axes.Axes, hazard: pd.DataFrame) -> None:
    panel_heading(ax, "e", "Monthly hazard ROC AUC")
    x = np.arange(len(SCALES), dtype=float)
    style = {
        "P1": (BLUE, "o", -0.012),
        "P2": (ORANGE, "s", 0.012),
    }

    ax.axhline(0.5, color=MID, lw=0.8, ls=(0, (3, 2)), zorder=1)
    for rule in RULES:
        sub = hazard[hazard["persistence_rule"].eq(rule)].set_index("spei_timescale").loc[SCALES]
        values = sub["roc_auc"].to_numpy(float)
        color, marker, xoff = style[rule]
        ax.plot(
            x + xoff,
            values,
            color=color,
            marker=marker,
            markersize=5.0,
            linewidth=1.6,
            label=rule,
            zorder=3,
        )
        for xi, value in zip(x + xoff, values):
            ax.text(
                xi,
                value + (0.011 if rule == "P2" else -0.013),
                f"{value:.3f}",
                ha="center",
                va="bottom" if rule == "P2" else "top",
                fontsize=6.1,
                fontweight="bold",
                color=color,
            )

    ax.set_xticks(x, SCALES)
    ax.set_ylabel("ROC AUC")
    ax.set_ylim(0.48, 0.70)
    ax.set_yticks([0.50, 0.55, 0.60, 0.65, 0.70])
    clean_axes(ax, "y")
    ax.legend(ncol=2, loc="upper left", handlelength=1.6, columnspacing=1.0)
    ax.text(1.98, 0.503, "Random", ha="right", va="bottom", fontsize=6.0, color=MID)
    ax.text(
        0.99,
        -0.24,
        "Evaluation: 2021-2023",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=6.4,
        color=MID,
    )


def build_figure(frames: dict[str, pd.DataFrame]) -> mpl.figure.Figure:
    configure_style()
    fig = plt.figure(figsize=(7.10, 8.55), facecolor=WHITE)
    grid = fig.add_gridspec(
        3,
        2,
        height_ratios=[0.88, 1.0, 1.0],
        left=0.105,
        right=0.985,
        bottom=0.085,
        top=0.965,
        wspace=0.38,
        hspace=0.58,
    )
    ax_a = fig.add_subplot(grid[0, :])
    ax_b = fig.add_subplot(grid[1, 0])
    ax_c = fig.add_subplot(grid[1, 1])
    ax_d = fig.add_subplot(grid[2, 0])
    ax_e = fig.add_subplot(grid[2, 1])

    draw_panel_a(ax_a)
    draw_panel_b(ax_b, frames["roles"])
    draw_panel_c(ax_c, frames["rmse"])
    draw_panel_d(ax_d, frames["r2"])
    draw_panel_e(ax_e, frames["hazard"])
    return fig


def write_outputs(fig: mpl.figure.Figure, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_script = Path(__file__).resolve()
    target_script = output_dir / f"{OUTPUT_STEM}.py"
    if source_script != target_script.resolve():
        shutil.copy2(source_script, target_script)

    metadata = {
        "Title": "Figure 3 - Information boundaries and predictive evaluation",
        "Author": "Frozen Figure 3 source tables; Python/matplotlib rendering",
        "Subject": "Read-only scientific figure redesign",
    }
    pdf = output_dir / f"{OUTPUT_STEM}.pdf"
    svg = output_dir / f"{OUTPUT_STEM}.svg"
    png = output_dir / f"{OUTPUT_STEM}.png"
    fig.savefig(pdf, format="pdf", metadata=metadata)
    fig.savefig(svg, format="svg", metadata={"Title": metadata["Title"]})
    fig.savefig(png, format="png", dpi=600, metadata={"Title": metadata["Title"]})
    return [target_script, pdf, svg, png]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frames = read_inputs()
    fig = build_figure(frames)
    outputs = write_outputs(fig, args.output_dir)
    plt.close(fig)
    print(f"matplotlib={mpl.__version__}")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
