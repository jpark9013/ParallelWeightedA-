#!/bin/bash
# Serial verification: same start/goal, w=1 vs w=5, grid sparse + geom recommender medium.
# Captures cost, time_s, expansions for correctness and timing check.
#
#   salloc --nodes=1 --ntasks=1 --cpus-per-task=8 --time=01:30:00 --qos=interactive \
#     --constraint=cpu --account=m4341 bash scripts/verify_w1_w5_cost_time.sh
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
BIN="./algo/serial/astar_serial"
OUT="${OUT:-results/verify_w1_w5_serial.tsv}"
mkdir -p "$(dirname "$OUT")"

echo -e "graph\tw\ttime_s\texpansions\tcost\tline" >"$OUT"

run_one () {
  local mode=$1 spec=$2 w=$3 label=$4
  echo "=== $label w=$w ===" >&2
  set +e
  line="$("$BIN" --mode "$mode" --spec "$spec" --start 0 --goal 999999999 -w "$w" 2>&1 | grep -E '^cost=' | tail -1)"
  rc=$?
  set -e
  if [[ "$rc" != "0" ]] || [[ -z "$line" ]]; then
    printf '%s\t%s\tNA\tNA\tNA\t%s\n' "$label" "$w" "${line:-run_failed rc=$rc}"
    printf '%s\t%s\tNA\tNA\tNA\t%s\n' "$label" "$w" "${line:-run_failed rc=$rc}" >>"$OUT"
    return 0
  fi
  # cost=%.12g ... time_s=%f patterns vary slightly by mode
  cost="$(sed -n 's/.*cost=\([^ ]*\).*/\1/p' <<<"$line" | head -1)"
  ts="$(sed -n 's/.*time_s=\([^ ]*\).*/\1/p' <<<"$line" | head -1)"
  exp="$(sed -n 's/.*expansions=\([^ ]*\).*/\1/p' <<<"$line" | head -1)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$w" "$ts" "$exp" "$cost" "$line"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$label" "$w" "$ts" "$exp" "$cost" "$line" >>"$OUT"
}

run_one grid bench_specs/grid_1e9_sparse.spec 1 grid_1e9_sparse
run_one grid bench_specs/grid_1e9_sparse.spec 5 grid_1e9_sparse
run_one geom bench_specs/geom_1e9_recommender_medium.spec 1 recommender_medium
run_one geom bench_specs/geom_1e9_recommender_medium.spec 5 recommender_medium

echo "Wrote $OUT" >&2
