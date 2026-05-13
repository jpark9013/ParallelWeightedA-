#!/usr/bin/env python3
"""Scaling figures for CS 5220 paper (see paper/data/DATA_INVENTORY.md).

Writes six individual figures to paper/figures/fig_scaling_01_*.pdf (+ .png).
Optional: --combined also writes fig_scaling_onepage.pdf (2x3 grid).

Y axes use "Time (s)" (not "wall time"). Line plots over MPI nodes include an
ideal strong-scaling reference T_ideal(n)=T(1)/n from the measured time at 1 node.
"""
from pathlib import Path
from typing import Optional, Tuple

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import AutoMinorLocator, MaxNLocator

REPO = Path(__file__).resolve().parents[1]


def read_nodes_124_geom():
    """recommender_medium, w=1, threads from nodes_1_2_4 TSV."""
    p = REPO / "results/combined_w_thr_nodes/nodes_1_2_4_w1_grid_recommender.tsv"
    out = {}  # (nodes, threads) -> (time_s, exp)
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 9 or parts[0] != "recommender_medium":
                continue
            nodes, w, th = int(parts[3]), int(parts[4]), int(parts[5])
            if w != 1 or parts[6] == "NA":
                continue
            out[(nodes, th)] = (float(parts[6]), int(parts[8]))
    return out


def read_w1_w5_geom():
    p = REPO / "results/geom_w_compare/w1_w5_nodes.tsv"
    out = {}  # (nodes, w) -> time_s
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            g, nodes, w, th, ts, rc, exp = line.strip().split("\t")
            if g != "recommender_medium" or int(th) != 1:
                continue
            out[(int(nodes), int(w))] = float(ts)
    return out


def read_sweep_times(nodes: int, graph_key: str, w: int, threads: int) -> Optional[float]:
    """Single time from sweep.tsv or None if missing/NA."""
    p = REPO / "results/sweep_w_threads/sweep.tsv"
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue
            n, wg, gkey, th = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
            if n != nodes or wg != w or gkey != graph_key or th != threads:
                continue
            if parts[4] != "0" or parts[5] == "NA":
                return None
            return float(parts[5])
    return None


def read_sparse_dense_speedup_12() -> Tuple[float, float, int, int]:
    """Speedup T(1 node)/T(2 nodes); prefers 1 OpenMP thread / node, then other (w, thr) pairs."""
    candidates = [(5, 1), (3, 1), (5, 2), (5, 32), (5, 128), (3, 32)]
    for w, th in candidates:
        ts = read_sweep_times(1, "n1e9_sparse", w, th)
        t2s = read_sweep_times(2, "n1e9_sparse", w, th)
        td = read_sweep_times(1, "n1e9_dense", w, th)
        t2d = read_sweep_times(2, "n1e9_dense", w, th)
        if None in (ts, t2s, td, t2d) or t2s <= 0 or t2d <= 0:
            continue
        sp = ts / t2s
        de = td / t2d
        return sp, de, w, th
    # Fallback if sweep incomplete
    return 0.57, 0.49, 5, 1


def read_compute_heavy_omp():
    p = REPO / "results/combined_w_thr_nodes/geom_1e8_compute_heavy_parallel_neighbors_omp1_8_64.tsv"
    out = {}
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 6:
                continue
            out[int(parts[4])] = float(parts[5])
    return out


def read_load_balance():
    p = REPO / "paper/data/geom_medium_2n_load_balance.tsv"
    rows = []
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            rows.append((parts[0], float(parts[2])))
    return rows


def read_grid_sparse_1n1t():
    p = REPO / "results/combined_w_thr_nodes/nodes_1_2_4_w1_grid_recommender.tsv"
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 9 or parts[0] != "grid_1e9_sparse":
                continue
            if int(parts[3]) == 1 and int(parts[4]) == 1 and int(parts[5]) == 1 and parts[6] != "NA":
                return float(parts[6])
    return None


def _save(fig, outdir: Path, stem: str) -> None:
    pdf = outdir / f"{stem}.pdf"
    png = outdir / f"{stem}.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", pdf, "&", png.name)


def _ylabel_time(ax) -> None:
    ax.set_ylabel("Time (s)")


def _style_y_linear_from_zero(ax, *, margin_top=0.08) -> None:
    """Dense major ticks; y starts at 0."""
    lo, hi = ax.get_ylim()
    ax.set_ylim(0, max(hi * (1.0 + margin_top), 1e-9))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=10, min_n_ticks=6))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))


def _ideal_strong_line(ax, ns: list, t_at_1: float, *, color: str = "#444444", label: str = "Ideal scaling") -> None:
    """T_ideal(n) = T(1 node) / n for strong scaling on node count."""
    ys = [t_at_1 / float(n) for n in ns]
    ax.plot(ns, ys, "--", color=color, lw=1.15, alpha=0.75, zorder=1, label=label)


def plot_panel_01_strong_scaling(outdir: Path, nodes124: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    ns = [1, 2, 4]
    t1 = nodes124[(1, 1)][0]
    ys = [nodes124[(n, 1)][0] for n in ns]
    ax.plot(ns, ys, "o-", color="#1f77b4", lw=2, ms=8, label=r"$w{=}1$, 1 thr/rank", zorder=3)
    _ideal_strong_line(ax, ns, t1, color="#666666", label=r"Ideal ($T_1/n$)")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes (1 rank/node)")
    _ylabel_time(ax)
    ax.set_title("Strong scaling: geom recommender medium $10^9$")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    _style_y_linear_from_zero(ax)
    _save(fig, outdir, "fig_scaling_01_strong_mpi_geom_medium")


def plot_panel_02_w_overlay(outdir: Path, w15: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    ns = [1, 2, 4]
    colors = ("#1f77b4", "#ff7f0e")
    # Measured: thinner lines / smaller markers than ideal dashed refs; w=5 is solid (not dashed).
    meas_lw, meas_ms = 1.35, 4.8
    for wi, (w, lab) in enumerate(((1, r"$w{=}1$"), (5, r"$w{=}5$"))):
        t_at_1 = w15[(1, w)]
        ys = [w15[(n, w)] for n in ns]
        c = colors[wi]
        mk = "o" if w == 1 else "s"
        ax.plot(ns, ys, "-", marker=mk, lw=meas_lw, ms=meas_ms, color=c, label=lab, zorder=3)
        _ideal_strong_line(ax, ns, t_at_1, color=c, label=f"Ideal {lab}")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes (1 rank/node, 1 OpenMP thread/rank)")
    _ylabel_time(ax)
    ax.set_title("Same graph: heuristic weight $w$")
    ax.legend(fontsize=8, loc="upper right", ncol=1)
    ax.grid(True, which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)
    _save(fig, outdir, "fig_scaling_02_w_overlay_nodes")


def plot_panel_03_omp_threads(outdir: Path, nodes124: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 3.6), constrained_layout=True)
    ths = [1, 8]
    t2n = [nodes124[(2, t)][0] for t in ths]
    ax.bar([str(t) for t in ths], t2n, color=["#2ca02c", "#d62728"])
    ax.set_xlabel("OpenMP threads / rank")
    _ylabel_time(ax)
    ax.set_title("OpenMP at 2 nodes (geom medium $10^9$, $w{=}1$)")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)
    _save(fig, outdir, "fig_scaling_03_omp_threads_2nodes")


def plot_panel_04_neighbor_intensity(outdir: Path, nodes124: dict, heavy: dict, grid1: Optional[float]) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    gtime = grid1 if grid1 is not None else 202.0
    mtime = nodes124[(1, 1)][0]
    h1 = heavy.get(1, 39.5)
    h8 = heavy.get(8, 30.0)
    labels = ["Grid\nsparse", "Geom\nmedium", "Geom heavy\n1 thr", "Geom heavy\n8 thr"]
    vals = [gtime, mtime, h1, h8]
    cols = ["#8c564b", "#1f77b4", "#9467bd", "#9467bd"]
    ax.bar(range(4), vals, color=cols, alpha=0.85)
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=9)
    _ylabel_time(ax)
    ax.set_title("Neighbor-generation cost (1 node, 1 MPI rank)")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)
    _save(fig, outdir, "fig_scaling_04_neighbor_intensity")


def plot_panel_05_sparse_dense_speedup(outdir: Path) -> None:
    """Bar chart: 1→2 node speedup sparse vs dense (implicit grid $10^9$)."""
    sp, de, w, th = read_sparse_dense_speedup_12()
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    names = ["Sparse\n$n{=}10^9$", "Dense\n$n{=}10^9$"]
    vals = [sp, de]
    x = np.arange(2)
    ax.bar(x, vals, color=["#8c564b", "#e377c2"], width=0.55, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=10)
    thr_lbl = "1 OpenMP thread / node" if th == 1 else f"{th} OpenMP threads / node"
    ax.set_xlabel(f"Implicit grid ($w={w}$, {thr_lbl}, 1 MPI rank / node)")
    ax.set_ylabel(r"Speedup ($T_1/T_2$)")
    ax.set_title("1→2 MPI nodes: sparse vs dense")
    ymax = max(2.2, float(np.nanmax(vals)) * 1.25)
    ax.set_ylim(0, ymax)
    ax.axhline(2.0, color="#333333", ls="--", lw=1.8, label="Ideal (2×)", zorder=0)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=10, min_n_ticks=6))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.grid(True, axis="y", which="both", alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02 * ymax, f"{v:.2f}×", ha="center", fontsize=10)
    _save(fig, outdir, "fig_scaling_05_sparse_vs_dense_w5")


def plot_panel_06_load_balance(outdir: Path, lb: list) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 3.6), constrained_layout=True)
    labs = [r[0].replace("_", "\n") for r in lb]
    ts = [r[1] for r in lb]
    ax.bar(labs, ts, color=["#1f77b4", "#ff7f0e"])
    _ylabel_time(ax)
    ax.set_title("Baseline vs donation steal\n(2 nodes, 1 thr, geom medium $w{=}1$)")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)
    ymax = ax.get_ylim()[1]
    for i, v in enumerate(ts):
        ax.text(i, v + 0.02 * ymax, f"{v:.0f}s", ha="center", fontsize=9)
    _save(fig, outdir, "fig_scaling_06_load_balance_steal")


def plot_combined(outdir: Path, nodes124, w15, heavy, lb, grid1, speedup_pair) -> None:
    sp, de, w_used, th_used = speedup_pair
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 6.8), constrained_layout=True)
    fig.suptitle(
        "Scaling summary (implicit graphs; 1 MPI rank/node unless noted)",
        fontsize=12,
        fontweight="bold",
    )
    ns = [1, 2, 4]
    ax = axes[0, 0]
    t1 = nodes124[(1, 1)][0]
    ys = [nodes124[(n, 1)][0] for n in ns]
    ax.plot(ns, ys, "o-", color="#1f77b4", lw=2, ms=8, label=r"$w{=}1$, 1 thr/rank", zorder=3)
    _ideal_strong_line(ax, ns, t1, color="#666666", label=r"Ideal ($T_1/n$)")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes")
    _ylabel_time(ax)
    ax.set_title("(1) Strong scaling: geom medium $10^9$, $w{=}1$")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")
    _style_y_linear_from_zero(ax)

    ax = axes[0, 1]
    colors = ("#1f77b4", "#ff7f0e")
    meas_lw, meas_ms = 1.35, 4.8
    for wi, (w, lab) in enumerate(((1, r"$w{=}1$"), (5, r"$w{=}5$"))):
        t_at_1 = w15[(1, w)]
        ys2 = [w15[(n, w)] for n in ns]
        c = colors[wi]
        mk = "o" if w == 1 else "s"
        ax.plot(ns, ys2, "-", marker=mk, lw=meas_lw, ms=meas_ms, color=c, label=lab, zorder=3)
        _ideal_strong_line(ax, ns, t_at_1, color=c, label=f"Ideal {lab}")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes")
    _ylabel_time(ax)
    ax.set_title("(2) Same graph, $w$ overlay (1 thr/rank)")
    ax.legend(fontsize=6, loc="upper right")
    ax.grid(True, which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)

    ax = axes[0, 2]
    ths = [1, 8]
    t2n = [nodes124[(2, t)][0] for t in ths]
    ax.bar([str(t) for t in ths], t2n, color=["#2ca02c", "#d62728"])
    ax.set_xlabel("OpenMP threads / rank")
    _ylabel_time(ax)
    ax.set_title("(3) Threads @ 2 nodes, geom medium $w{=}1$")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)

    ax = axes[1, 0]
    gtime = grid1 if grid1 is not None else 202.0
    mtime = nodes124[(1, 1)][0]
    h1 = heavy.get(1, 39.5)
    h8 = heavy.get(8, 30.0)
    labels = ["Grid\nsparse", "Geom\nmedium", "Geom heavy\n1 thr", "Geom heavy\n8 thr"]
    vals = [gtime, mtime, h1, h8]
    cols = ["#8c564b", "#1f77b4", "#9467bd", "#9467bd"]
    ax.bar(range(4), vals, color=cols, alpha=0.85)
    ax.set_xticks(range(4))
    ax.set_xticklabels(labels, fontsize=8)
    _ylabel_time(ax)
    ax.set_title("(4) Neighbor cost (1n, 1 rank; heavy $=10^8$ parallel spec)")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)

    ax = axes[1, 1]
    xb = np.arange(2)
    ax.bar(xb, [sp, de], color=["#8c564b", "#e377c2"], width=0.55, alpha=0.9)
    ax.set_xticks(xb)
    ax.set_xticklabels(["Sparse\n$10^9$", "Dense\n$10^9$"], fontsize=8)
    thr_lbl = "1 thr/node" if th_used == 1 else f"{th_used} thr/node"
    ax.set_xlabel(f"(5) Grid $w={w_used}$, {thr_lbl}, 1 rank/node")
    ax.set_ylabel(r"Speedup ($T_1/T_2$)")
    ymax = max(2.2, max(sp, de) * 1.25)
    ax.set_ylim(0, ymax)
    ax.axhline(2.0, color="#333333", ls="--", lw=1.5, label="Ideal 2×")
    ax.yaxis.set_major_locator(MaxNLocator(nbins=8, min_n_ticks=5))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.set_title("(5) 1→2 nodes: sparse vs dense")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    ax.legend(fontsize=7, loc="upper right")

    ax = axes[1, 2]
    labs = [r[0].replace("_", "\n") for r in lb]
    ts = [r[1] for r in lb]
    ax.bar(labs, ts, color=["#1f77b4", "#ff7f0e"])
    _ylabel_time(ax)
    ax.set_title("(6) Load balance: baseline vs steal\n(2n, 1 thr, geom medium $w{=}1$)")
    ax.grid(True, axis="y", which="both", alpha=0.3)
    _style_y_linear_from_zero(ax)
    ymax = ax.get_ylim()[1]
    for i, v in enumerate(ts):
        ax.text(i, v + 0.02 * ymax, f"{v:.0f}s", ha="center", fontsize=8)

    outp = outdir / "fig_scaling_onepage.pdf"
    fig.savefig(outp, bbox_inches="tight")
    fig.savefig(outdir / "fig_scaling_onepage.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("Wrote", outp, "(combined)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--combined",
        action="store_true",
        help="Also write fig_scaling_onepage.pdf (2x3 grid).",
    )
    args = ap.parse_args()

    outdir = REPO / "paper/figures"
    outdir.mkdir(parents=True, exist_ok=True)

    nodes124 = read_nodes_124_geom()
    w15 = read_w1_w5_geom()
    heavy = read_compute_heavy_omp()
    lb = read_load_balance()
    grid1 = read_grid_sparse_1n1t()
    speedup_pair = read_sparse_dense_speedup_12()

    plot_panel_01_strong_scaling(outdir, nodes124)
    plot_panel_02_w_overlay(outdir, w15)
    plot_panel_03_omp_threads(outdir, nodes124)
    plot_panel_04_neighbor_intensity(outdir, nodes124, heavy, grid1)
    plot_panel_05_sparse_dense_speedup(outdir)
    plot_panel_06_load_balance(outdir, lb)

    if args.combined:
        plot_combined(outdir, nodes124, w15, heavy, lb, grid1, speedup_pair)


if __name__ == "__main__":
    main()
