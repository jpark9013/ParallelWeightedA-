#!/bin/bash
# One TSV for two graphs × (w∈1,5 × threads∈1,8 × nodes∈1,2). plot_w_thr_nodes_combined.py emits
# poster_time_faceted.jpg (two panels by w), poster_efficiency.jpg (η vs nodes), poster_caption.txt.
# Pass --legacy-all-lines to that script for the older single-chart *_all_lines.jpg.
#
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=128 --exclusive \
#     --time=01:00:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_w_thr_nodes_combined.sh
#
# Sparse grid (grid_1e9_sparse), w=1, nodes=2: two ranks on *two* nodes can hit std::bad_alloc
# on this Cray stack; use two ranks on one node for those timings (see poster_caption.txt / patch_sparse scripts).
#
# Env: TIMEOUT_SEC (default 900 per run — sparse w=1 multi-node needs headroom)
set -euo pipefail

REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

MPI="./algo/parallel/astar_mpi"
OUTDIR="results/combined_w_thr_nodes"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/grid_geom_w_thr_nodes.tsv"
TIMEOUT_SEC="${TIMEOUT_SEC:-900}"

START=0
GOAL=999999999

echo -e "graph\tmode\tspec\tnodes\tw\tthreads\ttime_s\texit_code\texpansions" >"$OUT"

extract_field () {
  local key="$1"
  sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p" | head -1
}

run_one () {
  local graph="$1" mode="$2" spec="$3" nodes="$4" w="$5" threads="$6"
  export OMP_NUM_THREADS="$threads"
  set +e
  out="$(timeout "$TIMEOUT_SEC" srun -N"$nodes" -n"$nodes" -c"$threads" --cpu-bind=cores \
    "$MPI" --mode "$mode" --spec "$spec" --start "$START" --goal "$GOAL" -w "$w" 2>&1)"
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
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$graph" "$mode" "$spec" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$graph" "$mode" "$spec" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" >>"$OUT"
}

echo "== bench_w_thr_nodes_combined: TIMEOUT_SEC=$TIMEOUT_SEC OUT=$OUT =="

pairs=(
  "grid_1e9_sparse:grid:bench_specs/grid_1e9_sparse.spec"
  "recommender_medium:geom:bench_specs/geom_1e9_recommender_medium.spec"
)

nodes_list=(1 2)
w_list=(1 5)
threads_list=(1 8)

for p in "${pairs[@]}"; do
  IFS=: read -r graph mode spec <<<"$p"
  for nodes in "${nodes_list[@]}"; do
    for w in "${w_list[@]}"; do
      for threads in "${threads_list[@]}"; do
        echo "--- $graph nodes=$nodes w=$w threads=$threads ---"
        run_one "$graph" "$mode" "$spec" "$nodes" "$w" "$threads"
      done
    done
  done
done

python3 scripts/plot_w_thr_nodes_combined.py "$OUT" --outdir "$OUTDIR"
echo "Done $(date -Is)"
