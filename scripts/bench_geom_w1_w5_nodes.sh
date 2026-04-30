#!/bin/bash
# Linear-scale comparison: w=1 vs w=5 for nodes=1,2,4 (1 rank/node, 1 OpenMP thread/rank).
# Graphs: recommender medium + dense social-embedding kNN (see bench_specs).
#
# Run on a compute allocation, e.g.:
#   salloc --nodes=4 --ntasks=4 --cpus-per-task=128 --exclusive \
#     --time=01:00:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_w1_w5_nodes.sh
#
# Env: TIMEOUT_SEC=900  (per run, default 900)
set -euo pipefail

REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

MPI="./algo/parallel/astar_mpi"
OUTDIR="results/geom_w_compare"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/w1_w5_nodes.tsv"
TIMEOUT_SEC="${TIMEOUT_SEC:-900}"

# Far endpoints on the 1e9 vertex implicit geom graph
GOAL=999999999
START=0

echo -e "graph\tnodes\tw\tthreads\ttime_s\texit_code\texpansions" >"$OUT"

extract_field () {
  local key="$1"
  sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p" | head -1
}

run_one () {
  local gkey="$1" spec="$2" nodes="$3" w="$4"
  export OMP_NUM_THREADS=1
  set +e
  out="$(timeout "$TIMEOUT_SEC" srun -N"$nodes" -n"$nodes" -c1 --cpu-bind=cores \
    "$MPI" --mode geom --spec "$spec" --start "$START" --goal "$GOAL" -w "$w" 2>&1)"
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

  printf '%s\t%s\t%s\t1\t%s\t%s\t%s\n' "$gkey" "$nodes" "$w" "$time_s" "$rc" "$exp"
  printf '%s\t%s\t%s\t1\t%s\t%s\t%s\n' "$gkey" "$nodes" "$w" "$time_s" "$rc" "$exp" >>"$OUT"
}

echo "== bench_geom_w1_w5_nodes: TIMEOUT_SEC=$TIMEOUT_SEC OUT=$OUT =="

graphs=(
  "recommender_medium:bench_specs/geom_1e9_recommender_medium.spec"
  "social_embedding_dense:bench_specs/geom_1e9_social_embedding_dense.spec"
)

nodes_list=(1 2 4)
w_list=(1 5)

for entry in "${graphs[@]}"; do
  IFS=: read -r gkey spec <<<"$entry"
  for nodes in "${nodes_list[@]}"; do
    for w in "${w_list[@]}"; do
      echo "--- $gkey nodes=$nodes w=$w ---"
      run_one "$gkey" "$spec" "$nodes" "$w"
    done
  done
done

python3 scripts/plot_w1_w5_nodes_linear.py "$OUT" --outdir "$OUTDIR"
echo "Done $(date -Is)"
