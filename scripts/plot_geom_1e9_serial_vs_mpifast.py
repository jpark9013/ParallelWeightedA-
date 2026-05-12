#!/usr/bin/env python3
"""Bar chart: serial vs MPI fast on geom 1e9 recommender medium (same start/goal/w)."""
import argparse
import csv
import os
import subprocess
import sys


def try_magick(svg_path: str, jpg_path: str) -> bool:
    for exe in ("magick", "convert"):
        rc = subprocess.call(["bash", "-lc", "command -v %s >/dev/null 2>&1" % exe])
        if rc == 0:
            subprocess.check_call(
                [
                    "bash",
                    "-lc",
                    '%s -density 144 "%s" -quality 92 -background white -flatten "%s"'
                    % (exe, svg_path, jpg_path),
                ]
            )
            return True
    return False


def write_svg(out_svg, labels, times, title):
    w, h = 820, 520
    pad_l, pad_r, pad_t, pad_b = 120, 40, 72, 140
    x0, x1 = pad_l, w - pad_r
    y0, y1 = h - pad_b, pad_t

    ymax = max(times) * 1.12
    ymin = 0.0

    def ymap(v: float) -> float:
        if ymax == ymin:
            return (y0 + y1) / 2
        return y0 - (v - ymin) * (y0 - y1) / (ymax - ymin)

    n = len(labels)
    bw = (x1 - x0) / max(n, 1) * 0.62
    gap = (x1 - x0) / max(n, 1)
    xs = [x0 + (i + 0.5) * gap for i in range(n)]

    colors = ["#1f77b4", "#d62728"]

    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">')
    lines.append('<rect width="100%" height="100%" fill="white"/>')
    lines.append(
        f'<text x="{w/2:.1f}" y="38" text-anchor="middle" font-family="sans-serif" font-size="18">{title}</text>'
    )
    lines.append(
        f'<text x="{w/2:.1f}" y="58" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#444">start=0 goal=999999999  w=1  k=64 candidates=512  n=1e9</text>'
    )

    # axes
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y0}" stroke="#222" stroke-width="2"/>')
    lines.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#222" stroke-width="2"/>')

    # y grid + ticks (5)
    for i in range(6):
        v = ymin + (ymax - ymin) * i / 5.0
        y = ymap(v)
        lines.append(f'<line x1="{x0}" y1="{y:.2f}" x2="{x1}" y2="{y:.2f}" stroke="#eee" stroke-width="1"/>')
        lines.append(f'<line x1="{x0-6}" y1="{y:.2f}" x2="{x0}" y2="{y:.2f}" stroke="#222" stroke-width="2"/>')
        lines.append(
            f'<text x="{x0-10}" y="{y+4:.2f}" text-anchor="end" font-family="sans-serif" font-size="12">{v:.0f}</text>'
        )

    for i, (lab, t, c) in enumerate(zip(labels, times, colors)):
        cx = xs[i]
        xbar = cx - bw / 2
        ybar = ymap(t)
        lines.append(
            f'<rect x="{xbar:.2f}" y="{ybar:.2f}" width="{bw:.2f}" height="{y0 - ybar:.2f}" fill="{c}" opacity="0.88" stroke="white" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{cx:.2f}" y="{ybar - 8:.2f}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="#111">{t:.1f}s</text>'
        )
        lines.append(
            f'<text x="{cx:.2f}" y="{y0 + 22:.2f}" text-anchor="middle" font-family="sans-serif" font-size="13">{lab}</text>'
        )

    lines.append(
        f'<text x="16" y="{(y0+y1)/2:.1f}" text-anchor="middle" font-family="sans-serif" font-size="15" transform="rotate(-90 16 {(y0+y1)/2:.1f})">time (s)</text>'
    )
    lines.append("</svg>")

    os.makedirs(os.path.dirname(out_svg) or ".", exist_ok=True)
    with open(out_svg, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def read_rows(tsv_path):
    rows = []
    with open(tsv_path, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            rows.append(row)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Plot serial vs MPI-fast bars from TSV.")
    ap.add_argument("tsv", help="TSV with columns instrument, time_s")
    ap.add_argument("--outdir", default="results/geom_1e9_serial_vs_mpifast", help="output directory")
    args = ap.parse_args()

    rows = read_rows(args.tsv)
    labels = [r["instrument"] for r in rows]
    times = [float(r["time_s"]) for r in rows]

    os.makedirs(args.outdir, exist_ok=True)
    svg = os.path.join(args.outdir, "geom_1e9_recommender_medium_serial_vs_mpi_fast.svg")
    jpg = os.path.join(args.outdir, "geom_1e9_recommender_medium_serial_vs_mpi_fast.jpg")
    title = "Geom 1e9 recommender medium: serial vs astar_mpi_fast (same CPU node type)"
    write_svg(svg, labels, times, title)
    if try_magick(svg, jpg):
        print("Wrote", svg, "and", jpg)
    else:
        print("Wrote", svg, "(ImageMagick not found; skipped JPG)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
