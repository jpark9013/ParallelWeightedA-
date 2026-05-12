#!/bin/bash
# Time `astar_mpi_fast` on geom_1e9_recommender_medium for nodes=1 and nodes=2.
# Run inside a Slurm allocation with >=2 nodes when testing N=2, e.g.:
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=8 --exclusive \
#     --time=01:00:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_medium_n1_n2.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"

MPI="${MPI:-$REPO/algo/parallel/astar_mpi_fast}"
SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"
START="${START:-0}"
GOAL="${GOAL:-999999999}"
W="${W:-1}"
OMP_THREADS="${OMP_THREADS:-8}"
CPUS_PER_TASK="${CPUS_PER_TASK:-8}"

OUTDIR="${OUTDIR:-$REPO/results/geom_medium_n1_n2}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/timing.tsv"
STAMP="$(date -Is)"

echo -e "stamp\tnodes\tmpi_ranks\tomp_threads\ttime_s\texpansions\tcost\trc\tline" >"$OUT"

run () {
  local nodes="$1"
  export OMP_NUM_THREADS="$OMP_THREADS"
  set +e
  out="$(srun -N"$nodes" -n"$nodes" -c"$CPUS_PER_TASK" --cpu-bind=cores \
    "$MPI" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  [[ -n "$cost" ]] || cost="NA"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$STAMP" "$nodes" "$nodes" "$OMP_THREADS" "${time_s:-NA}" "${exp:-NA}" "${cost:-NA}" "$rc" "$line" | tee -a "$OUT"
}

echo "== bench_geom_medium_n1_n2 SPEC=$SPEC OMP=$OMP_THREADS cpus/task=$CPUS_PER_TASK OUT=$OUT =="
echo "--- nodes=1 ---"
run 1
echo "--- nodes=2 ---"
run 2
echo "Done $(date -Is)"
