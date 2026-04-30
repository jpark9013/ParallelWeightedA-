#!/bin/bash
# Interactive/long-timeout rerun for sparse grid @ 2 ranks, w=1 only.
# Writes RESULT lines to a log file and patches combined TSV + regenerates JPG.
#
# Interactive QOS max wall is often 4h — each sparse w=1 run can exceed that alone.
# Run **one** threads setting per allocation unless both finish comfortably under the wall.
#
# Usage (inside salloc -N2 …):
#   bash scripts/rerun_sparse_grid_w1_node2_inline.sh        # threads 1 then 8 (same allocation)
#   bash scripts/rerun_sparse_grid_w1_node2_inline.sh 1      # only OMP threads=1
#   bash scripts/rerun_sparse_grid_w1_node2_inline.sh 8      # only OMP threads=8
#
#   export SPARSE_W1_TIMEOUT=14400   # max seconds per srun (default 14400 ≈ 4h)
#
set -euo pipefail
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

MPI="./algo/parallel/astar_mpi"
SPEC="bench_specs/grid_1e9_sparse.spec"
OUT="results/combined_w_thr_nodes/grid_geom_w_thr_nodes.tsv"
mkdir -p results/combined_w_thr_nodes
LOG="results/combined_w_thr_nodes/sparse_w1_node2_rerun_$(date +%Y%m%d_%H%M%S).log"
TO="${SPARSE_W1_TIMEOUT:-14400}"

MODE="${1:-both}"

extract_field() {
  local key="$1"
  sed -n "s/.*${key}=\([^ ]*\).*/\1/p" | head -1
}

run_case() {
  local t=$1 c=$2
  export OMP_NUM_THREADS="$t"
  set +e
  local out
  out="$(timeout "$TO" srun -N2 -n2 -c"$c" --cpu-bind=cores \
    "$MPI" --mode grid --spec "$SPEC" --start 0 --goal 999999999 -w 1 2>&1)"
  rc=$?
  set -e
  time_s="NA"
  exp="NA"
  if [[ "$rc" == "0" || "$rc" == "1" ]]; then
    line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
    time_s="$(printf '%s\n' "$line" | extract_field time_s)"
    exp="$(printf '%s\n' "$line" | extract_field expansions)"
    [[ -n "$time_s" ]] || time_s="NA"
    [[ -n "$exp" ]] || exp="NA"
  fi
  printf '%s\n' "$out"
  echo "RESULT threads=$t cpus=$c rc=$rc time_s=$time_s expansions=$exp"
}

{
  if [[ "$MODE" == "1" ]]; then
    echo "=== $(date -Is) threads=1 cpus=1 ==="
    run_case 1 1
  elif [[ "$MODE" == "8" ]]; then
    echo "=== $(date -Is) threads=8 cpus=8 ==="
    run_case 8 8
  else
    echo "=== $(date -Is) threads=1 cpus=1 ==="
    run_case 1 1
    echo "=== $(date -Is) threads=8 cpus=8 ==="
    run_case 8 8
  fi
} 2>&1 | tee "$LOG"

python3 scripts/patch_sparse_grid_from_slurm_out.py "$LOG" "$OUT"
echo "log: $LOG"
