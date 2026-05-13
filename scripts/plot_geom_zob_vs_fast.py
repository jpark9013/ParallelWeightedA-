#!/usr/bin/env python3
"""Bar chart: astar_mpi_fast vs astar_mpi_zob from results/geom_zob_vs_fast/bench.tsv.

Uses the last row per (variant, nodes, mpi_ranks, omp_threads) with rc==0 and finite time_s.
Writes PNG + PDF next to the TSV by default.
"""
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_bench_tsv(path: Path) -> List[List[str]]:
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    if len(lines) < 2:
        return []
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 10:
            rows.append(parts)
    return rows


def last_times_by_key(rows: List[List[str]]) -> Dict[Tuple[str, int, int, int], float]:
    """(variant, nodes, ranks, omp) -> time_s (last row wins)."""
    out: Dict[Tuple[str, int, int, int], float] = {}
    for p in rows:
        variant = p[1]
        try:
            nodes = int(p[2])
            ranks = int(p[3])
            omp = int(p[4])
            rc = int(p[9])
            ts = float(p[6])
        except (ValueError, IndexError):
            continue
        if rc != 0:
            continue
        key = (variant, nodes, ranks, omp)
        out[key] = ts
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/geom_zob_vs_fast/bench.tsv",
    )
    ap.add_argument("--out", type=Path, default=None, help="PNG path (PDF gets same stem)")
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    inp = args.input
    if args.out is None:
        out_png = inp.parent / "fig_geom_zob_vs_fast.png"
    else:
        out_png = args.out
    out_pdf = out_png.with_suffix(".pdf")

    times = last_times_by_key(read_bench_tsv(inp))

    # Default matrix from bench_geom_zob_vs_fast.sh
    configs = [
        (1, 1, 1, "1 node\n1 OpenMP thread"),
        (1, 1, 8, "1 node\n8 threads"),
        (2, 2, 1, "2 nodes\n1 thread / rank"),
        (2, 2, 8, "2 nodes\n8 threads / rank"),
    ]

    x = list(range(len(configs)))
    w = 0.36
    fast_vals: List[Optional[float]] = []
    zob_vals: List[Optional[float]] = []
    for nodes, ranks, omp, _ in configs:
        tf = times.get(("fast", nodes, ranks, omp))
        tz = times.get(("zob_pq", nodes, ranks, omp))
        fast_vals.append(tf)
        zob_vals.append(tz)

    finite = [v for v in fast_vals + zob_vals if v is not None]
    ymax = max(finite, default=1.0) * 1.18
    ymax = max(ymax, 1.0)

    fig, ax = plt.subplots(figsize=(8.2, 4.6))
    x0 = [i - w / 2 for i in x]
    x1 = [i + w / 2 for i in x]

    def bars(xs, vals, label, color, hatch):
        rects = []
        for xi, v in zip(xs, vals):
            if v is None:
                rects.append(None)
                ax.text(xi, ymax * 0.02, "no\ndata", ha="center", va="bottom", fontsize=7, color="0.4")
                continue
            r = ax.bar([xi], [v], width=w, color=color, edgecolor="0.25", linewidth=0.6, hatch=hatch)[0]
            rects.append(r)
            ax.annotate(
                f"{v:.1f}s",
                xy=(xi, v),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                fontsize=8,
                color="0.15",
            )
        # Legend proxy: one invisible bar with label
        ax.bar([], [], width=w, label=label, color=color, edgecolor="0.25", hatch=hatch)
        return rects

    bars(x0, fast_vals, "astar_mpi_fast (shared OPEN / rank)", "#4C72B0", "")
    bars(x1, zob_vals, "astar_mpi_zob (per-thread OPEN)", "#DD8452", "//")

    ax.set_xticks(x)
    ax.set_xticklabels([c[3] for c in configs], fontsize=10)
    ax.set_ylabel("Wall time (s)")
    ax.set_ylim(0, ymax)
    ax.set_title("Geom recommender medium n=1e9 (start=0, goal=1e9−1, w=1)")
    ax.legend(loc="upper left", frameon=True, fontsize=9)
    ax.grid(axis="y", linestyle=":", alpha=0.75)
    fig.tight_layout()
    try:
        rel = os.path.relpath(str(inp), str(repo))
    except ValueError:
        rel = str(inp)
    ax.text(
        0.99,
        0.02,
        f"Source: {rel}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7,
        color="0.45",
    )

    fig.savefig(out_png, dpi=160)
    fig.savefig(out_pdf)
    print(f"Wrote {out_png}")
    print(f"Wrote {out_pdf}")


if __name__ == "__main__":
    main()
