#!/usr/bin/env python3
"""Multi-series line chart from TSV: graph,config,time_s (one line per config, x = graph)."""
import argparse
import csv
from collections import defaultdict


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv", help="TSV with header: graph,config,time_s,...")
    ap.add_argument("-o", "--output", default="results/lines_chart.svg")
    ap.add_argument(
        "--title",
        default="Benchmark · time_s (program) vs graph scenario",
        help="Chart title (SVG)",
    )
    args = ap.parse_args()

    times = defaultdict(dict)
    with open(args.tsv, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            g = row["graph"].strip()
            c = row["config"].strip()
            t = row["time_s"].strip()
            if t and t.upper() != "NA":
                times[g][c] = float(t)

    graphs = sorted(times.keys())

    def config_sort_key(name):
        if name == "serial":
            return (-1, 0, 0)
        if name.startswith("mpi_") and "x" in name:
            body = name[len("mpi_") :]
            try:
                a, b = body.split("x", 1)
                return (0, -int(a), -int(b))
            except ValueError:
                pass
        return (1, name)

    all_cfgs = set()
    for g in graphs:
        all_cfgs.update(times[g].keys())
    configs = sorted(all_cfgs, key=config_sort_key)

    palette = ["#2c3e50", "#3498db", "#1abc9c", "#9b59b6", "#e67e22", "#e74c3c", "#34495e", "#16a085"]
    colors = {"serial": "#2c3e50"}
    for i, c in enumerate(configs):
        if c not in colors:
            colors[c] = palette[(i + 1) % len(palette)]

    W, H = 1200, 640
    margin_l, margin_r, margin_t, margin_b = 160, 40, 80, 160
    plot_w = W - margin_l - margin_r
    plot_h = H - margin_t - margin_b

    ymax = 0.01
    for g in graphs:
        for c in configs:
            ymax = max(ymax, times[g].get(c, 0.0))
    ymax *= 1.12

    ng = len(graphs)
    step_x = plot_w / max(1, ng)

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">')
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(
        f'<text x="{W/2}" y="36" text-anchor="middle" font-size="18" font-weight="600">{args.title}</text>'
    )

    nticks = 5
    for i in range(nticks + 1):
        v = ymax * i / nticks
        y = margin_t + plot_h - (v / ymax) * plot_h
        out.append(f'<line x1="{margin_l}" y1="{y}" x2="{margin_l + plot_w}" y2="{y}" stroke="#ddd"/>')
        fmt = f"{v:.1f}" if ymax >= 50 else f"{v:.3f}"
        out.append(f'<text x="{margin_l - 8}" y="{y + 4}" text-anchor="end" fill="#555">{fmt}</text>')

    out.append(
        f'<text x="24" y="{margin_t + plot_h / 2:.0f}" transform="rotate(-90 24 {margin_t + plot_h / 2:.0f})" '
        'text-anchor="middle" fill="#333">time_s (program)</text>'
    )
    out.append(
        f'<line x1="{margin_l}" y1="{margin_t}" x2="{margin_l}" y2="{margin_t + plot_h}" stroke="#333"/>'
    )
    out.append(
        f'<line x1="{margin_l}" y1="{margin_t + plot_h}" x2="{margin_l + plot_w}" y2="{margin_t + plot_h}" stroke="#333"/>'
    )

    # x tick marks (vertical guides at each category)
    for gi in range(ng):
        cx = margin_l + (gi + 0.5) * step_x
        out.append(
            f'<line x1="{cx:.2f}" y1="{margin_t + plot_h}" x2="{cx:.2f}" y2="{margin_t + plot_h + 6}" stroke="#333"/>'
        )

    # Polylines + markers per config
    for c in configs:
        col = colors.get(c, "#888")
        pts = []
        for gi, g in enumerate(graphs):
            val = times[g].get(c)
            if val is None:
                continue
            px = margin_l + (gi + 0.5) * step_x
            py = margin_t + plot_h - (val / ymax) * plot_h
            pts.append((px, py, val))
        if len(pts) < 2:
            if len(pts) == 1:
                px, py, val = pts[0]
                out.append(
                    f'<circle cx="{px:.2f}" cy="{py:.2f}" r="5" fill="{col}" stroke="#fff" stroke-width="1"/>'
                )
            continue
        pairs = " ".join(f"{px:.2f},{py:.2f}" for px, py, _ in pts)
        out.append(
            f'<polyline fill="none" stroke="{col}" stroke-width="2.5" stroke-linecap="round" '
            f'stroke-linejoin="round" points="{pairs}"/>'
        )
        for px, py, val in pts:
            out.append(
                f'<circle cx="{px:.2f}" cy="{py:.2f}" r="4" fill="{col}" stroke="#fff" stroke-width="1.5"/>'
            )

    # x labels (graph names)
    for gi, g in enumerate(graphs):
        lx = margin_l + (gi + 0.5) * step_x
        ly = margin_t + plot_h + 28
        label = g.replace("_", " ")
        out.append(
            f'<text x="{lx:.2f}" y="{ly}" text-anchor="middle" transform="rotate(-30 {lx:.2f} {ly})">{label}</text>'
        )

    # legend (line swatch)
    lx0 = margin_l
    ly0 = H - 52
    ncol = 3
    col_w = min(380, (W - margin_l - margin_r) / ncol)
    for i, c in enumerate(configs):
        col = colors.get(c, "#888")
        lx = lx0 + (i % ncol) * col_w
        ly = ly0 + (i // ncol) * 24
        out.append(f'<line x1="{lx}" y1="{ly + 6}" x2="{lx + 28}" y2="{ly + 6}" stroke="{col}" stroke-width="3"/>')
        out.append(f'<text x="{lx + 36}" y="{ly + 11}">{c}</text>')

    out.append("</svg>")
    with open(args.output, "w") as f:
        f.write("\n".join(out))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
