#!/bin/bash
# Geom recommender medium n=1e9: one MPI rank per logical core, OMP_NUM_THREADS=1.
# Compares 1-node runs with 1, 8, and full-node rank counts (default full = 128 or SLURM_CPUS_ON_NODE).
#
# srun: -n R -c 1 --cpu-bind=cores  => each rank bound to one CPU.
#
# Example (full node on Perlmutter CPU):
#   salloc -N1 --exclusive --ntasks=128 --cpus-per-task=1 --time=02:00:00 \
#     --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_mpi_per_core.sh
#
# Smaller allocation (e.g. 8 CPUs): runs 1 and 8 ranks; skips full-node case if R > SLURM_CPUS_ON_NODE.
#
# Env:
#   BINARY=.../astar_mpi_fast   (default: repo build)
#   FULL_NODE_RANKS=128         (used when SLURM_CPUS_ON_NODE unset)
#   RANK_LIST="1 8 128"         (override rank counts)
#   RESET_BENCH_TSV=0           (append to existing TSV)
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
make -C algo/parallel -s astar_mpi_fast

BINARY="${BINARY:-$REPO/algo/parallel/astar_mpi_fast}"
SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"
START="${START:-0}"
GOAL="${GOAL:-999999999}"
W="${W:-1}"
RESET_BENCH_TSV="${RESET_BENCH_TSV:-1}"
FULL_NODE_RANKS="${FULL_NODE_RANKS:-128}"
RANK_LIST="${RANK_LIST:-}"

OUTDIR="${OUTDIR:-$REPO/results/geom_mpi_per_core}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/bench.tsv"
STAMP="$(date -Is)"

if [[ "$RESET_BENCH_TSV" == "1" ]] || [[ ! -s "$OUT" ]]; then
  echo -e "stamp\tvariant\tnodes\tmpi_ranks\tomp_threads\tcpus_per_task\ttime_s\texpansions\tcost\trc\tline" >"$OUT"
fi

extract_line () {
  # Avoid pipefail exit 1 when srun fails and there is no cost= line.
  { printf '%s\n' "$1" | grep -E '^(cost=|no_path )' | tail -1; } || true
}

run_ranks () {
  local ranks="$1"
  export OMP_NUM_THREADS=1
  echo "--- mpi_per_core nodes=1 ranks=$ranks cpus_per_rank=1 OMP=1 ---"
  set +e
  out="$(srun -N1 -n"$ranks" -c1 --cpu-bind=cores \
    "$BINARY" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_line "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  [[ -n "$cost" ]] || cost="NA"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$STAMP" "mpi_per_core" 1 "$ranks" 1 1 "${time_s:-NA}" "${exp:-NA}" "${cost:-NA}" "$rc" "$line" | tee -a "$OUT"
}

echo "== bench_geom_mpi_per_core STAMP=$STAMP OUT=$OUT BINARY=$BINARY =="

if [[ -n "${SLURM_TIMELIMIT:-}" ]]; then
  echo "== SLURM_TIMELIMIT=$SLURM_TIMELIMIT (each solve ~5+ min; allow ~20+ min for three cases) =="
fi

ALLOC="${SLURM_CPUS_ON_NODE:-}"
FULL="$FULL_NODE_RANKS"
if [[ -n "$ALLOC" ]]; then
  if [[ "$ALLOC" -lt "$FULL" ]]; then
    FULL="$ALLOC"
  fi
fi

if [[ -n "$RANK_LIST" ]]; then
  mapfile -t RANKS < <(echo "$RANK_LIST" | tr -s ' ' '\n' | grep -v '^$' | sort -n -u)
else
  mapfile -t RANKS < <(printf '%s\n' 1 8 "$FULL" | sort -n -u)
fi

for ranks in "${RANKS[@]}"; do
  if [[ -z "$ranks" || "$ranks" -lt 1 ]]; then
    continue
  fi
  if [[ -n "$ALLOC" && "$ranks" -gt "$ALLOC" ]]; then
    echo "skip ranks=$ranks (allocation has SLURM_CPUS_ON_NODE=$ALLOC)"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$STAMP" "mpi_per_core_skipped" 1 "$ranks" 1 1 "NA" "NA" "NA" "127" "skipped: ranks > SLURM_CPUS_ON_NODE" | tee -a "$OUT"
    continue
  fi
  run_ranks "$ranks"
done

echo "Done $(date -Is). Plot: python3 $REPO/scripts/plot_geom_mpi_per_core.py --input $OUT"
