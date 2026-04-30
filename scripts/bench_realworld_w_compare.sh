#!/bin/bash
# Real-world-style implicit graphs: compare weighted A* (-w 1 vs -w 5) and MPI layouts.
# Run on a compute allocation, e.g.:
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=128 --exclusive \
#     --time=00:45:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_realworld_w_compare.sh
#
# Env: SKIP_MPI=1  → serial only (quick smoke on login).
#
# Note: this MPI superstep search is not identical to serial A*; reported cost can differ
# from the serial optimum on some geom instances (distributed ordering / early goal).
set -euo pipefail
REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

SERIAL="./algo/serial/astar_serial"
MPI="./algo/parallel/astar_mpi"

NODES="${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-1}}"
CORES_PER_NODE="${SLURM_CPUS_ON_NODE:-128}"
NCORES=$((NODES * CORES_PER_NODE))
[[ "$NCORES" -ge 1 ]] || NCORES=128
echo "== bench_realworld_w_compare: NODES=$NODES NCORES=$NCORES SKIP_MPI=${SKIP_MPI:-0} =="

run_serial () {
  local w=$1
  shift
  echo "--- serial w=$w ---"
  TIMEFORMAT='wall=%R'
  time "$SERIAL" "$@" -w "$w"
}

run_mpi () {
  local desc=$1 nranks=$2 threads=$3 cpus=$4 w=$5
  shift 5
  local need=$((nranks * cpus))
  if [[ "$need" -gt "$NCORES" ]]; then
    echo "--- skip mpi $desc w=$w (needs $need cores) ---"
    return 0
  fi
  export OMP_NUM_THREADS="$threads"
  echo "--- mpi $desc w=$w (ranks=$nranks threads=$threads -c$cpus) ---"
  TIMEFORMAT='wall=%R'
  time srun -N"$NODES" -n"$nranks" -c"$cpus" --cpu-bind=cores "$MPI" "$@" -w "$w"
}

bench_graph () {
  local title=$1 mode=$2 spec=$3 st=$4 goal=$5
  echo ""
  echo "################################################################"
  echo "### $title"
  echo "### $mode $spec start=$st goal=$goal"
  echo "################################################################"
  local base=(--mode "$mode" --spec "$spec" --start "$st" --goal "$goal")

  run_serial 1 "${base[@]}"
  run_serial 5 "${base[@]}"

  if [[ "${SKIP_MPI:-0}" == "1" ]]; then
    return 0
  fi

  # (description, nranks, threads, cpus_per_rank)
  local layouts=(
    "256×1:256:1:1"
    "128×2:128:2:2"
    "64×4:64:4:4"
    "32×8:32:8:8"
    "16×16:16:16:16"
  )
  local L
  for L in "${layouts[@]}"; do
    IFS=: read -r d nr th cp <<< "$L"
    run_mpi "$d" "$nr" "$th" "$cp" 1 "${base[@]}"
    run_mpi "$d" "$nr" "$th" "$cp" 5 "${base[@]}"
  done
}

# label|mode|spec|start|goal
bench_graph "Urban blocked grid (8-neigh, ~11% blocked cells)" \
  grid bench_specs/grid_urban_blocks.spec 0 5759999

bench_graph "Large campus / light suburbs" \
  grid bench_specs/grid_campus.spec 0 12249999

bench_graph "Elongated metro strip (1500×9000, winding search)" \
  grid bench_specs/grid_elongated_metro.spec 0 13499999

bench_graph "Regional sparse kNN (few long-range links)" \
  geom bench_specs/geom_regional_roads.spec 0 2499999

bench_graph "Urban dense kNN (local mesh)" \
  geom bench_specs/geom_urban_knn.spec 0 899999

echo ""
echo "Done $(date -Is)"
