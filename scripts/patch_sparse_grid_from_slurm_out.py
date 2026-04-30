#!/usr/bin/env python3
"""Parse RESULT lines from sbatch_rerun_sparse_grid_w1_node2.sh output; patch TSV; regenerate plot."""
from __future__ import print_function

import csv
import os
import re
import subprocess
import sys


def parse_results(text):
    """Return (t1, exp1, rc1), (t8, exp8, rc8) — any may stay None if missing."""
    t1 = e1 = r1 = t8 = e8 = r8 = None
    for line in text.splitlines():
        m = re.match(
            r"^RESULT threads=(\d+) cpus=\d+ rc=(\d+) time_s=(\S+) expansions=(\S+)\s*$", line
        )
        if not m:
            continue
        th, rc, ts, ex = m.group(1), m.group(2), m.group(3), m.group(4)
        if th == "1":
            t1, r1, e1 = ts, rc, ex
        elif th == "8":
            t8, r8, e8 = ts, rc, ex
    return (t1, e1, r1), (t8, e8, r8)


def main():
    if len(sys.argv) != 3:
        print("usage: patch_sparse_grid_from_slurm_out.py SLURM.out grid_geom_w_thr_nodes.tsv", file=sys.stderr)
        sys.exit(2)
    slurm_out, tsv_path = sys.argv[1], sys.argv[2]
    text = open(slurm_out, "r").read()
    (t1, e1, r1), (t8, e8, r8) = parse_results(text)
    if t1 is None and t8 is None:
        print("patch: no RESULT lines in", slurm_out, file=sys.stderr)
        sys.exit(1)

    # grid_geom_w_thr_nodes.tsv lives at repo/results/combined_w_thr_nodes/
    _tsv = os.path.abspath(tsv_path)
    repo = os.path.dirname(os.path.dirname(os.path.dirname(_tsv)))
    rows = []
    with open(tsv_path, newline="") as f:
        r = csv.DictReader(f, delimiter="\t")
        fieldnames = list(r.fieldnames)
        for row in r:
            rows.append(row)

    for row in rows:
        if row.get("graph") != "grid_1e9_sparse":
            continue
        if row.get("nodes") != "2" or row.get("w") != "1":
            continue
        if row.get("threads") == "1" and t1 is not None:
            row["time_s"] = t1
            row["expansions"] = e1 or "NA"
            row["exit_code"] = r1 or ""
        if row.get("threads") == "8" and t8 is not None:
            row["time_s"] = t8
            row["expansions"] = e8 or "NA"
            row["exit_code"] = r8 or ""

    with open(tsv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    plot = os.path.join(repo, "scripts/plot_w_thr_nodes_combined.py")
    outdir = os.path.dirname(os.path.abspath(tsv_path))
    subprocess.check_call([sys.executable, plot, tsv_path, "--outdir", outdir])
    print("patched", tsv_path, "from", slurm_out)


if __name__ == "__main__":
    main()
