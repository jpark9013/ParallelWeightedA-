# -*- coding: utf-8 -*-
"""Shared helpers: log y-axis mapping and ideal parallel scaling T_ref / N."""
from __future__ import print_function

import math

EPS = 1e-300


def linear_range_for_log_plot(values):
    """Return (lo, hi) linear bounds for positive samples; widen slightly."""
    pos = [float(v) for v in values if v is not None and v > 0]
    if not pos:
        return 1e-4, 1.0
    lo = min(pos)
    hi = max(pos)
    return max(lo / 1.22, 1e-12), hi * 1.22


def ypix_log10(v, ymin_log, ymax_log, mt, ph):
    v = max(float(v), EPS)
    lv = math.log10(v)
    den = ymax_log - ymin_log
    if den <= 0:
        return mt + ph
    return mt + ph - (lv - ymin_log) / den * ph


def ypix_linear(v, ymin, ymax, mt, ph):
    den = float(ymax) - float(ymin)
    if den <= 0:
        return mt + ph
    return mt + ph - (float(v) - float(ymin)) / den * ph


def nice_linear_ticks_from_zero(max_datum):
    """
    Coarse axis from 0: ymax >= max_datum * 1.02, round-number ticks
    (e.g. max ~200 s -> 0, 100, 200, 300; small times -> 0, 0.02, 0.04, 0.06).
    Returns (tick_values, ymax).
    """
    if max_datum <= 0:
        return [0.0, 1.0], 1.0
    hi = float(max_datum) * 1.02
    if hi >= 75:
        step = 100.0
        axis_top = math.ceil(hi / step) * step
    elif hi >= 15:
        step = 25.0
        axis_top = math.ceil(hi / step) * step
    elif hi >= 2.5:
        step = 5.0
        axis_top = math.ceil(hi / step) * step
    elif hi >= 0.15:
        step = 0.05
        axis_top = math.ceil(hi / step) * step
    elif hi >= 0.03:
        step = 0.02
        axis_top = math.ceil(hi / step) * step
        axis_top = max(axis_top, 0.06)
    else:
        step = 0.01
        axis_top = max(0.05, math.ceil(hi / step) * step)
    ticks = []
    t = 0.0
    while t <= axis_top + 1e-12:
        ticks.append(t)
        t += step
    # Keep at most ~5 grid lines (coarse, poster-friendly)
    while len(ticks) >= 6 and step < axis_top:
        step *= 2.0
        axis_top = math.ceil(hi / step) * step
        ticks = []
        t = 0.0
        while t <= axis_top + 1e-12:
            ticks.append(t)
            t += step
    return ticks, axis_top


def ideal_scaled_times(t_ref, node_counts):
    """Ideal wall-clock scaling with nodes=1 as reference: T_ideal(N) = T(nodes=1) / N."""
    if t_ref is None or t_ref <= 0:
        return [None] * len(node_counts)
    return [t_ref / float(n) for n in node_counts]


def parallel_efficiency_points(y_series, node_counts):
    """
    Strong scaling efficiency η(N) = T(1) / (N · T(N)) when node_counts[0] corresponds to T(1).
    Same indexing as node_counts and y_series; returns None where inputs missing or non-positive.
    Ideal scaling implies η(N) = 1 for all N (horizontal reference at 1).
    """
    if not y_series or not node_counts:
        return []
    t_ref = y_series[0]
    if t_ref is None or t_ref <= 0:
        return [None] * len(node_counts)
    out = []
    for i, n in enumerate(node_counts):
        t = y_series[i] if i < len(y_series) else None
        if t is None or t <= 0 or n <= 0:
            out.append(None)
        else:
            out.append(float(t_ref) / (float(n) * float(t)))
    return out


def linear_range_for_linear_plot(values, bracket_one=False):
    """Return (lo, hi) linear bounds; widen slightly. If bracket_one, force interval to include 1.0 (efficiency reference)."""
    pos = [float(v) for v in values if v is not None]
    if not pos:
        return (0.0, 1.2) if bracket_one else (0.0, 1.0)
    lo = min(pos)
    hi = max(pos)
    if bracket_one:
        lo = min(lo, 1.0)
        hi = max(hi, 1.0)
    pad = max((hi - lo) * 0.08, 0.02)
    lo = max(0.0, lo - pad)
    hi = hi + pad
    return lo, hi


def log10_tick_values(lo_lin, hi_lin):
    """Decade tick positions within [lo_lin, hi_lin]."""
    if lo_lin <= 0 or hi_lin <= 0 or hi_lin < lo_lin:
        return []
    ylo = math.log10(lo_lin)
    yhi = math.log10(hi_lin)
    loe = int(math.floor(ylo))
    hie = int(math.ceil(yhi))
    out = []
    for e in range(loe, hie + 1):
        v = 10.0 ** e
        if lo_lin <= v <= hi_lin:
            out.append(v)
    return out
