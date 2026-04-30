#!/bin/bash
# Sparse case where parallel often does poorly: 4-neighbor grid (low degree, cheap expansions).
# Runs w=1 vs w=5 across nodes and threads, then emits per-thread 2-line linear plots (nodes on x-axis).
#
# Run on a compute allocation, e.g.:
#   salloc --nodes=4 --ntasks=4 --cpus-per-task=128 --exclusive \
#     --time=00:45:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_grid_sparse_w1_w5_nodes_threads.sh
#
# Env:
#   TIMEOUT_SEC=300  (per run, default 300)
set -euo pipefail

REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

MPI="./algo/parallel/astar_mpi"
OUTDIR="results/grid_sparse_w_compare"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/w1_w5_nodes_threads.tsv"
TIMEOUT_SEC="${TIMEOUT_SEC:-300}"

SPEC="bench_specs/grid_1e9_sparse.spec"
START=0
GOAL=999999999

echo -e "graph\tnodes\tw\tthreads\ttime_s\texit_code\texpansions" >"$OUT"

extract_field () {
  local key="$1"
  sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p" | head -1
}

run_one () {
  local nodes="$1" w="$2" threads="$3"
  export OMP_NUM_THREADS="$threads"

  set +e
  out="$(timeout "$TIMEOUT_SEC" srun -N"$nodes" -n"$nodes" -c"$threads" --cpu-bind=cores \
    "$MPI" --mode grid --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$w" 2>&1)"
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

  printf 'grid_1e9_sparse\t%s\t%s\t%s\t%s\t%s\t%s\n' "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp"
  printf 'grid_1e9_sparse\t%s\t%s\t%s\t%s\t%s\t%s\n' "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" >>"$OUT"
}

echo "== bench_grid_sparse_w1_w5_nodes_threads: SPEC=$SPEC TIMEOUT_SEC=$TIMEOUT_SEC OUT=$OUT =="

nodes_list=(1 2 4)
threads_list=(1 8)
w_list=(1 5)

for threads in "${threads_list[@]}"; do
  for nodes in "${nodes_list[@]}"; do
    for w in "${w_list[@]}"; do
      echo "--- grid_1e9_sparse nodes=$nodes threads=$threads w=$w ---"
      run_one "$nodes" "$w" "$threads"
    done
  done
done

python3 scripts/plot_w1_w5_nodes_linear_by_threads.py "$OUT" --outdir "$OUTDIR"
echo "Done $(date -Is)"

