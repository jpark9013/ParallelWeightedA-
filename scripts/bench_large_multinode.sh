#!/bin/bash
# Large-scale serial vs MPI (run under salloc on CPU nodes).
#
# Two-node example (256 cores total, 30 min wall):
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=128 --exclusive \
#     --time=00:30:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_large_multinode.sh
#
# One-node (128 cores): same script; MPI configs that need >128 cores are skipped.
set -euo pipefail
REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

SERIAL="./algo/serial/astar_serial"
MPI="./algo/parallel/astar_mpi"

NODES="${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-1}}"
# Typical Perlmutter CPU node: 128 logical CPUs per node when fully allocated.
CORES_PER_NODE="${SLURM_CPUS_ON_NODE:-128}"
NCORES=$((NODES * CORES_PER_NODE))
if [[ "$NCORES" -lt 1 ]]; then NCORES=128; fi
echo "Detected allocation: NODES=$NODES CORES_PER_NODE=$CORES_PER_NODE NCORES=$NCORES"

run_case () {
  local label=$1
  shift
  echo ""
  echo "######## $label ########"
  echo "--- serial ---"
  TIMEFORMAT='wall_clock_s=%R'
  time "$SERIAL" "$@"
}

run_mpi () {
  local desc=$1 nranks=$2 threads=$3 cpus_per_rank=$4
  shift 4
  local need=$((nranks * cpus_per_rank))
  if [[ "$need" -gt "$NCORES" ]]; then
    echo "--- skip mpi $desc (needs ${need} cores, have ${NCORES}) ---"
    return 0
  fi
  export OMP_NUM_THREADS="$threads"
  echo ""
  echo "--- mpi $desc (ranks=$nranks threads=$threads cpus_per_rank=$cpus_per_rank) ---"
  TIMEFORMAT='wall_clock_s=%R'
  time srun -N"$NODES" -n"$nranks" -c"$cpus_per_rank" --cpu-bind=cores "$MPI" "$@"
}

GRID1E10_SPEC="bench_specs/grid_1e10_8way.spec"
GRID1E10_GOAL=9999999999
run_case "GRID 10^10 vertices (100k×100k, 8-neigh), w=1" \
  --mode grid --spec "$GRID1E10_SPEC" --start 0 --goal "$GRID1E10_GOAL" -w 1

GEOM1E9_SPEC="bench_specs/geom_1e9_dense_knn.spec"
GEOM1E9_GOAL=999999999
run_case "GEOM 10^9 vertices (k=96, candidates=384), w=1" \
  --mode geom --spec "$GEOM1E9_SPEC" --start 0 --goal "$GEOM1E9_GOAL" -w 1

GEOM_ARGS=(--mode geom --spec "$GEOM1E9_SPEC" --start 0 --goal "$GEOM1E9_GOAL" -w 1)
GRID_ARGS=(--mode grid --spec "$GRID1E10_SPEC" --start 0 --goal "$GRID1E10_GOAL" -w 1)

echo ""
echo "######## MPI scaling on GEOM 10^9 ########"
run_mpi "256×1" 256 1 1 "${GEOM_ARGS[@]}"
run_mpi "128×2" 128 2 2 "${GEOM_ARGS[@]}"
run_mpi "64×4" 64 4 4 "${GEOM_ARGS[@]}"
run_mpi "32×8" 32 8 8 "${GEOM_ARGS[@]}"
run_mpi "16×16" 16 16 16 "${GEOM_ARGS[@]}"
run_mpi "8×32" 8 32 32 "${GEOM_ARGS[@]}"

echo ""
echo "######## MPI on GRID 10^10 ########"
run_mpi "128×2" 128 2 2 "${GRID_ARGS[@]}"
run_mpi "64×4" 64 4 4 "${GRID_ARGS[@]}"
run_mpi "32×8" 32 8 8 "${GRID_ARGS[@]}"

echo ""
echo "Done $(date -Is)"
