#!/usr/bin/env python3
"""Stdlib-only: read bench.tsv, write fig_geom_mpi_scaling_lines.svg.

X: cores per node (log2). Y: time (s) (log10). Same mapping as plot_geom_mpi_scaling_lines.py.
"""
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TSV = REPO / "results/geom_mpi_scaling/bench.tsv"
OUT = REPO / "results/geom_mpi_scaling/fig_geom_mpi_scaling_lines.svg"

# Parse last rc=0 time per (series, ranks)
best = {}
for line in TSV.read_text(encoding="utf-8").splitlines()[1:]:
    p = line.split("\t")
    if len(p) < 10 or p[1] not in ("1node", "2node"):
        continue
    series, ranks_s, rc_s, ts_s = p[1], p[3], p[9], p[6]
    try:
        ranks, rc, ts = int(ranks_s), int(rc_s), float(ts_s)
    except ValueError:
        continue
    if rc != 0:
        continue
    best[(series, ranks)] = ts

r1 = [1, 2, 4, 8, 16, 32, 64, 128]
r2 = [2, 4, 8, 16, 32, 64, 128, 256]
W, H = 680, 400
Mx, My = 80, 50
# log2(cores per node), 1 .. 128
xmin_l, xmax_l = 0.0, math.log(128) / math.log(2)
ymin_l, ymax_l = math.log10(4.0), math.log10(400.0)


def tx_cores(c):
    lc = math.log(c) / math.log(2)
    return Mx + (lc - xmin_l) / (xmax_l - xmin_l) * W


def ty(t):
    return My + H - (math.log10(t) - ymin_l) / (ymax_l - ymin_l) * H


def polyline_pts(rs, series):
    pts = []
    for r in rs:
        t = best.get((series, r))
        if t is None:
            continue
        c = r if series == "1node" else r // 2
        pts.append((tx_cores(c), ty(t)))
    return pts


def path_d(pts):
    if not pts:
        return ""
    return "M " + " L ".join("%.2f %.2f" % p for p in pts)


t1 = best.get(("1node", 1))
t2 = best.get(("2node", 2))

ideal1 = [(tx_cores(c), ty(t1 / c)) for c in r1 if t1]
ideal2 = [(tx_cores(c), ty(t2 / c)) for c in r1 if t2]

p1 = polyline_pts(r1, "1node")
p2 = polyline_pts(r2, "2node")

lines = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<svg xmlns="http://www.w3.org/2000/svg" width="860" height="520" viewBox="0 0 860 520">',
    '  <rect width="100%" height="100%" fill="white"/>',
    '  <text x="430" y="28" text-anchor="middle" font-size="15" font-family="sans-serif">'
    "Geom recommender medium n=1e9, w=1 — MPI scaling (cores/node, log time)</text>",
    '  <text x="430" y="500" text-anchor="middle" font-size="11" fill="#555" font-family="sans-serif">'
    "Ideal: T(1)/c and T(2)/c (c = cores per node)</text>",
]

# Grid: vertical at powers of 2 (cores per node)
for k in range(0, 8):
    c = 2**k
    x = tx_cores(c)
    lines.append(
        '  <line x1="%.2f" y1="%.1f" x2="%.2f" y2="%.1f" stroke="#ddd" stroke-width="1"/>'
        % (x, My, x, My + H)
    )
    lines.append(
        '  <text x="%.2f" y="%.0f" text-anchor="middle" font-size="10" fill="#333" font-family="sans-serif">%d</text>'
        % (x, My + H + 22, c)
    )

# Horizontal grid: decade ticks only (plain labels)
for lv in (1, 10, 100):
    y = ty(float(lv))
    lines.append(
        '  <line x1="%.1f" y1="%.2f" x2="%.1f" y2="%.2f" stroke="#eee" stroke-width="1"/>'
        % (Mx, y, Mx + W, y)
    )
    lines.append(
        '  <text x="%.0f" y="%.2f" text-anchor="end" font-size="10" fill="#333" font-family="sans-serif">%g</text>'
        % (Mx - 8, y + 4, float(lv))
    )

lines.append(
    '  <text x="430" y="475" text-anchor="middle" font-size="12" font-family="sans-serif"># of cores used per node (1 rank : 1 core)</text>'
)
lines.append(
    '  <text transform="translate(22,280) rotate(-90)" text-anchor="middle" font-size="12" font-family="sans-serif">time (s)</text>'
)

if path_d(p1):
    lines.append(
        '  <path d="%s" fill="none" stroke="#4C72B0" stroke-width="2.5"/>'
        % path_d(p1)
    )
    for (x, y) in p1:
        lines.append(
            '  <circle cx="%.2f" cy="%.2f" r="5" fill="#4C72B0" stroke="#222" stroke-width="0.5"/>'
            % (x, y)
        )
if path_d(p2):
    lines.append(
        '  <path d="%s" fill="none" stroke="#DD8452" stroke-width="2.5"/>'
        % path_d(p2)
    )
    for (x, y) in p2:
        lines.append(
            '  <circle cx="%.2f" cy="%.2f" r="5" fill="#DD8452" stroke="#222" stroke-width="0.5"/>'
            % (x, y)
        )
if path_d(ideal1):
    lines.append(
        '  <path d="%s" fill="none" stroke="#4C72B0" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.75"/>'
        % path_d(ideal1)
    )
if path_d(ideal2):
    lines.append(
        '  <path d="%s" fill="none" stroke="#DD8452" stroke-width="1.5" stroke-dasharray="6,4" opacity="0.75"/>'
        % path_d(ideal2)
    )

lines += [
    '  <rect x="600" y="58" width="220" height="88" fill="white" stroke="#ccc"/>',
    '  <text x="612" y="78" font-size="11" font-family="sans-serif" fill="#4C72B0">● 1 node (measured)</text>',
    '  <text x="612" y="96" font-size="11" font-family="sans-serif" fill="#4C72B0">- - ideal T(1)/c</text>',
    '  <text x="612" y="114" font-size="11" font-family="sans-serif" fill="#DD8452">■ 2 nodes (measured)</text>',
    '  <text x="612" y="132" font-size="11" font-family="sans-serif" fill="#DD8452">- - ideal T(2)/c</text>',
    "</svg>",
]

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines), encoding="utf-8")
print("Wrote", OUT)
