#!/usr/bin/env python3
"""
Create 4 JPG summary plots from results/sweep_w_threads/sweep.tsv:
 - independent var: nodes      (hold w=1, threads=32)
 - independent var: w          (hold nodes=2, threads=32)
 - independent var: threads    (hold nodes=2, w=1)
 - independent var: graph      (hold nodes=2, w=1, threads=32)

If graph is NOT independent, it is held constant at graph=n1e10_dense.
Plots use y = time_s on log10 scale (decade ticks: 0.1, 1, 10, ...).
Outputs JPG only (no SVG artifacts left behind).
"""
import argparse
import csv
import math
import os
import subprocess
import tempfile


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


def render_svg_to_jpg(svg_text: str, out_jpg: str) -> None:
    os.makedirs(os.path.dirname(out_jpg), exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg_text)
        tmp_svg = f.name
    try:
        # Prefer magick; fall back to convert.
        exe = None
        for cand in ("magick", "convert"):
            if subprocess.call(["bash", "-lc", f"command -v {cand} >/dev/null 2>&1"]) == 0:
                exe = cand
                break
        if exe is None:
            raise RuntimeError("ImageMagick not found (need magick/convert)")
        subprocess.check_call(
            [
                "bash",
                "-lc",
                f'{exe} -density 144 "{tmp_svg}" -quality 92 -background white -flatten "{out_jpg}"',
            ]
        )
    finally:
        try:
            os.unlink(tmp_svg)
        except OSError:
            pass


def make_plot(title: str, xlabel: str, xvals, series: dict, out_jpg: str) -> None:
    # series: name -> list[time or None], aligned with xvals
    W, H = 1100, 560
    ml, mr, mt, mb = 95, 30, 70, 140
    pw, ph = W - ml - mr, H - mt - mb

    # log scale can't include 0. Clamp to a small positive.
    ymin = 1e-3
    vmax = ymin
    for _, ys in series.items():
        for v in ys:
            if v is not None:
                vmax = max(vmax, v)
    ymax = vmax * 1.25
    if ymax <= ymin:
        ymax = ymin * 10

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(f'<text x="{W/2}" y="34" text-anchor="middle" font-size="18" font-weight="600">{title}</text>')
    out.append(f'<text x="{W/2}" y="54" text-anchor="middle" fill="#555">y = time_s (seconds, log10)</text>')

    # axes
    out.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+ph}" stroke="#333"/>')
    out.append(f'<line x1="{ml}" y1="{mt+ph}" x2="{ml+pw}" y2="{mt+ph}" stroke="#333"/>')
    out.append(
        f'<text x="24" y="{mt + ph/2:.0f}" transform="rotate(-90 24 {mt + ph/2:.0f})" '
        'text-anchor="middle" fill="#333">time_s</text>'
    )
    out.append(f'<text x="{ml + pw/2:.0f}" y="{H-20}" text-anchor="middle" fill="#333">{xlabel}</text>')

    # y ticks at powers of 10 (…0.1, 1, 10, 100… seconds)
    lo = int(math.floor(math.log10(ymin)))
    hi = int(math.ceil(math.log10(ymax)))
    for e in range(lo, hi + 1):
        v = 10 ** e
        if v < ymin or v > ymax:
            continue
        frac = (math.log10(v) - math.log10(ymin)) / (math.log10(ymax) - math.log10(ymin))
        y = mt + ph - frac * ph
        out.append(f'<line x1="{ml}" y1="{y:.2f}" x2="{ml+pw}" y2="{y:.2f}" stroke="#eee"/>')
        out.append(f'<text x="{ml-8}" y="{y+4:.2f}" text-anchor="end" fill="#555">{v:g}</text>')

    # x positions evenly spaced
    n = len(xvals)
    xs = [ml + (i + 0.5) * (pw / n) for i in range(n)]
    for i, xv in enumerate(xvals):
        x = xs[i]
        out.append(f'<line x1="{x:.2f}" y1="{mt+ph}" x2="{x:.2f}" y2="{mt+ph+6}" stroke="#333"/>')
        out.append(f'<text x="{x:.2f}" y="{mt+ph+26}" text-anchor="middle">{xv}</text>')

    # lines
    for name, ys in sorted(series.items()):
        col = color_for(name)
        pts = []
        for i, v in enumerate(ys):
            if v is None:
                pts.append(None)
                continue
            frac = logy(v, ymin, ymax)
            y = mt + ph - frac * ph
            pts.append((xs[i], y))
        # polyline segments
        seg = []
        for p in pts + [None]:
            if p is None:
                if len(seg) >= 2:
                    pairs = " ".join(f"{x:.2f},{y:.2f}" for x, y in seg)
                    out.append(
                        f'<polyline fill="none" stroke="{col}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="{pairs}"/>'
                    )
                seg = []
            else:
                seg.append(p)
        # markers
        for p in pts:
            if p is None:
                continue
            x, y = p
            out.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="{col}" stroke="#fff" stroke-width="1.5"/>')

    # legend
    lx0 = ml
    ly0 = H - 110
    ncol = 2
    col_w = (W - ml - mr) / ncol
    items = sorted(series.keys())
    for i, name in enumerate(items):
        col = color_for(name)
        lx = lx0 + (i % ncol) * col_w
        ly = ly0 + (i // ncol) * 24
        out.append(f'<line x1="{lx:.0f}" y1="{ly+6:.0f}" x2="{lx+28:.0f}" y2="{ly+6:.0f}" stroke="{col}" stroke-width="3"/>')
        out.append(f'<text x="{lx+36:.0f}" y="{ly+11:.0f}">{name}</text>')

    out.append("</svg>")
    render_svg_to_jpg("\n".join(out), out_jpg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", nargs="?", default="results/sweep_w_threads/sweep.tsv")
    ap.add_argument("--outdir", default="results/sweep_w_threads/summary")
    args = ap.parse_args()

    rows = []
    with open(args.tsv, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            rows.append(row)

    graphs = sorted({r["graph"] for r in rows})
    fixed_graph = "n1e10_dense"
    if fixed_graph not in graphs:
        # Fallback: pick any dense 1e10 graph if naming differs.
        for g in graphs:
            if "n1e10" in g and "dense" in g:
                fixed_graph = g
                break

    def get_time(nodes, w, graph, tpn):
        for r in rows:
            if (
                int(r["nodes"]) == nodes
                and int(r["w"]) == w
                and r["graph"] == graph
                and int(r["threads_per_node"]) == tpn
            ):
                t = r["time_s"]
                if t and t != "NA":
                    try:
                        return float(t)
                    except ValueError:
                        return None
                return None
        return None

    # 1) independent: nodes (hold w=1, threads=32, graph fixed)
    x_nodes = ["1", "2", "4"]
    series_nodes = {}
    series_nodes[fixed_graph] = [get_time(int(n), 1, fixed_graph, 32) for n in (1, 2, 4)]
    make_plot(
        f"Sweep summary: vary nodes (graph={fixed_graph}, w=1, threads/node=32)",
        "# nodes",
        x_nodes,
        series_nodes,
        os.path.join(args.outdir, "vary_nodes.jpg"),
    )

    # 2) independent: w (hold nodes=2, threads=32, graph fixed)
    x_w = ["1", "3", "5"]
    series_w = {}
    series_w[fixed_graph] = [get_time(2, int(w), fixed_graph, 32) for w in (1, 3, 5)]
    make_plot(
        f"Sweep summary: vary w (graph={fixed_graph}, nodes=2, threads/node=32)",
        "w",
        x_w,
        series_w,
        os.path.join(args.outdir, "vary_w.jpg"),
    )

    # 3) independent: threads (hold nodes=2, w=1, graph fixed)
    x_t = ["1", "2", "32", "128"]
    series_t = {}
    series_t[fixed_graph] = [get_time(2, 1, fixed_graph, t) for t in (1, 2, 32, 128)]
    make_plot(
        f"Sweep summary: vary threads/node (graph={fixed_graph}, nodes=2, w=1)",
        "threads per node",
        x_t,
        series_t,
        os.path.join(args.outdir, "vary_threads.jpg"),
    )

    # 4) independent: graph (hold nodes=2, w=1, threads=32)
    x_g = graphs
    series_g = {"time_s": [get_time(2, 1, g, 32) for g in graphs]}
    make_plot(
        "Sweep summary: vary graph (nodes=2, w=1, threads/node=32)",
        "graph",
        x_g,
        series_g,
        os.path.join(args.outdir, "vary_graph.jpg"),
    )


if __name__ == "__main__":
    main()

