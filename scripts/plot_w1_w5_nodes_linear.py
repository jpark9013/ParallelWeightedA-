#!/usr/bin/env python3
"""
Two-line chart: x = MPI nodes (1,2,4), y = time_s (log10). Series w=1 and w=5.
Dashed = ideal scaling T(nodes=1)/N per series.
Reads TSV: graph, nodes, w, threads, time_s, exit_code, expansions
Writes one JPG per distinct `graph` column value.
"""
from __future__ import print_function

import argparse
import csv
import math
import os
import subprocess
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from plot_chart_common import ideal_scaled_times, linear_range_for_log_plot, log10_tick_values, ypix_log10

# Distinct, colorblind-friendly pair
COLOR_W1 = "#2563eb"
COLOR_W5 = "#dc2626"


def try_magick(svg_path, jpg_path):
    for exe in ("magick", "convert"):
        if subprocess.call(["bash", "-lc", "command -v %s >/dev/null 2>&1" % exe]) == 0:
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


def write_svg(path, title, subtitle, xlabs, series_w1, series_w5, node_counts):
    W, H = 1000, 560
    ml, mr, mt, mb = 100, 36, 78, 130
    pw, ph = W - ml - mr, H - mt - mb

    vals = []
    for v in series_w1 + series_w5:
        if v is not None and v > 0:
            vals.append(v)
    for s in (series_w1, series_w5):
        t0 = s[0] if s else None
        if t0 is not None and t0 > 0:
            for iv in ideal_scaled_times(t0, node_counts):
                if iv is not None and iv > 0:
                    vals.append(iv)
    lo_lin, hi_lin = linear_range_for_log_plot(vals)
    ymin_log = math.log10(lo_lin)
    ymax_log = math.log10(hi_lin)

    def ypix(v):
        return ypix_log10(v, ymin_log, ymax_log, mt, ph)

    n = len(xlabs)
    xs = [ml + (i + 0.5) * (pw / max(n, 1)) for i in range(n)]

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (W, H))
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(
        '<text x="%.1f" y="34" text-anchor="middle" font-size="18" font-weight="600">%s</text>'
        % (W / 2, title)
    )
    out.append(
        '<text x="%.1f" y="54" text-anchor="middle" fill="#555" font-size="13">%s</text>'
        % (W / 2, subtitle)
    )

    for tv in log10_tick_values(lo_lin, hi_lin):
        y = ypix(tv)
        out.append(
            '<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#e5e7eb"/>'
            % (ml, y, ml + pw, y)
        )
        tlab = "%.4g" % tv if tv < 1.0 else "%g" % tv
        out.append(
            '<text x="%d" y="%.2f" text-anchor="end" fill="#555">%s</text>'
            % (ml - 8, y + 4, tlab)
        )

    out.append(
        '<text x="22" y="%.0f" transform="rotate(-90 22 %.0f)" text-anchor="middle" fill="#333">time_s (log10)</text>'
        % (mt + ph / 2, mt + ph / 2)
    )
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333"/>'
        % (ml, mt, ml, mt + ph)
    )
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#333"/>'
        % (ml, mt + ph, ml + pw, mt + ph)
    )

    for i, lab in enumerate(xlabs):
        x = xs[i]
        out.append(
            '<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#333"/>'
            % (x, mt + ph, x, mt + ph + 5)
        )
        out.append(
            '<text x="%.2f" y="%d" text-anchor="middle">%s</text>' % (x, mt + ph + 22, lab)
        )

    def polyline_ideal(yseries, color):
        t0 = yseries[0] if yseries else None
        if t0 is None or t0 <= 0:
            return
        ideal = ideal_scaled_times(t0, node_counts)
        pts = []
        for i, v in enumerate(ideal):
            if v is None:
                continue
            pts.append((xs[i], ypix(v)))
        if len(pts) < 2:
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="2.5" stroke-opacity="0.55" '
            'stroke-dasharray="8 5" stroke-linecap="round" points="%s"/>' % (color, pairs)
        )

    def polyline(yseries, color, label):
        pts = []
        for i, v in enumerate(yseries):
            if v is None:
                continue
            pts.append((xs[i], ypix(v)))
        if len(pts) < 2:
            if len(pts) == 1:
                x, y = pts[0]
                out.append(
                    '<circle cx="%.2f" cy="%.2f" r="5" fill="%s" stroke="#fff" stroke-width="1"/>'
                    % (x, y, color)
                )
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" '
            'stroke-linejoin="round" points="%s"/>' % (color, pairs)
        )
        for x, y in pts:
            out.append(
                '<circle cx="%.2f" cy="%.2f" r="4" fill="%s" stroke="#fff" stroke-width="1.5"/>'
                % (x, y, color)
            )

    polyline_ideal(series_w1, COLOR_W1)
    polyline_ideal(series_w5, COLOR_W5)
    polyline(series_w1, COLOR_W1, "w=1")
    polyline(series_w5, COLOR_W5, "w=5")

    # legend
    lx0, ly0 = ml, H - 98
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>'
        % (lx0, ly0 + 6, lx0 + 36, ly0 + 6, COLOR_W1)
    )
    out.append('<text x="%d" y="%d">w = 1 (exact heuristic weight)</text>' % (lx0 + 44, ly0 + 10))
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>'
        % (lx0 + 220, ly0 + 6, lx0 + 256, ly0 + 6, COLOR_W5)
    )
    out.append(
        '<text x="%d" y="%d">w = 5 (weighted A*)</text>' % (lx0 + 264, ly0 + 10)
    )
    out.append(
        '<text x="%d" y="%d" fill="#444" font-size="11">Dashed = ideal T1/N (same colour).</text>'
        % (lx0, ly0 + 28)
    )

    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", help="TSV with header graph, nodes, w, threads, time_s, ...")
    ap.add_argument(
        "--outdir",
        default="results/geom_w_compare",
        help="Directory for output JPGs",
    )
    args = ap.parse_args()

    rows = []
    with open(args.tsv, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            rows.append(row)

    # graph -> (nodes -> w -> time)
    by_graph = {}
    for row in rows:
        g = row["graph"].strip()
        try:
            nodes = int(row["nodes"])
            w = int(float(row["w"]))
        except (ValueError, KeyError):
            continue
        t = row.get("time_s", "").strip()
        time = None
        if t and t.upper() != "NA":
            try:
                time = float(t)
            except ValueError:
                time = None
        by_graph.setdefault(g, {}).setdefault(nodes, {})[w] = time

    node_list = [1, 2, 4]
    xlabs = [str(n) for n in node_list]

    titles = {
        "recommender_medium": "Recommender-style embedding graph (n=10^9, k=64, 512 candidates)",
        "social_embedding_dense": "Dense social-embedding kNN (n=10^9, k=128, 1024 candidates)",
    }

    os.makedirs(args.outdir, exist_ok=True)
    for g, nd in sorted(by_graph.items()):
        s1 = [nd.get(n, {}).get(1) for n in node_list]
        s5 = [nd.get(n, {}).get(5) for n in node_list]
        title = titles.get(g, g.replace("_", " "))
        subtitle = (
            "MPI nodes (1 rank per node), OMP_NUM_THREADS=1 · log10 y · solid = measured, dashed = ideal T1/N"
        )
        tmp = os.path.join(args.outdir, ".tmp_%s_w1w5.svg" % g)
        jpg = os.path.join(args.outdir, "%s_w1_w5_linear.jpg" % g)
        write_svg(tmp, title, subtitle, xlabs, s1, s5, node_list)
        if not try_magick(tmp, jpg):
            print("warning: ImageMagick not found; wrote %s (convert manually)" % tmp, file=sys.stderr)
        else:
            try:
                os.remove(tmp)
            except OSError:
                pass
            print("wrote", jpg)


if __name__ == "__main__":
    main()
