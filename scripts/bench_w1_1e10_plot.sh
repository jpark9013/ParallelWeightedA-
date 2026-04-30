#!/bin/bash
# Six 10^10-vertex implicit grids, w=1, serial + MPI, TSV + SVG.
# All use 100000×100000 = 10^10 (w=1 on huge non-square 4-neigh grids is often impractically slow).
# Env SKIP_MPI=1: serial rows only (for login nodes).
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=128 --exclusive \
#     --time=00:40:00 --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_w1_1e10_plot.sh
set -euo pipefail
REPO="${REPO:-/global/homes/j/julianp1/DistributedWeightedA-}"
cd "$REPO"
export GPU_SUPPORT_ENABLED="${GPU_SUPPORT_ENABLED:-0}"

SERIAL="./algo/serial/astar_serial"
MPI="./algo/parallel/astar_mpi"
OUTDIR="${OUTDIR:-results}"
mkdir -p "$OUTDIR"
TSV="$OUTDIR/w1_1e10_times.tsv"
SVG="$OUTDIR/w1_1e10_lines.svg"

NODES="${SLURM_JOB_NUM_NODES:-${SLURM_NNODES:-1}}"
CORES_PER_NODE="${SLURM_CPUS_ON_NODE:-128}"
NCORES=$((NODES * CORES_PER_NODE))
[[ "$NCORES" -ge 1 ]] || NCORES=128

GOAL=9999999999
W=1

echo -e "graph\tconfig\ttime_s\texpansions\tcost" >"$TSV"

extract () {
  sed -n 's/.*time_s=\([0-9.]*\).*/\1/p' | head -1
}
extract_exp () {
  sed -n 's/.*expansions=\([0-9]*\).*/\1/p' | head -1
}
extract_cost () {
  sed -n 's/.*cost=\([0-9.eE+-]*\).*/\1/p' | head -1
}

record () {
  local graph=$1 config=$2 line=$3
  local ts ex co
  ts=$(echo "$line" | extract)
  ex=$(echo "$line" | extract_exp)
  co=$(echo "$line" | extract_cost)
  [[ -n "$ts" ]] || ts=NA
  [[ -n "$ex" ]] || ex=NA
  [[ -n "$co" ]] || co=NA
  printf '%s\t%s\t%s\t%s\t%s\n' "$graph" "$config" "$ts" "$ex" "$co" >>"$TSV"
}

run_serial () {
  local graph=$1 spec=$2
  echo "### $graph serial w=$W"
  local line
  line=$("$SERIAL" --mode grid --spec "$spec" --start 0 --goal "$GOAL" -w "$W" 2>&1 | tail -1)
  record "$graph" serial "$line"
}

run_mpi () {
  local graph=$1 spec=$2 tag=$3 nranks=$4 threads=$5 cpus=$6
  local need=$((nranks * cpus))
  if [[ "$need" -gt "$NCORES" ]]; then
    echo "skip $graph $tag (need $need cores)"
    return 0
  fi
  export OMP_NUM_THREADS="$threads"
  echo "### $graph $tag"
  local line
  set +e
  line=$(srun -N"$NODES" -n"$nranks" -c"$cpus" --cpu-bind=cores \
    "$MPI" --mode grid --spec "$spec" --start 0 --goal "$GOAL" -w "$W" 2>&1 | tail -1)
  set -e
  record "$graph" "$tag" "$line"
}

GRAPHS=(
  "uniform_8way:bench_specs/grid_1e10_uniform_8way.spec"
  "urban:bench_specs/grid_1e10_urban.spec"
  "campus:bench_specs/grid_1e10_campus.spec"
  "elongated_metro:bench_specs/grid_1e10_elongated.spec"
  "regional_4way:bench_specs/grid_1e10_regional_4way.spec"
  "dense_urban:bench_specs/grid_1e10_dense_urban.spec"
)

echo "NODES=$NODES NCORES=$NCORES -> TSV $TSV"

# MPI layouts: use full 256-wide set when allocated, else 128-wide (fits one CPU node).
MPI_JOBS=()
if [[ "${SKIP_MPI:-0}" != "1" ]]; then
  if [[ "$NCORES" -ge 256 ]]; then
    MPI_JOBS+=("mpi_256x1:256:1:1" "mpi_128x2:128:2:2" "mpi_64x4:64:4:4" "mpi_32x8:32:8:8" "mpi_16x16:16:16:16")
  else
    MPI_JOBS+=("mpi_128x1:128:1:1" "mpi_64x2:64:2:2" "mpi_32x4:32:4:4" "mpi_16x8:16:8:8" "mpi_8x16:8:16:16")
  fi
fi

for entry in "${GRAPHS[@]}"; do
  IFS=: read -r g spec <<<"$entry"
  run_serial "$g" "$spec"
  for mj in "${MPI_JOBS[@]}"; do
    IFS=: read -r tag nr th cp <<<"$mj"
    run_mpi "$g" "$spec" "$tag" "$nr" "$th" "$cp"
  done
done

python3 scripts/plot_w5_1e11_bars.py "$TSV" -o "$SVG" \
  --title "Weighted A* w=1 · implicit grids · 10^10 vertices each · time_s (lower is better)"
echo "Wrote $SVG"
ls -la "$TSV" "$SVG"
