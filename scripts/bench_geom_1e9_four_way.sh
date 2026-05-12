#!/bin/bash
# Four-way scaling study on geom_1e9_recommender_medium:
#   (1) serial (no MPI), 1 thread
#   (2) MPI 1 rank / 1 node, OMP_NUM_THREADS=8
#   (3) MPI 2 ranks / 2 nodes, OMP_NUM_THREADS=1 per rank
#   (4) MPI 2 ranks / 2 nodes, OMP_NUM_THREADS=8 per rank
#
# Intended to run *inside* an allocation that spans at least 2 nodes, e.g.:
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=8 --exclusive \
#     --time=01:30:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_1e9_four_way.sh
#
# Or from repo root with existing multi-node job step resources.
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"

SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"
START="${START:-0}"
GOAL="${GOAL:-999999999}"
W="${W:-1}"

SERIAL="${SERIAL:-$REPO/algo/serial/astar_serial}"
MPI="${MPI:-$REPO/algo/parallel/astar_mpi_fast}"

OUTDIR="${OUTDIR:-$REPO/results/geom_1e9_four_way}"
mkdir -p "$OUTDIR"
OUT="${OUTDIR}/geom_1e9_four_way.tsv"
STAMP="$(date -Is)"

extract_time_exp_cost () {
  printf '%s\n' "$1" | grep -E '^(cost=|no_path )' | tail -1
}

echo -e "stamp\tconfig\tnodes\tmpi_ranks\tomp_threads\ttime_s\texpansions\tcost\trc\tline" >"$OUT"

run_serial () {
  local label="$1"
  export OMP_NUM_THREADS=1
  set +e
  out="$("$SERIAL" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_time_exp_cost "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  if [[ -z "$cost" ]]; then cost="NA"; fi
  printf '%s\n' "$STAMP	$label	1	0	1	${time_s:-NA}	${exp:-NA}	${cost:-NA}	$rc	$line" | tee -a "$OUT"
}

run_mpi () {
  local label="$1" nodes="$2" ranks="$3" cpus_per_task="$4" omp="$5"
  shift 5
  export OMP_NUM_THREADS="$omp"
  set +e
  out="$(srun "$@" "$MPI" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_time_exp_cost "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  if [[ -z "$cost" ]]; then cost="NA"; fi
  printf '%s\n' "$STAMP	$label	$nodes	$ranks	$omp	${time_s:-NA}	${exp:-NA}	${cost:-NA}	$rc	$line" | tee -a "$OUT"
}

echo "== bench_geom_1e9_four_way: SPEC=$SPEC OUT=$OUT STAMP=$STAMP =="

echo "--- (1) serial, 1 thread ---"
run_serial "serial_1x1"

echo "--- (2) 1 node, 1 rank, 8 threads ---"
run_mpi "mpi_1n1r8t" 1 1 8 8 -N1 -n1 -c8 --cpu-bind=cores

echo "--- (3) 2 nodes, 2 ranks, 1 thread per rank ---"
run_mpi "mpi_2n2r1t" 2 2 1 1 -N2 -n2 -c1 --cpu-bind=cores

echo "--- (4) 2 nodes, 2 ranks, 8 threads per rank ---"
run_mpi "mpi_2n2r8t" 2 2 8 8 -N2 -n2 -c8 --cpu-bind=cores

echo "Done $(date -Is)"
