#!/bin/bash
# Compare astar_mpi_fast (shared OPEN per rank) vs astar_mpi_zob (per-thread OPEN + splitmix partition).
# Geom recommender medium 1e9, start=0 goal=999999999 w=1.
#
# Default: 1 rank per node, OpenMP threads = CPUS_PER_TASK.
# Optional many-rank mode: RUN_MANY_RANKS=1 uses 1 MPI rank per logical CPU (OMP_NUM_THREADS=1).
#
# Run inside Slurm allocation, e.g.:
#   salloc --nodes=2 --ntasks=2 --cpus-per-task=8 --exclusive --time=02:00:00 \
#     --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_zob_vs_fast.sh
#
# Append without wiping TSV (for split jobs / short interactive windows):
#   RESET_BENCH_TSV=0 bash scripts/bench_geom_zob_vs_fast.sh
#
# Run only one (nodes:ranks:omp) case, both binaries (space-separated for several):
#   BENCH_ONLY="1:1:8" RESET_BENCH_TSV=0 bash scripts/bench_geom_zob_vs_fast.sh
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
make -C algo/parallel -s astar_mpi_fast astar_mpi_zob

FAST="${FAST:-$REPO/algo/parallel/astar_mpi_fast}"
ZOB="${ZOB:-$REPO/algo/parallel/astar_mpi_zob}"
SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"
START="${START:-0}"
GOAL="${GOAL:-999999999}"
W="${W:-1}"
CPUS_PER_TASK="${CPUS_PER_TASK:-8}"
RUN_MANY_RANKS="${RUN_MANY_RANKS:-0}"
RESET_BENCH_TSV="${RESET_BENCH_TSV:-1}"
BENCH_ONLY="${BENCH_ONLY:-}"

OUTDIR="${OUTDIR:-$REPO/results/geom_zob_vs_fast}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/bench.tsv"
STAMP="$(date -Is)"

if [[ "$RESET_BENCH_TSV" == "1" ]] || [[ ! -s "$OUT" ]]; then
  echo -e "stamp\tvariant\tnodes\tmpi_ranks\tomp_threads\tcpus_per_task\ttime_s\texpansions\tcost\trc\tline" >"$OUT"
fi

extract_line () {
  printf '%s\n' "$1" | grep -E '^(cost=|no_path )' | tail -1
}

run_case () {
  local variant="$1" binary="$2" nodes="$3" ranks="$4" omp="$5" cpt="$6" extra_srun=("${@:7}")
  export OMP_NUM_THREADS="$omp"
  set +e
  out="$(srun -N"$nodes" -n"$ranks" -c"$cpt" --cpu-bind=cores "${extra_srun[@]}" \
    "$binary" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_line "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  [[ -n "$cost" ]] || cost="NA"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$STAMP" "$variant" "$nodes" "$ranks" "$omp" "$cpt" "${time_s:-NA}" "${exp:-NA}" "${cost:-NA}" "$rc" "$line" | tee -a "$OUT"
}

echo "== bench_geom_zob_vs_fast STAMP=$STAMP OUT=$OUT CPUS_PER_TASK=$CPUS_PER_TASK RUN_MANY_RANKS=$RUN_MANY_RANKS RESET_BENCH_TSV=$RESET_BENCH_TSV BENCH_ONLY=${BENCH_ONLY:-all} =="

if [[ -n "${SLURM_TIMELIMIT:-}" ]]; then
  echo "== SLURM_TIMELIMIT=$SLURM_TIMELIMIT (need ~5–6 min per case × 8 cases + margin; use --time or a longer QOS if runs stop mid-matrix) =="
fi

# (nodes, ranks, omp) — 1 rank per node unless many-ranks block below
DEFAULT_MATRIX="1:1:1 1:1:8 2:2:1 2:2:8"
if [[ -n "$BENCH_ONLY" ]]; then
  MATRIX="$BENCH_ONLY"
else
  MATRIX="$DEFAULT_MATRIX"
fi

for spec in $MATRIX; do
  IFS=: read -r nodes ranks omp <<<"$spec"
  echo "--- fast nodes=$nodes ranks=$ranks OMP=$omp ---"
  run_case "fast" "$FAST" "$nodes" "$ranks" "$omp" "$CPUS_PER_TASK"
  echo "--- zob  nodes=$nodes ranks=$ranks OMP=$omp ---"
  run_case "zob_pq" "$ZOB" "$nodes" "$ranks" "$omp" "$CPUS_PER_TASK"
done

if [[ "$RUN_MANY_RANKS" == "1" ]]; then
  # 1 rank per core on one node (Perlmutter CPU: 128 cores); OMP=1
  if [[ -n "${SLURM_CPUS_ON_NODE:-}" ]]; then
    NC="${SLURM_CPUS_ON_NODE}"
  else
    NC=128
  fi
  echo "--- many-ranks 1 node: ranks=$NC OMP=1 (fast then zob) ---"
  export OMP_NUM_THREADS=1
  run_case "fast_1rank_per_core" "$FAST" 1 "$NC" 1 1
  run_case "zob_1rank_per_core" "$ZOB" 1 "$NC" 1 1
  if [[ "${SLURM_NNODES:-1}" -ge 2 ]]; then
    echo "--- many-ranks 2 nodes: ranks=$((NC*2)) OMP=1 ---"
    run_case "fast_1rank_per_core_2n" "$FAST" 2 "$((NC * 2))" 1 1
    run_case "zob_1rank_per_core_2n" "$ZOB" 2 "$((NC * 2))" 1 1
  fi
fi

echo "Done $(date -Is)"
