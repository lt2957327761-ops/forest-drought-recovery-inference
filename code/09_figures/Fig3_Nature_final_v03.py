#!/usr/bin/env python3
"""Layout-only refinement of Fig3_Nature_final_v01.

The scientific panels, values, data sources, and validation rules are inherited
unchanged from v01. This script changes only layout, typography, annotation
wording, and visual hierarchy for TASK FIG3_STYLE_REFINEMENT_V03.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Circle


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import Fig3_Nature_final_v01 as base  # noqa: E402


OUTPUT_DIR = Path(os.environ.get("NEE_OUTPUT_ROOT", Path(__file__).resolve().parents[2] / "outputs"))
OUTPUT_STEM = "Fig3_Nature_final_v03"


def configure_style() -> None:
    base.configure_style()
    mpl.rcParams.update(
        {
            "axes.titlesize": 10.35,
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.0,
        }
    )


def panel_heading(ax: mpl.axes.Axes, label: str, title: str, *, y: float = 1.075) -> None:
    """Place label and title in one text object for exact baseline alignment."""
    ax.text(
        0.0,
        y,
        f"({label})   {title}",
        transform=ax.transAxes,
        ha="left",
        va="baseline",
        fontsize=10.35,
        fontweight="bold",
        color=base.INK,
        clip_on=False,
    )


def draw_panel_a(ax: mpl.axes.Axes) -> None:
    panel_heading(ax, "a", "Information boundaries determine apparent prediction skill", y=1.045)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    boundary_x = 21.0
    ax.axvspan(0, boundary_x, color=base.BLUE_LIGHT, alpha=0.48, zorder=0)
    ax.axvspan(boundary_x, 100, color=base.PALE, alpha=0.50, zorder=0)
    ax.plot([boundary_x, boundary_x], [8, 87], color=base.INK, lw=1.2, ls=(0, (3, 2)), zorder=5)
    ax.text(
        boundary_x,
        89,
        "DROUGHT-END BOUNDARY",
        ha="center",
        va="bottom",
        fontsize=7.0,
        fontweight="bold",
        color=base.INK,
    )

    ax.text(2.5, 77, "KNOWN AT DROUGHT END", color=base.BLUE_DARK, fontsize=7.0, fontweight="bold")
    ax.text(28, 77, "PROSPECTIVE PIPELINE", color=base.BLUE_DARK, fontsize=7.0, fontweight="bold")
    ax.text(28, 34, "FUTURE INFORMATION", color=base.ORANGE_DARK, fontsize=7.0, fontweight="bold")

    base.rounded_stage(ax, 2.5, 47, 14.0, 20, "Observed\ndrought event", base.BLUE, base.BLUE_LIGHT, fontsize=7.5)
    base.rounded_stage(ax, 27, 51, 16.5, 17, "Prospective\nfeature set", base.BLUE, base.BLUE_LIGHT, fontsize=7.5)
    base.rounded_stage(ax, 50, 51, 13.0, 17, "Frozen\nmodel", base.BLUE, base.BLUE_LIGHT, fontsize=7.5)
    base.rounded_stage(
        ax,
        70,
        51,
        22.0,
        17,
        "Spatial-block /\ntime validation",
        base.BLUE,
        base.BLUE_LIGHT,
        fontsize=7.5,
    )
    base.rounded_stage(
        ax,
        29,
        8,
        21.0,
        16,
        "Post-drought\nclimate + fire",
        base.ORANGE,
        base.ORANGE_LIGHT,
        fontsize=7.5,
    )
    base.rounded_stage(
        ax,
        59,
        8,
        25.0,
        16,
        "Retrospective\nassociation diagnostic",
        base.ORANGE,
        base.ORANGE_LIGHT,
        fontsize=7.5,
    )

    base.arrow(ax, (16.5, 57), (20.4, 57), base.BLUE)
    ax.add_patch(Circle((boundary_x, 57), radius=1.25, facecolor=base.WHITE, edgecolor=base.INK, lw=1.0, zorder=6))
    base.arrow(ax, (22.3, 59.5), (27, 59.5), base.BLUE)
    base.arrow(ax, (43.5, 59.5), (50, 59.5), base.BLUE)
    base.arrow(ax, (63, 59.5), (70, 59.5), base.BLUE)
    base.arrow(ax, (22.1, 54), (29, 16), base.ORANGE, connectionstyle="arc3,rad=0.12")
    base.arrow(ax, (50, 16), (59, 16), base.ORANGE)


def draw_panel_b(ax: mpl.axes.Axes, roles) -> None:
    panel_heading(ax, "b", "Audited feature roles")
    mapping = [
        ("KNOWN_AT_DROUGHT_END", "Known at\ndrought end", base.BLUE),
        ("POST_DROUGHT_INFORMATION", "Post-drought", base.ORANGE),
        ("FUTURE_INFORMATION", "Future interval", base.ORANGE),
        ("EXCLUDED_FROM_PROSPECTIVE_FEATURE_SET", "Excluded", base.MID),
    ]
    counts = roles["leakage_status"].value_counts()
    labels = [label for _, label, _ in mapping]
    values = [int(counts.get(status, 0)) for status, _, _ in mapping]
    colors = [color for _, _, color in mapping]
    y = np.arange(len(mapping))[::-1]

    bars = ax.barh(y, values, color=colors, height=0.52, edgecolor=base.WHITE, linewidth=0.5)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Number of audited features")
    ax.set_xlim(0, 35.5)
    ax.set_xticks([0, 10, 20, 30])
    ax.grid(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_color(base.LIGHT)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=3, width=0.6, pad=2.5)
    for bar, value, color in zip(bars, values, colors):
        ax.text(
            value + 0.50,
            bar.get_y() + bar.get_height() / 2,
            f"{value}",
            ha="left",
            va="center",
            fontsize=7.6,
            fontweight="bold",
            color=color,
        )

    group_counts = roles["feature_group"].fillna("unclassified").value_counts()
    major_groups = ["static forest", "fire", "soil-topography", "recovery climate", "drought severity"]
    other_groups = [group for group in group_counts.index if group not in major_groups]
    inset_labels = ["Static forest", "Fire", "Soil-topography", "Recovery climate", "Drought severity"]
    inset_values = [int(group_counts.get(group, 0)) for group in major_groups]
    inset_labels.append(f"Other ({len(other_groups)} groups)")
    inset_values.append(int(group_counts.loc[other_groups].sum()) if other_groups else 0)

    inset = ax.inset_axes([0.61, 0.105, 0.37, 0.50], zorder=6)
    inset.patch.set_facecolor(base.WHITE)
    inset.patch.set_edgecolor(base.LIGHT)
    inset.patch.set_linewidth(0.65)
    iy = np.arange(len(inset_labels))[::-1]
    inset.barh(iy, inset_values, height=0.52, color="#9AAEB9", alpha=0.76)
    inset.set_yticks(iy, inset_labels)
    inset.set_xlim(0, 7.4)
    inset.set_xticks([])
    inset.tick_params(axis="y", length=0, labelsize=5.4, pad=1.5)
    for spine in inset.spines.values():
        spine.set_color(base.LIGHT)
        spine.set_linewidth(0.6)
    for yi, value in zip(iy, inset_values):
        inset.text(value + 0.16, yi, str(value), ha="left", va="center", color=base.INK, fontsize=5.7, fontweight="bold")
    inset.text(
        0.03,
        1.04,
        "Feature categories",
        transform=inset.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.2,
        fontweight="bold",
        color=base.INK,
    )


def draw_panel_c(ax: mpl.axes.Axes, rmse) -> None:
    panel_heading(ax, "c", "Spatial-block RMSE")
    ordered = rmse.set_index("spei_timescale").loc[base.SCALES]
    y = np.arange(len(base.SCALES))[::-1]
    prospective = ordered["prospective_rmse"].to_numpy(float)
    retrospective = ordered["retrospective_rmse"].to_numpy(float)

    for yi, pro, retro in zip(y, prospective, retrospective):
        ax.plot([retro, pro], [yi, yi], color=base.LIGHT, lw=3.0, solid_capstyle="round", zorder=1)
        ax.scatter(pro, yi, s=42, color=base.BLUE, edgecolor=base.WHITE, linewidth=0.6, zorder=3)
        ax.scatter(retro, yi, s=42, marker="s", color=base.ORANGE, edgecolor=base.WHITE, linewidth=0.6, zorder=3)
        ax.text(pro + 0.018, yi - 0.16, f"{pro:.2f}", color=base.BLUE_DARK, ha="left", va="top", fontsize=6.6)
        ax.text(retro - 0.018, yi - 0.16, f"{retro:.2f}", color=base.ORANGE_DARK, ha="right", va="top", fontsize=6.6)
        ax.text(
            (pro + retro) / 2,
            yi + 0.17,
            rf"$\Delta$RMSE = {retro - pro:.2f}",
            color=base.ORANGE_DARK,
            ha="center",
            va="bottom",
            fontsize=6.5,
            fontweight="bold",
        )

    ax.set_yticks(y, base.SCALES)
    ax.set_xlabel("RMSE (months)")
    ax.set_xlim(1.08, 1.58)
    ax.set_ylim(-0.50, 2.48)
    base.clean_axes(ax, "x")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [
        Line2D([], [], marker="o", ms=5.3, linestyle="none", color=base.BLUE, label="Prospective"),
        Line2D([], [], marker="s", ms=5.3, linestyle="none", color=base.ORANGE, label="Retrospective"),
    ]
    ax.legend(handles=handles, ncol=2, loc="upper center", bbox_to_anchor=(0.58, 1.03), columnspacing=1.2, handletextpad=0.4)


def draw_panel_d(ax: mpl.axes.Axes, r2) -> None:
    panel_heading(ax, "d", "Fixed 2021-2023 exact-duration $R^2$")
    x = np.arange(len(base.SCALES), dtype=float)
    width = 0.28
    colors = {"P1": base.BLUE, "P2": base.ORANGE}
    offsets = {"P1": -width / 2, "P2": width / 2}
    label_offset = 0.0019

    for rule in base.RULES:
        sub = r2[r2["persistence_rule"].eq(rule)].set_index("spei_timescale").loc[base.SCALES]
        values = sub["r2"].to_numpy(float)
        xx = x + offsets[rule]
        bars = ax.bar(xx, values, width=width, color=colors[rule], label=f"{rule} persistence", zorder=3)
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + (label_offset if value >= 0 else -label_offset),
                f"{value:.3f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                color=colors[rule],
                fontsize=6.5,
                fontweight="bold",
            )

    ax.axhline(0, color=base.MID, lw=0.8, zorder=2)
    ax.set_xticks(x, base.SCALES)
    ax.set_ylabel("$R^2$")
    ax.set_ylim(-0.032, 0.030)
    ax.set_yticks([-0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03])
    base.clean_axes(ax, "y")
    ax.legend(ncol=1, loc="upper right", handlelength=1.3, labelspacing=0.25)


def draw_panel_e(ax: mpl.axes.Axes, hazard) -> None:
    panel_heading(ax, "e", "Monthly-hazard discrimination")
    x = np.arange(len(base.SCALES), dtype=float)
    style = {
        "P1": (base.BLUE, "o", -0.012, -0.0125, "top"),
        "P2": (base.ORANGE, "s", 0.012, 0.0105, "bottom"),
    }

    ax.axhline(0.5, color=base.MID, lw=0.8, ls=(0, (3, 2)), zorder=1)
    for rule in base.RULES:
        sub = hazard[hazard["persistence_rule"].eq(rule)].set_index("spei_timescale").loc[base.SCALES]
        values = sub["roc_auc"].to_numpy(float)
        color, marker, xoff, yoff, valign = style[rule]
        ax.plot(x + xoff, values, color=color, marker=marker, markersize=5.3, linewidth=1.6, label=rule, zorder=3)
        for xi, value in zip(x + xoff, values):
            ax.text(
                xi,
                value + yoff,
                f"{value:.3f}",
                ha="center",
                va=valign,
                fontsize=6.5,
                fontweight="bold",
                color=color,
            )

    ax.set_xticks(x, base.SCALES)
    ax.set_ylabel("ROC AUC")
    ax.set_ylim(0.48, 0.70)
    ax.set_yticks([0.50, 0.55, 0.60, 0.65, 0.70])
    base.clean_axes(ax, "y")
    ax.legend(ncol=2, loc="upper left", handlelength=1.6, columnspacing=1.0)
    ax.text(1.98, 0.503, "Random = 0.5", ha="right", va="bottom", fontsize=6.8, color=base.MID)


def build_figure(frames) -> mpl.figure.Figure:
    configure_style()
    fig = plt.figure(figsize=(7.10, 8.55), facecolor=base.WHITE)
    grid = fig.add_gridspec(
        3,
        2,
        height_ratios=[0.88, 1.0, 1.0],
        left=0.105,
        right=0.985,
        bottom=0.075,
        top=0.965,
        wspace=0.38,
        hspace=0.39,
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
        "Subject": "Layout-only refinement; scientific values unchanged",
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
    frames = base.read_inputs()
    fig = build_figure(frames)
    outputs = write_outputs(fig, args.output_dir)
    plt.close(fig)
    print(f"matplotlib={mpl.__version__}")
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
