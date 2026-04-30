#!/bin/bash
# Run the requested sweep:
#   nodes = 1,2,4
#   w     = 1,3,5
#   threads/node = 1,2,32,128
#   graphs = n=1e9/1e10 × sparse/dense (grid 4-neigh vs 8-neigh)
#
# IMPORTANT: run inside an allocation that can support the max config, e.g.
#   salloc --nodes=4 --ntasks=4 --cpus-per-task=128 --exclusive \
#     --time=00:35:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/run_nodes_w_threads_sweep.sh
#
# Output: results/sweep_w_threads/sweep.tsv
set -euo pipefail

REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

OUTDIR="results/sweep_w_threads"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/sweep.tsv"

ASTAR="./algo/parallel/astar_mpi"

graphs=(
  "n1e9_sparse:bench_specs/grid_1e9_sparse.spec:999999999"
  "n1e9_dense:bench_specs/grid_1e9_dense.spec:999999999"
  "n1e10_sparse:bench_specs/grid_1e10_sparse.spec:9999999999"
  "n1e10_dense:bench_specs/grid_1e10_dense.spec:9999999999"
)

nodes_list=(1 2 4)
w_list=(1 3 5)
threads_list=(1 2 32 128)

echo -e "nodes\tw\tgraph\tthreads_per_node\texit_code\ttime_s\texpansions\tcost" >"$OUT"

extract_field () {
  local key="$1"
  sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p" | head -1
}

timeout_for () {
  # Keep overall sweep bounded; sparse 4-neigh cases can explode at w=1.
  local g="$1" w="$2"
  if [[ "$g" == *"sparse"* ]]; then
    if [[ "$w" == "1" ]]; then echo 20; else echo 30; fi
    return
  fi
  # dense 8-neigh: still can be heavy at n=1e10 + w=1
  if [[ "$g" == *"n1e10_dense"* ]]; then echo 60; return; fi
  echo 40
}

run_one () {
  local nodes="$1" w="$2" gname="$3" spec="$4" goal="$5" tpn="$6"
  local to
  to="$(timeout_for "$gname" "$w")"

  export OMP_NUM_THREADS="$tpn"
  # Use 1 rank per node so x-axis is threads/node exactly.
  set +e
  out="$(timeout "$to" srun -N"$nodes" -n"$nodes" -c"$tpn" --cpu-bind=cores \
    "$ASTAR" --mode grid --spec "$spec" --start 0 --goal "$goal" -w "$w" \
    2>&1)"
  rc=$?
  set -e

  time_s="NA"; exp="NA"; cost="NA"
  if [[ "$rc" == "0" || "$rc" == "1" ]]; then
    # rank0 prints the summary line; take last matching.
    line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
    time_s="$(printf '%s\n' "$line" | extract_field time_s)"
    exp="$(printf '%s\n' "$line" | extract_field expansions)"
    cost="$(printf '%s\n' "$line" | extract_field cost)"
    [[ -n "$time_s" ]] || time_s="NA"
    [[ -n "$exp" ]] || exp="NA"
    [[ -n "$cost" ]] || cost="NA"
  fi

  echo -e "${nodes}\t${w}\t${gname}\t${tpn}\t${rc}\t${time_s}\t${exp}\t${cost}" >>"$OUT"
}

echo "Writing $OUT"

for g in "${graphs[@]}"; do
  IFS=: read -r gname spec goal <<<"$g"
  for nodes in "${nodes_list[@]}"; do
    for w in "${w_list[@]}"; do
      for tpn in "${threads_list[@]}"; do
        echo "nodes=$nodes w=$w graph=$gname tpn=$tpn"
        run_one "$nodes" "$w" "$gname" "$spec" "$goal" "$tpn"
      done
    done
  done
done

echo "Done. TSV: $OUT"

