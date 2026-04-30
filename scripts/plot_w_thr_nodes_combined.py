#!/usr/bin/env python3
"""
MPI node scaling charts from TSV: measured time on log10 y (legacy chart), optional ideal T1/N.

Poster-oriented outputs (default):
  - Faceted time: two stacked panels (w=1 and w=5), linear y from 0 s per panel;
    threads encoded by consistent hues (threads=1 vs threads=8).
  - Efficiency: η = T₁/(N·T_N) vs nodes with η = 1 reference line (four series).
  - Caption file for caveats (not drawn on figures).

Legacy: single chart with four (w×threads) series and eight lines (--legacy-all-lines).
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
from plot_chart_common import (
    ideal_scaled_times,
    linear_range_for_linear_plot,
    linear_range_for_log_plot,
    log10_tick_values,
    nice_linear_ticks_from_zero,
    parallel_efficiency_points,
    ypix_linear,
    ypix_log10,
)

# Original four-series colours (legacy chart)
SERIES_COLOR = {
    (1, 1): "#332288",
    (1, 8): "#44AA99",
    (5, 1): "#CC6677",
    (5, 8): "#DD8452",
}

SERIES_STROKE = {
    (5, 1): "#882222",
}

# Poster faceted panels: same hues for threads=1 and threads=8 in both w panels
THREAD_COLOR_POSTER = {
    1: "#332288",
    8: "#44AA99",
}
THREAD_STROKE_POSTER = {
    1: "#222222",
    8: "#226666",
}


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


def linear_tick_values(lo, hi, n=6):
    lo, hi = float(lo), float(hi)
    if hi <= lo:
        return [lo]
    step = (hi - lo) / float(max(n - 1, 1))
    return [lo + i * step for i in range(n)]


def write_svg(
    path,
    title,
    subtitle,
    xlabs,
    series_map,
    node_counts,
    footnote=None,
    x_axis_label=None,
):
    """
    series_map: ordered list of ((w, threads), [y0, y1] or None gaps)
    node_counts: e.g. [1, 2] — used for ideal scaling T1/N
    """
    W, H = 1100, 610
    ml, mr, mt, mb = 108, 40, 82, 188
    pw, ph = W - ml - mr, H - mt - mb

    vals = []
    for _, ys in series_map:
        for v in ys:
            if v is not None and v > 0:
                vals.append(v)
        t_ref = ys[0] if ys else None
        if t_ref is not None and t_ref > 0:
            for iv in ideal_scaled_times(t_ref, node_counts):
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
        '<text x="%.1f" y="56" text-anchor="middle" fill="#444" font-size="13">%s</text>'
        % (W / 2, subtitle)
    )

    for tv in log10_tick_values(lo_lin, hi_lin):
        y = ypix(tv)
        out.append(
            '<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#e8e8e8"/>'
            % (ml, y, ml + pw, y)
        )
        if tv >= 1.0 or tv <= 0:
            tlab = "%g" % tv
        else:
            tlab = "%.4g" % tv
        out.append('<text x="%d" y="%.2f" text-anchor="end" fill="#555">%s</text>' % (ml - 8, y + 4, tlab))

    out.append(
        '<text x="24" y="%.0f" transform="rotate(-90 24 %.0f)" text-anchor="middle" fill="#222">time_s (program, log10 scale)</text>'
        % (mt + ph / 2, mt + ph / 2)
    )
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt, ml, mt + ph))
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt + ph, ml + pw, mt + ph)
    )

    for i, lab in enumerate(xlabs):
        x = xs[i]
        out.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#222"/>' % (x, mt + ph, x, mt + ph + 5))
        out.append('<text x="%.2f" y="%d" text-anchor="middle" font-weight="500">%s</text>' % (x, mt + ph + 24, lab))

    if x_axis_label:
        out.append(
            '<text x="%.1f" y="%d" text-anchor="middle" fill="#222" font-size="13" font-weight="600">%s</text>'
            % (ml + pw / 2, mt + ph + 44, x_axis_label)
        )

    order = [(1, 1), (1, 8), (5, 1), (5, 8)]

    def polyline_ideal(key, yseries, color):
        t_ref = yseries[0] if yseries else None
        if t_ref is None or t_ref <= 0:
            return
        ideal = ideal_scaled_times(t_ref, node_counts)
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
            'stroke-dasharray="8 5" stroke-linecap="round" stroke-linejoin="round" points="%s"/>'
            % (color, pairs)
        )

    def polyline(key, yseries, color):
        pts = []
        for i, v in enumerate(yseries):
            if v is None:
                continue
            pts.append((xs[i], ypix(v)))
        if len(pts) < 2:
            if len(pts) == 1:
                x, y = pts[0]
                sw = SERIES_STROKE.get(key, "#fff")
                out.append(
                    '<circle cx="%.2f" cy="%.2f" r="6" fill="%s" stroke="%s" stroke-width="1.5"/>'
                    % (x, y, color, sw)
                )
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" '
            'stroke-linejoin="round" points="%s"/>'
            % (color, pairs)
        )
        for x, y in pts:
            sw = SERIES_STROKE.get(key, "#fff")
            out.append(
                '<circle cx="%.2f" cy="%.2f" r="5" fill="%s" stroke="%s" stroke-width="1.5"/>'
                % (x, y, color, sw)
            )

    for key in order:
        ys = dict(series_map).get(key)
        if ys is None:
            continue
        polyline_ideal(key, ys, SERIES_COLOR[key])
    for key in order:
        ys = dict(series_map).get(key)
        if ys is None:
            continue
        polyline(key, ys, SERIES_COLOR[key])

    leg_y = H - 138 if x_axis_label else H - 178
    leg_x0 = ml
    col_w = 260
    row_h = 26
    labels = {
        (1, 1): "w=1, threads=1",
        (1, 8): "w=1, threads=8",
        (5, 1): "w=5, threads=1",
        (5, 8): "w=5, threads=8",
    }
    for i, key in enumerate(order):
        col = i % 2
        row = i // 2
        lx = leg_x0 + col * col_w
        ly = leg_y + row * row_h
        c = SERIES_COLOR[key]
        sw = SERIES_STROKE.get(key, "#222")
        out.append(
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="4" stroke-linecap="round"/>'
            % (lx, ly + 8, lx + 40, ly + 8, c)
        )
        out.append(
            '<circle cx="%d" cy="%d" r="5" fill="%s" stroke="%s" stroke-width="1.2"/>'
            % (lx + 20, ly + 8, c, sw)
        )
        out.append(
            '<text x="%d" y="%d" dominant-baseline="middle">%s</text>'
            % (lx + 52, ly + 9, labels[key])
        )

    leg_note_y = leg_y + 56
    out.append(
        '<text x="%d" y="%d" fill="#444" font-size="11.5">Dashed = ideal scaling: time at nodes=1 divided by number of nodes (same colour).</text>'
        % (ml, leg_note_y)
    )

    if footnote:
        out.append(
            '<text x="%.1f" y="%d" text-anchor="middle" fill="#7f1d1d" font-size="11.5">%s</text>'
            % (W / 2, H - 22, footnote)
        )

    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))


def write_svg_time_faceted(
    path,
    title,
    subtitle,
    xlabs,
    series_map,
    node_counts,
    x_axis_label=None,
):
    """
    Two stacked panels (w=1 and w=5), independent linear y axes from 0 s; threads only in legend (shared hues).
    """
    W = 1100
    ml, mr = 108, 40
    pw = W - ml - mr
    sm = dict(series_map)

    mt_p1 = 88
    ph = 218
    gap = 38
    mt_p2 = mt_p1 + ph + gap

    leg_h = 130
    H = mt_p2 + ph + leg_h

    n = len(xlabs)
    xs = [ml + (i + 0.5) * (pw / max(n, 1)) for i in range(n)]

    def panel_axis_zero_and_ticks(keys):
        """y from 0; ymax and ticks from nice_linear_ticks_from_zero(max over measured + ideal)."""
        vals = []
        for key in keys:
            ys = sm.get(key)
            if not ys:
                continue
            for v in ys:
                if v is not None and v > 0:
                    vals.append(v)
            t_ref = ys[0] if ys else None
            if t_ref is not None and t_ref > 0:
                for iv in ideal_scaled_times(t_ref, node_counts):
                    if iv is not None and iv > 0:
                        vals.append(iv)
        if not vals:
            ticks, ymax = nice_linear_ticks_from_zero(1.0)
            return 0.0, ymax, ticks
        mx = max(vals)
        ticks, ymax = nice_linear_ticks_from_zero(mx)
        return 0.0, ymax, ticks

    keys_w1 = [(1, 1), (1, 8)]
    keys_w5 = [(5, 1), (5, 8)]
    ymin1, ymax1, ticks1 = panel_axis_zero_and_ticks(keys_w1)
    ymin2, ymax2, ticks2 = panel_axis_zero_and_ticks(keys_w5)

    def ypix1(v):
        return ypix_linear(v, ymin1, ymax1, mt_p1, ph)

    def ypix2(v):
        return ypix_linear(v, ymin2, ymax2, mt_p2, ph)

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (W, H))
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(
        '<text x="%.1f" y="30" text-anchor="middle" font-size="18" font-weight="600">%s</text>'
        % (W / 2, title)
    )
    out.append(
        '<text x="%.1f" y="52" text-anchor="middle" fill="#444" font-size="12.5">%s</text>'
        % (W / 2, subtitle)
    )

    out.append(
        '<text x="%.1f" y="72" text-anchor="middle" font-size="13" font-weight="600" fill="#333">w = 1</text>'
        % (W / 2,)
    )
    out.append(
        '<text x="%.1f" y="%d" text-anchor="middle" font-size="13" font-weight="600" fill="#333">w = 5</text>'
        % (W / 2, mt_p2 - 14)
    )

    cy_axis = (mt_p1 + ph / 2.0 + mt_p2 + ph / 2.0) / 2.0
    out.append(
        '<text x="22" y="%.0f" transform="rotate(-90 22 %.0f)" text-anchor="middle" fill="#222" font-size="12">time (s), linear scale (from 0)</text>'
        % (cy_axis, cy_axis)
    )

    def draw_panel(mt, ypix_fn, ymin_lin, ymax_lin, tick_values):
        out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt, ml, mt + ph))
        out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt + ph, ml + pw, mt + ph))
        for tv in tick_values:
            y = ypix_fn(tv)
            out.append(
                '<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#ececec"/>'
                % (ml, y, ml + pw, y)
            )
            if ymax_lin <= 0.2:
                tlab = "%.4g" % tv
            elif ymax_lin <= 2.0:
                tlab = "%.3g" % tv
            else:
                tlab = "%g" % tv
            out.append(
                '<text x="%d" y="%.2f" text-anchor="end" fill="#555" font-size="11">%s</text>'
                % (ml - 6, y + 3, tlab)
            )
        for x in xs:
            out.append(
                '<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#f0f0f0"/>'
                % (x, mt, x, mt + ph)
            )

    draw_panel(mt_p1, ypix1, ymin1, ymax1, ticks1)
    draw_panel(mt_p2, ypix2, ymin2, ymax2, ticks2)

    def polyline_ideal_panel(ypix_fn, yseries, color):
        t_ref = yseries[0] if yseries else None
        if t_ref is None or t_ref <= 0:
            return
        ideal = ideal_scaled_times(t_ref, node_counts)
        pts = []
        for i, v in enumerate(ideal):
            if v is None:
                continue
            pts.append((xs[i], ypix_fn(v)))
        if len(pts) < 2:
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="2.5" stroke-opacity="0.55" '
            'stroke-dasharray="8 5" stroke-linecap="round" stroke-linejoin="round" points="%s"/>'
            % (color, pairs)
        )

    def polyline_panel(ypix_fn, key, yseries, color):
        pts = []
        for i, v in enumerate(yseries):
            if v is None:
                continue
            pts.append((xs[i], ypix_fn(v)))
        thr = key[1]
        sw = THREAD_STROKE_POSTER.get(thr, "#222")
        if len(pts) < 2:
            if len(pts) == 1:
                x, y = pts[0]
                out.append(
                    '<circle cx="%.2f" cy="%.2f" r="6" fill="%s" stroke="%s" stroke-width="1.5"/>'
                    % (x, y, color, sw)
                )
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" '
            'stroke-linejoin="round" points="%s"/>'
            % (color, pairs)
        )
        for x, y in pts:
            out.append(
                '<circle cx="%.2f" cy="%.2f" r="5" fill="%s" stroke="%s" stroke-width="1.5"/>'
                % (x, y, color, sw)
            )

    for key in keys_w1:
        ys = sm.get(key)
        if ys is None:
            continue
        c = THREAD_COLOR_POSTER[key[1]]
        polyline_ideal_panel(ypix1, ys, c)
    for key in keys_w5:
        ys = sm.get(key)
        if ys is None:
            continue
        c = THREAD_COLOR_POSTER[key[1]]
        polyline_ideal_panel(ypix2, ys, c)

    for key in keys_w1:
        ys = sm.get(key)
        if ys is None:
            continue
        polyline_panel(ypix1, key, ys, THREAD_COLOR_POSTER[key[1]])
    for key in keys_w5:
        ys = sm.get(key)
        if ys is None:
            continue
        polyline_panel(ypix2, key, ys, THREAD_COLOR_POSTER[key[1]])

    x_tick_y = mt_p2 + ph
    for i, lab in enumerate(xlabs):
        x = xs[i]
        out.append(
            '<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#222"/>'
            % (x, x_tick_y, x, x_tick_y + 5)
        )
        out.append(
            '<text x="%.2f" y="%d" text-anchor="middle" font-weight="500">%s</text>'
            % (x, x_tick_y + 22, lab)
        )

    if x_axis_label:
        out.append(
            '<text x="%.1f" y="%d" text-anchor="middle" fill="#222" font-size="13" font-weight="600">%s</text>'
            % (ml + pw / 2, x_tick_y + 46, x_axis_label)
        )

    leg_y = x_tick_y + (74 if x_axis_label else 54)
    leg_x0 = ml
    col_w = 280
    row_h = 26
    thread_order = [1, 8]
    thr_lab = {1: "threads = 1", 8: "threads = 8"}
    for i, thr in enumerate(thread_order):
        lx = leg_x0 + (i % 2) * col_w
        ly = leg_y + (i // 2) * row_h
        c = THREAD_COLOR_POSTER[thr]
        sw = THREAD_STROKE_POSTER.get(thr, "#222")
        out.append(
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="4" stroke-linecap="round"/>'
            % (lx, ly + 8, lx + 40, ly + 8, c)
        )
        out.append(
            '<circle cx="%d" cy="%d" r="5" fill="%s" stroke="%s" stroke-width="1.2"/>'
            % (lx + 20, ly + 8, c, sw)
        )
        out.append(
            '<text x="%d" y="%d" dominant-baseline="middle">%s (same colours in both panels)</text>'
            % (lx + 52, ly + 9, thr_lab[thr])
        )

    leg_note_y = leg_y + 38
    out.append(
        '<text x="%d" y="%d" fill="#444" font-size="11.5">Solid = measured · dashed = ideal T1/N per series (MPI ranks = nodes, 1 rank/node).</text>'
        % (ml, leg_note_y)
    )

    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))


def write_svg_efficiency(
    path,
    title,
    subtitle,
    xlabs,
    series_map,
    node_counts,
    x_axis_label=None,
):
    """η = T₁/(N·T_N) vs nodes; horizontal reference η = 1; four (w×threads) series."""
    W, H = 1100, 640
    ml, mr, mt, mb = 108, 40, 78, 168
    pw, ph = W - ml - mr, H - mt - mb
    sm = dict(series_map)
    order = [(1, 1), (1, 8), (5, 1), (5, 8)]

    vals = [1.0]
    eta_maps = {}
    for key in order:
        ys = sm.get(key)
        if not ys:
            eta_maps[key] = None
            continue
        etas = parallel_efficiency_points(ys, node_counts)
        eta_maps[key] = etas
        for e in etas:
            if e is not None:
                vals.append(e)

    lo, hi = linear_range_for_linear_plot(vals, bracket_one=True)
    ymin, ymax = lo, hi

    n = len(xlabs)
    xs = [ml + (i + 0.5) * (pw / max(n, 1)) for i in range(n)]

    def ypix(v):
        return ypix_linear(v, ymin, ymax, mt, ph)

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">' % (W, H))
    out.append('<style>text{font-family:system-ui,Segoe UI,sans-serif;font-size:12px}</style>')
    out.append(
        '<text x="%.1f" y="32" text-anchor="middle" font-size="18" font-weight="600">%s</text>'
        % (W / 2, title)
    )
    out.append(
        '<text x="%.1f" y="54" text-anchor="middle" fill="#444" font-size="12.5">%s</text>'
        % (W / 2, subtitle)
    )

    y1 = ypix(1.0)
    if mt <= y1 <= mt + ph:
        out.append(
            '<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#888888" stroke-width="1.5" '
            'stroke-dasharray="7 5" opacity="0.95"/>' % (ml, y1, ml + pw, y1)
        )
        out.append(
            '<text x="%d" y="%.2f" fill="#666" font-size="11">η = 1 (ideal)</text>'
            % (ml + pw - 2, y1 - 6)
        )

    for tv in linear_tick_values(ymin, ymax, 6):
        y = ypix(tv)
        out.append(
            '<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#ececec"/>'
            % (ml, y, ml + pw, y)
        )
        out.append(
            '<text x="%d" y="%.2f" text-anchor="end" fill="#555" font-size="11">%.4g</text>'
            % (ml - 6, y + 3, tv)
        )

    out.append(
        '<text x="26" y="%.0f" transform="rotate(-90 26 %.0f)" text-anchor="middle" fill="#222" font-size="12">parallel efficiency η = T₁ / (N · T_N)</text>'
        % (mt + ph / 2, mt + ph / 2)
    )
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt, ml, mt + ph))
    out.append(
        '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#222"/>' % (ml, mt + ph, ml + pw, mt + ph)
    )

    for x in xs:
        out.append(
            '<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#f2f2f2"/>'
            % (x, mt, x, mt + ph)
        )

    labels = {
        (1, 1): "w=1, threads=1",
        (1, 8): "w=1, threads=8",
        (5, 1): "w=5, threads=1",
        (5, 8): "w=5, threads=8",
    }

    def polyline_eta(key, etas, color):
        if not etas:
            return
        pts = []
        for i, v in enumerate(etas):
            if v is None:
                continue
            pts.append((xs[i], ypix(v)))
        sw = SERIES_STROKE.get(key, "#fff")
        if len(pts) < 2:
            if len(pts) == 1:
                x, y = pts[0]
                out.append(
                    '<circle cx="%.2f" cy="%.2f" r="6" fill="%s" stroke="%s" stroke-width="1.5"/>'
                    % (x, y, color, sw)
                )
            return
        pairs = " ".join("%.2f,%.2f" % (x, y) for x, y in pts)
        out.append(
            '<polyline fill="none" stroke="%s" stroke-width="3" stroke-linecap="round" '
            'stroke-linejoin="round" points="%s"/>'
            % (color, pairs)
        )
        for x, y in pts:
            out.append(
                '<circle cx="%.2f" cy="%.2f" r="5" fill="%s" stroke="%s" stroke-width="1.5"/>'
                % (x, y, color, sw)
            )

    for key in order:
        etas = eta_maps.get(key)
        if etas is None:
            continue
        polyline_eta(key, etas, SERIES_COLOR[key])

    for i, lab in enumerate(xlabs):
        x = xs[i]
        out.append(
            '<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#222"/>'
            % (x, mt + ph, x, mt + ph + 5)
        )
        out.append(
            '<text x="%.2f" y="%d" text-anchor="middle" font-weight="500">%s</text>'
            % (x, mt + ph + 22, lab)
        )

    if x_axis_label:
        out.append(
            '<text x="%.1f" y="%d" text-anchor="middle" fill="#222" font-size="13" font-weight="600">%s</text>'
            % (ml + pw / 2, mt + ph + 46, x_axis_label)
        )

    leg_y = H - 118 if x_axis_label else H - 98
    leg_x0 = ml
    col_w = 260
    row_h = 26
    for i, key in enumerate(order):
        col = i % 2
        row = i // 2
        lx = leg_x0 + col * col_w
        ly = leg_y + row * row_h
        c = SERIES_COLOR[key]
        sw = SERIES_STROKE.get(key, "#222")
        out.append(
            '<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="4" stroke-linecap="round"/>'
            % (lx, ly + 8, lx + 40, ly + 8, c)
        )
        out.append(
            '<circle cx="%d" cy="%d" r="5" fill="%s" stroke="%s" stroke-width="1.2"/>'
            % (lx + 20, ly + 8, c, sw)
        )
        out.append(
            '<text x="%d" y="%d" dominant-baseline="middle">%s</text>'
            % (lx + 52, ly + 9, labels[key])
        )

    out.append("</svg>")
    with open(path, "w") as f:
        f.write("\n".join(out))


def write_poster_caption(path, graph_key, graph_title, node_list):
    """Poster-facing notes (formerly footnotes on the chart)."""
    lines = []
    lines.append("Poster caption — copy beside or below figures")
    lines.append("")
    lines.append("Dataset: %s" % graph_title)
    lines.append("MPI ranks = nodes (%s); efficiency uses wall time at nodes=1 as T₁ per series." % ", ".join(str(n) for n in node_list))
    lines.append("")
    if graph_key == "grid_1e9_sparse":
        lines.append(
            "w=1 vs w=5 wall times differ by ~1e4 because the search work differs: this TSV reports ~1e9 state expansions "
            "for w=1 vs ~7e4–8e4 for w=5 (weighted A* with larger w is more goal-directed, not a plotting error)."
        )
        lines.append(
            "Sparse grid — very low w=5 times (~0.02–0.04 s) are real: weighted A* expands on the order of 8e4 states "
            "(see TSV expansions column), not a crash."
        )
        lines.append(
            "w=1 — two-node runs use 2 MPI ranks on one node; this placement hit std::bad_alloc for some configs "
            "(see logs / omit from chart if missing)."
        )
        lines.append("")
        lines.append(
            "Figures: *_poster_time_faceted.jpg uses separate linear y axes from 0 s per w panel. "
            "*_poster_efficiency.jpg shows η = T₁/(N·T_N) with η = 1 as ideal strong scaling."
        )
    else:
        lines.append(
            "Figures: *_poster_time_faceted.jpg uses separate linear y axes from 0 s per w panel. "
            "*_poster_efficiency.jpg shows η = T₁/(N·T_N) with η = 1 as ideal strong scaling."
        )
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tsv")
    ap.add_argument("--outdir", default="results/combined_w_thr_nodes")
    ap.add_argument(
        "--legacy-all-lines",
        action="store_true",
        help="Also emit the single combined chart (*_all_lines.jpg) with all eight lines.",
    )
    args = ap.parse_args()

    rows = []
    with open(args.tsv, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            rows.append(row)

    graphs = sorted(set(row["graph"].strip() for row in rows if row.get("graph")))

    titles = {
        "grid_1e9_sparse": "Sparse grid n=10^9 (4-neigh, no obstacles) · goal opposite corner",
        "recommender_medium": "Geom recommender medium n=10^9 (k=64, 512 candidates)",
    }

    node_list = [1, 2]
    xlabs = [str(n) for n in node_list]
    order = [(1, 1), (1, 8), (5, 1), (5, 8)]

    os.makedirs(args.outdir, exist_ok=True)

    for graph in graphs:
        nd = {}
        for row in rows:
            if row["graph"].strip() != graph:
                continue
            try:
                nodes = int(row["nodes"])
                w = int(float(row["w"]))
                threads = int(row["threads"])
            except (ValueError, KeyError):
                continue
            t = row.get("time_s", "").strip()
            time = None
            if t and t.upper() != "NA":
                try:
                    time = float(t)
                except ValueError:
                    time = None
            nd.setdefault(nodes, {})[(w, threads)] = time

        series_map = []
        for key in order:
            ys = [nd.get(n, {}).get(key) for n in node_list]
            series_map.append((key, ys))

        title = titles.get(graph, graph.replace("_", " "))
        subtitle_faceted = (
            "MPI ranks = nodes (1 rank/node); two panels by heuristic weight w; linear y from 0 s per panel; "
            "shared thread colours · solid = measured, dashed = ideal T1/N"
        )
        subtitle_eff = (
            "Strong scaling efficiency η = T₁/(N·T_N); horizontal line η = 1 is ideal · four series = (w × OpenMP threads)"
        )

        base = os.path.join(args.outdir, graph)

        tmp_facet = os.path.join(args.outdir, ".tmp_%s_poster_faceted.svg" % graph)
        jpg_facet = "%s_poster_time_faceted.jpg" % base
        write_svg_time_faceted(
            tmp_facet,
            title,
            subtitle_faceted,
            xlabs,
            series_map,
            node_list,
            x_axis_label="Number of nodes",
        )
        if not try_magick(tmp_facet, jpg_facet):
            print("warning: ImageMagick missing; left %s" % tmp_facet, file=sys.stderr)
        else:
            try:
                os.remove(tmp_facet)
            except OSError:
                pass
            print("wrote", jpg_facet)

        tmp_eff = os.path.join(args.outdir, ".tmp_%s_poster_eff.svg" % graph)
        jpg_eff = "%s_poster_efficiency.jpg" % base
        write_svg_efficiency(
            tmp_eff,
            title,
            subtitle_eff,
            xlabs,
            series_map,
            node_list,
            x_axis_label="Number of nodes",
        )
        if not try_magick(tmp_eff, jpg_eff):
            print("warning: ImageMagick missing; left %s" % tmp_eff, file=sys.stderr)
        else:
            try:
                os.remove(tmp_eff)
            except OSError:
                pass
            print("wrote", jpg_eff)

        cap_path = "%s_poster_caption.txt" % base
        write_poster_caption(cap_path, graph, title, node_list)
        print("wrote", cap_path)

        if args.legacy_all_lines:
            subtitle = (
                "MPI ranks = nodes (1 rank/node); log10 y; solid = measured, dashed = ideal T1/N · "
                "four curves = (w × OpenMP threads)"
            )
            footnote = None
            if graph == "grid_1e9_sparse":
                footnote = (
                    "Sparse grid: w=5 times (~0.02–0.04 s) are real — weighted A* expands ~8e4 states (see TSV), "
                    "not a crash. w=1: nodes=2 uses 2 ranks on one node (2-node rank placement hits std::bad_alloc here). "
                    "Y-axis is log scale so both w values are visible."
                )

            tmp = os.path.join(args.outdir, ".tmp_%s.svg" % graph)
            jpg = os.path.join(args.outdir, "%s_all_lines.jpg" % graph)
            write_svg(
                tmp,
                title,
                subtitle,
                xlabs,
                series_map,
                node_list,
                footnote,
                x_axis_label="Number of nodes",
            )
            if not try_magick(tmp, jpg):
                print("warning: ImageMagick missing; left %s" % tmp, file=sys.stderr)
            else:
                try:
                    os.remove(tmp)
                except OSError:
                    pass
                print("wrote", jpg)


if __name__ == "__main__":
    main()
