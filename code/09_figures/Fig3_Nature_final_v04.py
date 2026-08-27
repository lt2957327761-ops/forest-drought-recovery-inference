#!/usr/bin/env python3
"""Micro-layout refinement of Fig3_Nature_final_v03.

Only three visual parameters differ from v03: the x position of the blue-zone
label in panel (a), the GridSpec vertical spacing, and the y position of the top
delta annotation in panel (c). Scientific content and sources are unchanged.
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

import Fig3_Nature_final_v03 as v03  # noqa: E402


base = v03.base
OUTPUT_DIR = Path(os.environ.get("NEE_OUTPUT_ROOT", Path(__file__).resolve().parents[2] / "outputs"))
OUTPUT_STEM = "Fig3_Nature_final_v04"


def draw_panel_a(ax: mpl.axes.Axes) -> None:
    v03.panel_heading(ax, "a", "Information boundaries determine apparent prediction skill", y=1.045)
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

    # v04 micro-adjustment: x=0.2 (v03 used x=2.5), leaving clear air before the gate.
    ax.text(0.2, 77, "KNOWN AT DROUGHT END", color=base.BLUE_DARK, fontsize=7.0, fontweight="bold")
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


def draw_panel_c(ax: mpl.axes.Axes, rmse) -> None:
    v03.panel_heading(ax, "c", "Spatial-block RMSE")
    ordered = rmse.set_index("spei_timescale").loc[base.SCALES]
    y = np.arange(len(base.SCALES))[::-1]
    prospective = ordered["prospective_rmse"].to_numpy(float)
    retrospective = ordered["retrospective_rmse"].to_numpy(float)

    for index, (yi, pro, retro) in enumerate(zip(y, prospective, retrospective)):
        ax.plot([retro, pro], [yi, yi], color=base.LIGHT, lw=3.0, solid_capstyle="round", zorder=1)
        ax.scatter(pro, yi, s=42, color=base.BLUE, edgecolor=base.WHITE, linewidth=0.6, zorder=3)
        ax.scatter(retro, yi, s=42, marker="s", color=base.ORANGE, edgecolor=base.WHITE, linewidth=0.6, zorder=3)
        ax.text(pro + 0.018, yi - 0.16, f"{pro:.2f}", color=base.BLUE_DARK, ha="left", va="top", fontsize=6.6)
        ax.text(retro - 0.018, yi - 0.16, f"{retro:.2f}", color=base.ORANGE_DARK, ha="right", va="top", fontsize=6.6)
        delta_offset = 0.10 if index == 0 else 0.17
        ax.text(
            (pro + retro) / 2,
            yi + delta_offset,
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


def build_figure(frames) -> mpl.figure.Figure:
    v03.configure_style()
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
        hspace=0.34,
    )
    ax_a = fig.add_subplot(grid[0, :])
    ax_b = fig.add_subplot(grid[1, 0])
    ax_c = fig.add_subplot(grid[1, 1])
    ax_d = fig.add_subplot(grid[2, 0])
    ax_e = fig.add_subplot(grid[2, 1])

    draw_panel_a(ax_a)
    v03.draw_panel_b(ax_b, frames["roles"])
    draw_panel_c(ax_c, frames["rmse"])
    v03.draw_panel_d(ax_d, frames["r2"])
    v03.draw_panel_e(ax_e, frames["hazard"])
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
        "Subject": "Micro-layout refinement; scientific values unchanged",
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
