#!/bin/bash
# Benchmark astar_mpi_fast on geom_1e9_recommender using:
#   - 1 node
#   - ranks-per-node = 1 / 8 / 128
#   - heap = stl vs 4ary
#
# This script is tailored to the current codebase:
#   --heap stl|4ary
#   --inbox critical|localpq|sharded
#
# Recommended interactive allocation:
#
# salloc --nodes=1 --ntasks=128 --cpus-per-task=1 \
#   --exclusive --time=02:00:00 \
#   --qos=interactive --constraint=cpu \
#   --account=m4341 bash
#
# Usage:
#   bash scripts/bench_geom_1e9_heap_compare.sh
#
# Optional overrides:
#   MPI=... SPEC=... OUTDIR=... \
#   BUDGET=... INBOX=... \
#   bash scripts/bench_geom_1e9_heap_compare.sh

set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"

MPI="${MPI:-$REPO/algo/parallel/astar_mpi_fast}"

# Adjust if your filename differs.
SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"

START="${START:-0}"
GOAL="${GOAL:-999999999}"

# Weighted A*
W="${W:-1}"

# Superstep budget
BUDGET="${BUDGET:-256}"

# Inbox implementation:
#   critical | localpq | sharded
#
# Your code defaults to sharded and that is almost certainly
# the best choice for geom_1e9.
INBOX="${INBOX:-sharded}"

# Heaps to compare
HEAPS="${HEAPS:-stl 4ary}"

# MPI ranks per node
RPN_LIST="${RPN_LIST:-1 8 128}"

# Number of repeated trials per config
REPEATS="${REPEATS:-3}"

# Pinning / placement
CPU_BIND="${CPU_BIND:-cores}"

OUTDIR="${OUTDIR:-$REPO/results/geom_1e9_heap_compare}"
mkdir -p "$OUTDIR"

OUT="$OUTDIR/timing.tsv"
LOGDIR="$OUTDIR/logs"
mkdir -p "$LOGDIR"

STAMP="$(date -Is)"

echo -e \
"stamp\tnodes\tranks_per_node\tmpi_ranks\tomp_threads\theap\tinbox\tbudget\trepeat\ttime_s\texpansions\tcost\trc\tline" \
> "$OUT"

###############################################################################
# Thread policy
#
# Your code uses OpenMP inside:
#   - neighbor scoring
#   - inbox processing
#
# For geom graphs, hybrid mode usually matters.
#
# Suggested layout:
#   rpn=1   -> 32 threads
#   rpn=8   -> 8 threads
#   rpn=128 -> 1 thread
#
# Override with:
#   THREADS_1=...
#   THREADS_8=...
#   THREADS_128=...
###############################################################################

THREADS_1="${THREADS_1:-32}"
THREADS_8="${THREADS_8:-8}"
THREADS_128="${THREADS_128:-1}"

threads_for_rpn () {
  local rpn="$1"

  case "$rpn" in
    1)   echo "$THREADS_1" ;;
    8)   echo "$THREADS_8" ;;
    128) echo "$THREADS_128" ;;
    *)   echo 1 ;;
  esac
}

###############################################################################
# Run one benchmark configuration
###############################################################################

run () {
  local rpn="$1"
  local heap="$2"
  local rep="$3"

  local omp_threads
  omp_threads="$(threads_for_rpn "$rpn")"

  export OMP_NUM_THREADS="$omp_threads"
  export OMP_PROC_BIND=close
  export OMP_PLACES=cores

  local tag="heap_${heap}_rpn_${rpn}_omp_${omp_threads}_rep_${rep}"
  local logfile="$LOGDIR/${tag}.log"

  echo
  echo "=================================================================="
  echo "RUN:"
  echo "  heap         = $heap"
  echo "  inbox        = $INBOX"
  echo "  ranks/node   = $rpn"
  echo "  omp_threads  = $omp_threads"
  echo "  repeat       = $rep"
  echo "  logfile      = $logfile"
  echo "=================================================================="

  set +e

  out="$(
    srun \
      -N1 \
      -n"$rpn" \
      --ntasks-per-node="$rpn" \
      -c"$omp_threads" \
      --cpu-bind="$CPU_BIND" \
      "$MPI" \
        --mode geom \
        --spec "$SPEC" \
        --start "$START" \
        --goal "$GOAL" \
        -w "$W" \
        --budget "$BUDGET" \
        --heap "$heap" \
        --inbox "$INBOX" \
      2>&1
  )"

  rc=$?

  set -e

  printf '%s\n' "$out" | tee "$logfile"

  line="$(
    printf '%s\n' "$out" \
      | grep -E '^(cost=|no_path )' \
      | tail -1
  )"

  time_s="$(
    printf '%s\n' "$line" \
      | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p'
  )"

  exp="$(
    printf '%s\n' "$line" \
      | sed -n 's/.*expansions=\([0-9]*\).*/\1/p'
  )"

  cost="$(
    printf '%s\n' "$line" \
      | sed -n 's/^cost=\([^ ]*\).*/\1/p'
  )"

  [[ -n "$cost" ]] || cost="NA"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$STAMP" \
    "1" \
    "$rpn" \
    "$rpn" \
    "$omp_threads" \
    "$heap" \
    "$INBOX" \
    "$BUDGET" \
    "$rep" \
    "${time_s:-NA}" \
    "${exp:-NA}" \
    "${cost:-NA}" \
    "$rc" \
    "$line" \
    | tee -a "$OUT"
}

###############################################################################
# Main
###############################################################################

echo
echo "==============================================================="
echo "geom_1e9_recommender heap benchmark"
echo "==============================================================="
echo "MPI          : $MPI"
echo "SPEC         : $SPEC"
echo "OUT          : $OUT"
echo "LOGDIR       : $LOGDIR"
echo "HEAPS        : $HEAPS"
echo "RPN_LIST     : $RPN_LIST"
echo "REPEATS      : $REPEATS"
echo "INBOX        : $INBOX"
echo "BUDGET       : $BUDGET"
echo "==============================================================="
echo

for heap in $HEAPS; do
  for rpn in $RPN_LIST; do
    for rep in $(seq 1 "$REPEATS"); do
      run "$rpn" "$heap" "$rep"
    done
  done
done

echo
echo "Done $(date -Is)"
echo
echo "Results:"
echo "  $OUT"
echo
echo "Per-run logs:"
echo "  $LOGDIR"