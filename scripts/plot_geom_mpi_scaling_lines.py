#!/usr/bin/env python3
"""Log-log line plot: geom MPI strong scaling (1 vs 2 nodes) + ideal scaling curves.

Reads results/geom_mpi_scaling/bench.tsv (series 1node / 2node).
X: cores per node (1 node: mpi_ranks; 2 nodes: mpi_ranks/2), log base 2.
Y: time (s), log scale.
Ideal 1-node: T(c)=T(1)/c.  Ideal 2-node: T(c)=T(2)/c (c = cores per node; 2 ranks at c=1).
"""
import argparse
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def read_rows(path: Path) -> List[List[str]]:
    if not path.is_file():
        return []
    t = path.read_text(encoding="utf-8").strip()
    if not t:
        return []
    lines = t.splitlines()
    out: List[List[str]] = []
    for line in lines[1:]:
        p = line.split("\t")
        if len(p) >= 10:
            out.append(p)
    return out


def last_per_series_ranks(rows: List[List[str]]) -> Tuple[Dict[Tuple[str, int], float], Dict[Tuple[str, int], float]]:
    """(series, ranks) -> time_s and cost (last rc==0 wins)."""
    times: Dict[Tuple[str, int], float] = {}
    costs: Dict[Tuple[str, int], float] = {}
    for p in rows:
        series = p[1]
        if series not in ("1node", "2node"):
            continue
        try:
            ranks = int(p[3])
            rc = int(p[9])
            ts = float(p[6])
            cost = float(p[8]) if p[8] != "NA" else float("nan")
        except (ValueError, IndexError):
            continue
        if rc != 0:
            continue
        key = (series, ranks)
        times[key] = ts
        if not math.isnan(cost):
            costs[key] = cost
    return times, costs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results/geom_mpi_scaling/bench.tsv",
    )
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    inp = args.input
    out_png = inp.parent / "fig_geom_mpi_scaling_lines.png" if args.out is None else args.out
    out_pdf = out_png.with_suffix(".pdf")

    times, _costs = last_per_series_ranks(read_rows(inp))

    ranks_1 = [1, 2, 4, 8, 16, 32, 64, 128]
    ranks_2 = [2, 4, 8, 16, 32, 64, 128, 256]

    def cores_per_node(series: str, mpi_ranks: int) -> int:
        if series == "1node":
            return mpi_ranks
        return mpi_ranks // 2

    def series_y(series: str, ranks: List[int]) -> Tuple[List[int], List[float]]:
        xs, ys = [], []
        for r in ranks:
            t = times.get((series, r))
            if t is not None:
                xs.append(cores_per_node(series, r))
                ys.append(t)
        return xs, ys

    x1, y1 = series_y("1node", ranks_1)
    x2, y2 = series_y("2node", ranks_2)

    t1_baseline = times.get(("1node", 1))
    t2_baseline = times.get(("2node", 2))

    fig, ax = plt.subplots(figsize=(8.0, 5.0))

    if x1 and y1:
        ax.plot(x1, y1, "o-", color="#4C72B0", linewidth=2.0, markersize=7, label="1 node (measured)")
    if x2 and y2:
        ax.plot(x2, y2, "s-", color="#DD8452", linewidth=2.0, markersize=7, label="2 nodes (measured)")

    # Ideal vs cores per node c (same x for both series)
    c_fine = np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=float)

    if t1_baseline is not None:
        y_id1 = t1_baseline / c_fine
        ax.plot(c_fine, y_id1, "--", color="#4C72B0", linewidth=1.4, alpha=0.75, label="1 node ideal (T(1)/c)")
    if t2_baseline is not None:
        y_id2 = t2_baseline / c_fine
        ax.plot(c_fine, y_id2, "--", color="#DD8452", linewidth=1.4, alpha=0.75, label="2 nodes ideal (T(2)/c)")

    try:
        ax.set_xscale("log", base=2)
    except TypeError:
        ax.set_xscale("log", basex=2)
    ax.set_yscale("log")

    from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

    ax.xaxis.set_major_locator(LogLocator(base=2.0))
    ax.yaxis.set_major_locator(LogLocator(base=10.0))

    def _fmt_x_cores(v, _p):
        if v <= 0:
            return ""
        iv = int(round(v))
        if abs(v - iv) < 1e-5 * max(v, 1.0):
            return str(iv)
        return "%.3g" % v

    def _fmt_y_time(v, _p):
        if v <= 0:
            return ""
        r = round(v)
        if abs(v - r) < 1e-6 * max(abs(v), 1.0):
            return str(int(r))
        if v >= 10:
            return "%d" % int(round(v))
        return "%.3g" % v

    ax.xaxis.set_major_formatter(FuncFormatter(_fmt_x_cores))
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.yaxis.set_major_formatter(FuncFormatter(_fmt_y_time))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_xlabel("# of cores used per node (1 MPI rank : 1 core)")
    ax.set_ylabel("time (s)")
    ax.set_title("Geom recommender medium n=1e9, w=1 — MPI scaling")
    ax.grid(True, which="both", linestyle=":", alpha=0.65)
    ax.legend(loc="upper right", fontsize=9)

    ymin = 1e300
    for ys in (y1, y2):
        if ys:
            ymin = min(ymin, min(ys))
    if t1_baseline:
        ymin = min(ymin, (t1_baseline / 128.0) * 0.5)
    if t2_baseline:
        ymin = min(ymin, (t2_baseline / 128.0) * 0.5)
    if ymin >= 1e200:
        ymin = 1e-3
    ax.set_ylim(bottom=max(ymin * 0.35, 1e-3), top=None)

    fig.tight_layout()
    fig.savefig(out_png, dpi=160)
    fig.savefig(out_pdf)
    print("Wrote %s" % out_png)
    print("Wrote %s" % out_pdf)


if __name__ == "__main__":
    main()
