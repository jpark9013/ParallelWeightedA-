#!/bin/bash
# Matrix: w∈{1,5} × threads∈{1,8} × MPI nodes∈{1,2} for:
#   (A) Implicit GRID n=10^9 — bench_specs/grid_1e9_sparse.spec
#   (B) CSR graph — graphgen/data/tests/planar_n1000.txt (see README: true CSR n=10^9 not feasible)
#
# Output TSV includes cost= when present.
#
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=128 --exclusive \
#     --time=04:00:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_csr_planar_and_grid_1e9_sweep.sh
#
set -euo pipefail
REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

MPI="./algo/parallel/astar_mpi"
OUTDIR="results/csr_grid_1e9_matrix"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/sweep.tsv"
TIMEOUT_GRID="${TIMEOUT_GRID:-900}"
TIMEOUT_CSR="${TIMEOUT_CSR:-120}"

GRID_SPEC="bench_specs/grid_1e9_sparse.spec"
GRID_START=0
GRID_GOAL=999999999

CSR_EDGES="graphgen/data/tests/planar_n1000.txt"
CSR_START=0
CSR_GOAL=999

README="$OUTDIR/README.txt"
cat >"$README" <<'EOF'
CSR n = 10^9 vs this benchmark
------------------------------
The CSR loader (algo/common/csr_graph.hpp) builds an adjacency list with one vector per vertex and
loads all edges into memory. A graph with ~10^9 vertices cannot be constructed this way on typical HPC nodes.

This sweep therefore uses the bundled planar test graph (~1000 vertices, planar_n1000.txt) as the CSR case.
For CSR mode the heuristic is h=0, so weighted A* uses f=g regardless of -w; w=1 vs w=5 should give the same
ordering (expect nearly identical time_s / expansions).

Grid case uses implicit grid_1e9_sparse.spec (10^9 vertices, 4-neighbour unit grid, no obstacles).
EOF

echo -e "graph\tmode\tpath\tnodes\tw\tthreads\ttime_s\texit_code\texpansions\tcost" >"$OUT"

extract_field () {
  local key="$1"
  sed -n "s/.*${key}=\\([^ ]*\\).*/\\1/p" | head -1
}

run_grid () {
  local nodes=$1 w=$2 threads=$3
  export OMP_NUM_THREADS="$threads"
  set +e
  out="$(timeout "$TIMEOUT_GRID" srun -N"$nodes" -n"$nodes" -c"$threads" --cpu-bind=cores \
    "$MPI" --mode grid --spec "$GRID_SPEC" --start "$GRID_START" --goal "$GRID_GOAL" -w "$w" 2>&1)"
  rc=$?
  set -e
  time_s="NA"; exp="NA"; cost="NA"
  if [[ "$rc" == "0" || "$rc" == "1" ]]; then
    line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
    time_s="$(printf '%s\n' "$line" | extract_field time_s)"
    exp="$(printf '%s\n' "$line" | extract_field expansions)"
    cost="$(printf '%s\n' "$line" | extract_field cost)"
    [[ -n "$time_s" ]] || time_s="NA"
    [[ -n "$exp" ]] || exp="NA"
    [[ -n "$cost" ]] || cost="NA"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "grid_1e9_sparse" "grid" "$GRID_SPEC" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" "$cost"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "grid_1e9_sparse" "grid" "$GRID_SPEC" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" "$cost" >>"$OUT"
}

run_csr () {
  local nodes=$1 w=$2 threads=$3
  export OMP_NUM_THREADS="$threads"
  set +e
  out="$(timeout "$TIMEOUT_CSR" srun -N"$nodes" -n"$nodes" -c"$threads" --cpu-bind=cores \
    "$MPI" --mode csr --edges "$CSR_EDGES" --start "$CSR_START" --goal "$CSR_GOAL" -w "$w" 2>&1)"
  rc=$?
  set -e
  time_s="NA"; exp="NA"; cost="NA"
  if [[ "$rc" == "0" || "$rc" == "1" ]]; then
    line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
    time_s="$(printf '%s\n' "$line" | extract_field time_s)"
    exp="$(printf '%s\n' "$line" | extract_field expansions)"
    cost="$(printf '%s\n' "$line" | extract_field cost)"
    [[ -n "$time_s" ]] || time_s="NA"
    [[ -n "$exp" ]] || exp="NA"
    [[ -n "$cost" ]] || cost="NA"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "csr_planar_n1000" "csr" "$CSR_EDGES" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" "$cost"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "csr_planar_n1000" "csr" "$CSR_EDGES" "$nodes" "$w" "$threads" "$time_s" "$rc" "$exp" "$cost" >>"$OUT"
}

echo "== bench_csr_planar_and_grid_1e9_sweep OUT=$OUT TIMEOUT_GRID=$TIMEOUT_GRID TIMEOUT_CSR=$TIMEOUT_CSR =="

nodes_list=(1 2)
w_list=(1 5)
threads_list=(1 8)

for nodes in "${nodes_list[@]}"; do
  for w in "${w_list[@]}"; do
    for threads in "${threads_list[@]}"; do
      echo "--- GRID grid_1e9_sparse nodes=$nodes w=$w threads=$threads ---"
      run_grid "$nodes" "$w" "$threads"
    done
  done
done

for nodes in "${nodes_list[@]}"; do
  for w in "${w_list[@]}"; do
    for threads in "${threads_list[@]}"; do
      echo "--- CSR planar_n1000 nodes=$nodes w=$w threads=$threads ---"
      run_csr "$nodes" "$w" "$threads"
    done
  done
done

echo "Done $(date -Is)"
