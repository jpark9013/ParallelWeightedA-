#!/usr/bin/env python3
"""Bar chart from results/geom_mpi_per_core/bench.tsv (mpi_per_core runs).

Uses the last successful row (rc==0) per mpi_ranks for variant mpi_per_core.
"""
import argparse
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def read_rows(path: Path) -> List[List[str]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    lines = text.splitlines()
    rows = []
    for line in lines[1:]:
        parts = line.split("\t")
        if len(parts) >= 10:
            rows.append(parts)
    return rows


def last_time_per_ranks(rows: List[List[str]]) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for p in rows:
        if p[1] != "mpi_per_core":
            continue
        try:
            ranks = int(p[3])
            rc = int(p[9])
            ts = float(p[6])
        except (ValueError, IndexError):
            continue
        if rc != 0:
            continue
        out[ranks] = ts
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/geom_mpi_per_core/bench.tsv",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    repo = Path(__file__).resolve().parents[1]
    inp = args.input
    out_png = inp.parent / "fig_geom_mpi_per_core.png" if args.out is None else args.out
    out_pdf = out_png.with_suffix(".pdf")

    times = last_time_per_ranks(read_rows(inp))
    order = sorted(times.keys())

    if not order:
        order = [1, 8, 128]

    labels = []
    vals: List[Optional[float]] = []
    for r in order:
        labels.append("%d rank%s\n(%d core%s)" % (r, "s" if r != 1 else "", r, "s" if r != 1 else ""))
        vals.append(times.get(r))

    finite = [v for v in vals if v is not None]
    ymax = max(finite, default=1.0) * 1.2
    ymax = max(ymax, 1.0)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    xs = list(range(len(order)))
    for i, (xi, v) in enumerate(zip(xs, vals)):
        if v is None:
            ax.text(xi, ymax * 0.02, "no\ndata", ha="center", va="bottom", fontsize=8, color="0.4")
            continue
        ax.bar([xi], [v], width=0.65, color="#55A868", edgecolor="0.25", linewidth=0.6)
        ax.annotate(
            "%.1fs" % v,
            xy=(xi, v),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=9,
            color="0.15",
        )

    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Wall time (s)")
    ax.set_ylim(0, ymax)
    ax.set_title("Geom recommender medium n=1e9 — MPI 1 rank : 1 core (OMP=1)")
    ax.grid(axis="y", linestyle=":", alpha=0.75)
    try:
        rel = os.path.relpath(str(inp), str(repo))
    except ValueError:
        rel = str(inp)
    ax.text(0.99, 0.02, "Source: %s" % rel, transform=ax.transAxes, ha="right", va="bottom", fontsize=7, color="0.45")

    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    fig.savefig(out_pdf)
    print("Wrote %s" % out_png)
    print("Wrote %s" % out_pdf)


if __name__ == "__main__":
    main()
