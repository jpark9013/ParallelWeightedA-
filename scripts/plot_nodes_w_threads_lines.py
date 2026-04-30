#!/usr/bin/env python3
"""
Make per-(nodes,w,graph) log-scale line charts from sweep TSV.

Output: results/sweep_w_threads/charts/<graph>/nodes{N}_w{W}.jpg (JPG only; no persistent SVGs)
"""
import argparse
import csv
import math
import os
import subprocess
from collections import defaultdict


PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def color_for(key: str) -> str:
    h = 0
    for ch in key:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return PALETTE[h % len(PALETTE)]


def logy(v: float, ymin: float, ymax: float) -> float:
    v = max(v, ymin)
    return (math.log10(v) - math.log10(ymin)) / (math.log10(ymax) - math.log10(ymin))


def write_svg(path: str, title: str, xlabels, yvals, color: str):
    W, H = 1000, 520
    ml, mr, mt, mb = 90, 30, 70, 110
    pw, ph = W - ml - mr, H - mt - mb

    # log scale: can't include 0, so clamp to 1e-3 and annotate.
    vals = [v for v in yvals if v is not None]
    ymin = 1e-3
    ymax = max(vals + [ymin]) * 1.2
    if ymax <= ymin:
        ymax = ymin * 10

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(
        f'<text x="{W/2}" y="34" text-anchor="middle" font-size="18" font-weight="600">{title}</text>'
    )
    out.append(f'<text x="{W/2}" y="54" text-anchor="middle" fill="#555">y = time_s (seconds, log10)</text>')

    # axes
    out.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#333"/>')
    out.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#333"/>')

    # y ticks at powers of 10 (…0.1, 1, 10, 100… seconds)
    lo = int(math.floor(math.log10(ymin)))
    hi = int(math.ceil(math.log10(ymax)))
    for e in range(lo, hi + 1):
        v = 10 ** e
        if v < ymin or v > ymax:
            continue
        frac = (math.log10(v) - math.log10(ymin)) / (math.log10(ymax) - math.log10(ymin))
        y = mt + ph - frac * ph
        out.append(f'<line x1=\"{ml}\" y1=\"{y:.2f}\" x2=\"{ml+pw}\" y2=\"{y:.2f}\" stroke=\"#eee\"/>')
        out.append(f'<text x=\"{ml-8}\" y=\"{y+4:.2f}\" text-anchor=\"end\" fill=\"#555\">{v:g}</text>')

    # x positions (even)
    n = len(xlabels)
    xs = [ml + (i + 0.5) * (pw / n) for i in range(n)]
    for i, lab in enumerate(xlabels):
        x = xs[i]
        out.append(f'<line x1="{x:.2f}" y1="{mt+ph}" x2="{x:.2f}" y2="{mt+ph+6}" stroke="#333"/>')
        out.append(f'<text x="{x:.2f}" y="{mt+ph+28}" text-anchor="middle">{lab}</text>')

    # line path
    pts = []
    for i, v in enumerate(yvals):
        if v is None:
            pts.append(None)
            continue
        frac = logy(v, ymin, ymax)
        y = mt + ph - frac * ph
        pts.append((xs[i], y, v))

    # draw segments (skip gaps)
    seg = []
    for p in pts:
        if p is None:
            if len(seg) >= 2:
                pairs = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in seg)
                out.append(
                    f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="{pairs}"/>'
                )
            seg = []
            continue
        seg.append(p)
    if len(seg) >= 2:
        pairs = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in seg)
        out.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="{pairs}"/>'
        )

    for p in pts:
        if p is None:
            continue
        x, y, v = p
        out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{color}" stroke="#fff" stroke-width="1.5"/>')

    out.append("</svg>")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(out))


def try_magick(svg_path: str, jpg_path: str):
    for exe in ("magick", "convert"):
        if subprocess.call(["bash", "-lc", f"command -v {exe} >/dev/null 2>&1"]) == 0:
            subprocess.check_call(
                ["bash", "-lc", f'{exe} -density 144 "{svg_path}" -quality 92 -background white -flatten "{jpg_path}"']
            )
            return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", default="results/sweep_w_threads/sweep.tsv", nargs="?")
    ap.add_argument("--outdir", default="results/sweep_w_threads/charts")
    args = ap.parse_args()

    rows = []
    with open(args.tsv, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            rows.append(row)

    # map (nodes,w,graph) -> {threads: time}
    by = defaultdict(dict)
    for row in rows:
        nodes = int(row["nodes"])
        w = int(row["w"])
        graph = row["graph"]
        tpn = int(row["threads_per_node"])
        t = row["time_s"]
        time = None
        if t and t != "NA":
            try:
                time = float(t)
            except ValueError:
                time = None
        by[(nodes, w, graph)][tpn] = time

    threads = [1, 2, 32, 128]
    for (nodes, w, graph), mp in by.items():
        yvals = [mp.get(t) for t in threads]
        title = f"{graph} · nodes={nodes} · w={w}"
        color = color_for(f"{graph}:{nodes}:{w}")
        os.makedirs(os.path.join(args.outdir, graph), exist_ok=True)
        tmp_svg = os.path.join(args.outdir, graph, f".tmp_nodes{nodes}_w{w}.svg")
        jpg = os.path.join(args.outdir, graph, f"nodes{nodes}_w{w}.jpg")
        write_svg(tmp_svg, title, [str(t) for t in threads], yvals, color)
        try:
            try_magick(tmp_svg, jpg)
        finally:
            try:
                os.remove(tmp_svg)
            except OSError:
                pass


if __name__ == "__main__":
    main()

