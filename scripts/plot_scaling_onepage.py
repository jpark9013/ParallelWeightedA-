#!/usr/bin/env python3
"""Scaling figures for CS 5220 paper (see paper/data/DATA_INVENTORY.md).

Writes six individual figures to paper/figures/fig_scaling_01_*.pdf (+ .png).
Optional: --combined also writes fig_scaling_onepage.pdf (2x3 grid).
"""
from pathlib import Path
from typing import Optional

import argparse

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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


def read_sweep_sparse_dense_w5():
    """1 node, w=5, n1e9_sparse vs n1e9_dense, threads 1,2,32,128."""
    p = REPO / "results/sweep_w_threads/sweep.tsv"
    sparse, dense = {}, {}
    with open(p, encoding="utf-8") as f:
        f.readline()
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 8:
                continue
            nodes, w, gkey, th = int(parts[0]), int(parts[1]), parts[2], int(parts[3])
            if nodes != 1 or w != 5 or parts[4] != "0":
                continue
            if parts[5] == "NA":
                continue
            t = float(parts[6])
            if gkey == "n1e9_sparse":
                sparse[th] = t
            elif gkey == "n1e9_dense":
                dense[th] = t
    return sparse, dense


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


def plot_panel_01_strong_scaling(outdir: Path, nodes124: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    ns = [1, 2, 4]
    t1 = [nodes124[(n, 1)][0] for n in ns]
    ax.plot(ns, t1, "o-", color="#1f77b4", lw=2, ms=8, label=r"$w{=}1$, 1 thr/rank")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes (1 rank/node)")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Strong scaling: geom recommender medium $10^9$")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="upper right")
    _save(fig, outdir, "fig_scaling_01_strong_mpi_geom_medium")


def plot_panel_02_w_overlay(outdir: Path, w15: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    ns = [1, 2, 4]
    for w, sty, lab in ((1, "-", r"$w{=}1$"), (5, "--", r"$w{=}5$")):
        ys = [w15[(n, w)] for n in ns]
        ax.plot(ns, ys, sty, marker="s" if w == 5 else "o", lw=2, ms=7, label=lab)
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes (1 rank/node, 1 OpenMP thread/rank)")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Same graph: heuristic weight $w$")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    _save(fig, outdir, "fig_scaling_02_w_overlay_nodes")


def plot_panel_03_omp_threads(outdir: Path, nodes124: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 3.6), constrained_layout=True)
    ths = [1, 8]
    t2n = [nodes124[(2, t)][0] for t in ths]
    ax.bar([str(t) for t in ths], t2n, color=["#2ca02c", "#d62728"])
    ax.set_xlabel("OpenMP threads / rank")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("OpenMP at 2 nodes (geom medium $10^9$, $w{=}1$)")
    ax.grid(True, axis="y", alpha=0.3)
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
    ax.set_ylabel("Time (s)")
    ax.set_yscale("log")
    ax.set_title("Neighbor-generation cost (1 node, 1 MPI rank)")
    ax.grid(True, axis="y", alpha=0.3)
    _save(fig, outdir, "fig_scaling_04_neighbor_intensity")


def plot_panel_05_sparse_vs_dense(outdir: Path, sweep_s: dict, sweep_d: dict) -> None:
    fig, ax = plt.subplots(figsize=(5.5, 3.6), constrained_layout=True)
    thread_order = [1, 2, 32, 128]
    xs = np.arange(len(thread_order))
    w_plot = 5
    ys_s = [sweep_s.get(t, np.nan) for t in thread_order]
    ys_d = [sweep_d.get(t, np.nan) for t in thread_order]
    ax.plot(xs, ys_s, "o-", label="sparse $n{=}10^9$", color="#8c564b", lw=2)
    ax.plot(xs, ys_d, "s-", label="dense $n{=}10^9$", color="#e377c2", lw=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(t) for t in thread_order])
    ax.set_xlabel("Threads / node (1 MPI rank)")
    ax.set_ylabel("Wall time (s)")
    ax.set_title(f"Implicit grid: sparse vs dense ($w={w_plot}$, 1 node)")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    _save(fig, outdir, "fig_scaling_05_sparse_vs_dense_w5")


def plot_panel_06_load_balance(outdir: Path, lb: list) -> None:
    fig, ax = plt.subplots(figsize=(5.0, 3.6), constrained_layout=True)
    labs = [r[0].replace("_", "\n") for r in lb]
    ts = [r[1] for r in lb]
    ax.bar(labs, ts, color=["#1f77b4", "#ff7f0e"])
    ax.set_ylabel("Wall time (s)")
    ax.set_title("Baseline vs donation steal\n(2 nodes, 1 thr, geom medium $w{=}1$)")
    ax.grid(True, axis="y", alpha=0.3)
    for i, v in enumerate(ts):
        ax.text(i, v + 2, f"{v:.0f}s", ha="center", fontsize=9)
    _save(fig, outdir, "fig_scaling_06_load_balance_steal")


def plot_combined(outdir: Path, nodes124, w15, sweep_s, sweep_d, heavy, lb, grid1) -> None:
    fig, axes = plt.subplots(2, 3, figsize=(11.0, 6.8), constrained_layout=True)
    fig.suptitle(
        "Scaling summary (implicit graphs; 1 MPI rank/node unless noted)",
        fontsize=12,
        fontweight="bold",
    )
    ns = [1, 2, 4]
    ax = axes[0, 0]
    t1 = [nodes124[(n, 1)][0] for n in ns]
    ax.plot(ns, t1, "o-", color="#1f77b4", lw=2, ms=8, label=r"$w{=}1$, 1 thr/rank")
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("(1) Strong scaling: geom medium $10^9$, $w{=}1$")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper right")

    ax = axes[0, 1]
    for w, sty, lab in ((1, "-", r"$w{=}1$"), (5, "--", r"$w{=}5$")):
        ys = [w15[(n, w)] for n in ns]
        ax.plot(ns, ys, sty, marker="s" if w == 5 else "o", lw=2, ms=7, label=lab)
    ax.set_xticks(ns)
    ax.set_xlabel("MPI nodes")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("(2) Same graph, $w$ overlay (1 thr/rank)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[0, 2]
    ths = [1, 8]
    t2n = [nodes124[(2, t)][0] for t in ths]
    ax.bar([str(t) for t in ths], t2n, color=["#2ca02c", "#d62728"])
    ax.set_xlabel("OpenMP threads / rank")
    ax.set_ylabel("Wall time (s)")
    ax.set_title("(3) Threads @ 2 nodes, geom medium $w{=}1$")
    ax.grid(True, axis="y", alpha=0.3)

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
    ax.set_ylabel("Time (s)")
    ax.set_yscale("log")
    ax.set_title("(4) Neighbor cost (1n, 1 rank; heavy $=10^8$ parallel spec)")
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 1]
    thread_order = [1, 2, 32, 128]
    xs = np.arange(len(thread_order))
    w_plot = 5
    ys_s = [sweep_s.get(t, np.nan) for t in thread_order]
    ys_d = [sweep_d.get(t, np.nan) for t in thread_order]
    ax.plot(xs, ys_s, "o-", label="sparse $n{=}10^9$", color="#8c564b", lw=2)
    ax.plot(xs, ys_d, "s-", label="dense $n{=}10^9$", color="#e377c2", lw=2)
    ax.set_xticks(xs)
    ax.set_xticklabels([str(t) for t in thread_order])
    ax.set_xlabel("Threads / node (1 MPI rank)")
    ax.set_ylabel("Wall time (s)")
    ax.set_title(f"(5) Sparse vs dense grid, $w={w_plot}$, 1 node")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    ax = axes[1, 2]
    labs = [r[0].replace("_", "\n") for r in lb]
    ts = [r[1] for r in lb]
    ax.bar(labs, ts, color=["#1f77b4", "#ff7f0e"])
    ax.set_ylabel("Wall time (s)")
    ax.set_title("(6) Load balance: baseline vs steal\n(2n, 1 thr, geom medium $w{=}1$)")
    ax.grid(True, axis="y", alpha=0.3)
    for i, v in enumerate(ts):
        ax.text(i, v + 2, f"{v:.0f}s", ha="center", fontsize=9)

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
    sweep_s, sweep_d = read_sweep_sparse_dense_w5()
    heavy = read_compute_heavy_omp()
    lb = read_load_balance()
    grid1 = read_grid_sparse_1n1t()

    plot_panel_01_strong_scaling(outdir, nodes124)
    plot_panel_02_w_overlay(outdir, w15)
    plot_panel_03_omp_threads(outdir, nodes124)
    plot_panel_04_neighbor_intensity(outdir, nodes124, heavy, grid1)
    plot_panel_05_sparse_vs_dense(outdir, sweep_s, sweep_d)
    plot_panel_06_load_balance(outdir, lb)

    if args.combined:
        plot_combined(outdir, nodes124, w15, sweep_s, sweep_d, heavy, lb, grid1)


if __name__ == "__main__":
    main()
