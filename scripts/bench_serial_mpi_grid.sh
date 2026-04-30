#!/bin/bash
# Run inside an interactive CPU allocation, e.g. (short wall time to save hours):
#   salloc --nodes 1 --ntasks=1 --cpus-per-task=128 --time=00:15:00 \
#     --qos interactive --constraint cpu --account=m4341 \
#     bash /path/to/DistributedWeightedA-/scripts/bench_serial_mpi_grid.sh
# Build on login: make -C algo/serial && make -C algo/parallel
set -euo pipefail
REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"

# Cray MPICH on login can require this; harmless on compute.
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

SERIAL="./algo/serial/astar_serial"
MPI="./algo/parallel/astar_mpi"
SPEC="bench_specs/grid_sparse.spec"
GRID_GOAL=$((600 * 600 - 1))
ARGS=(--mode grid --spec "$SPEC" --start 0 --goal "$GRID_GOAL" -w 1)

echo "host=$(hostname) date=$(date -Is)"
echo "=== Serial (no MPI; serial binary is not OpenMP-enabled) ==="
for i in 1 2; do
  echo "--- serial run $i ---"
  TIMEFORMAT='wall_clock_s=%R'
  time "$SERIAL" "${ARGS[@]}"
done

# Hybrid runs: ranks * threads should fit allocated cores (128 on Perlmutter CPU node).
# srun -n R -c C with OMP_NUM_THREADS=T: use C>=T and R*C <= allocated CPUs.
run_hybrid () {
  local ranks=$1 threads=$2 cpus_per_rank=$3 label=$4
  export OMP_NUM_THREADS="$threads"
  echo "=== $label: MPI ranks=$ranks OMP_NUM_THREADS=$threads srun -c $cpus_per_rank ==="
  TIMEFORMAT='wall_clock_s=%R'
  time srun -n "$ranks" -c "$cpus_per_rank" --cpu-bind=cores "$MPI" "${ARGS[@]}"
}

run_hybrid 16 8 8 "full_node 16ranks x 8threads (128 cores)"
run_hybrid 8 8 8 "8ranks x 8threads (64 cores)"
run_hybrid 4 32 32 "full_node 4ranks x 32threads"
run_hybrid 2 32 32 "2ranks x 32threads (64 cores)"
run_hybrid 2 64 64 "full_node 2ranks x 64threads"
run_hybrid 1 64 64 "1rank x 64threads"

echo "done $(date -Is)"
