#!/bin/bash
# Geom recommender medium n=1e9: one MPI rank per logical core (OMP_NUM_THREADS=1).
# Compares single-node runs with 1, 8, and "full node" MPI ranks (-c 1, --cpu-bind=cores each).
#
# Requires a Slurm allocation with enough CPUs for the largest case (exclusive node recommended).
# Example (Perlmutter CPU):
#   salloc -N1 --exclusive --cpus-per-task=1 --ntasks=128 --time=02:00:00 \
#     --qos=regular --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_mpi_one_rank_per_core.sh
#
# With fewer CPUs allocated, set SLURM_CPUS_ON_NODE or the script uses 128 for the third case
# and srun will fail if the allocation is too small — use a full-node exclusive alloc.
#
# Env:
#   BIN=path/to/astar_mpi_fast   (default: algo/parallel/astar_mpi_fast)
#   SPEC, START, GOAL, W        (same defaults as other geom benches)
#   RESET_BENCH_TSV=0           append to existing TSV instead of overwriting
#   RANK_LIST="1 8 128"         override which MPI rank counts to try (must fit allocation)
set -euo pipefail

REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO"
make -C algo/parallel -s astar_mpi_fast

BIN="${BIN:-$REPO/algo/parallel/astar_mpi_fast}"
SPEC="${SPEC:-bench_specs/geom_1e9_recommender_medium.spec}"
START="${START:-0}"
GOAL="${GOAL:-999999999}"
W="${W:-1}"
RESET_BENCH_TSV="${RESET_BENCH_TSV:-1}"

OUTDIR="${OUTDIR:-$REPO/results/geom_mpi_one_rank_per_core}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/bench.tsv"
STAMP="$(date -Is)"

if [[ -n "${RANK_LIST:-}" ]]; then
  read -r -a RANKS <<<"$RANK_LIST"
else
  if [[ -n "${SLURM_CPUS_ON_NODE:-}" ]]; then
    NC="$SLURM_CPUS_ON_NODE"
  else
    NC=128
    echo "== note: SLURM_CPUS_ON_NODE unset; using NC=$NC for max-rank case (set RANK_LIST to override) ==" >&2
  fi
  RANKS=(1 8 "$NC")
fi

# Deduplicate (e.g. NC==8 -> only 1 and 8)
declare -A seen=()
UNIQUE_RANKS=()
for r in "${RANKS[@]}"; do
  [[ "$r" =~ ^[0-9]+$ ]] || { echo "bad rank count: $r" >&2; exit 2; }
  if [[ -z "${seen[$r]:-}" ]]; then
    seen[$r]=1
    UNIQUE_RANKS+=("$r")
  fi
done

if [[ "$RESET_BENCH_TSV" == "1" ]] || [[ ! -s "$OUT" ]]; then
  echo -e "stamp\tvariant\tnodes\tmpi_ranks\tomp_threads\tcpus_per_task\ttime_s\texpansions\tcost\trc\tline" >"$OUT"
fi

extract_line () {
  printf '%s\n' "$1" | grep -E '^(cost=|no_path )' | tail -1
}

echo "== bench_geom_mpi_one_rank_per_core STAMP=$STAMP OUT=$OUT BIN=$BIN =="
echo "== ranks to run: ${UNIQUE_RANKS[*]} (1 rank : 1 core, OMP_NUM_THREADS=1, -c1 --cpu-bind=cores) =="
if [[ -n "${SLURM_JOB_ID:-}" ]]; then
  echo "== SLURM_JOB_ID=$SLURM_JOB_ID SLURM_CPUS_ON_NODE=${SLURM_CPUS_ON_NODE:-unset} SLURM_NNODES=${SLURM_NNODES:-unset} =="
fi

export OMP_NUM_THREADS=1
export OMP_PROC_BIND="${OMP_PROC_BIND:-spread}"
export OMP_PLACES="${OMP_PLACES:-cores}"

for ranks in "${UNIQUE_RANKS[@]}"; do
  echo "--- 1 node, $ranks MPI ranks × 1 core (OMP=1) ---"
  set +e
  out="$(srun -N1 -n"$ranks" -c1 --cpu-bind=cores \
    "$BIN" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_line "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  [[ -n "$cost" ]] || cost="NA"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$STAMP" "fast_1rank_1core" 1 "$ranks" 1 1 "${time_s:-NA}" "${exp:-NA}" "${cost:-NA}" "$rc" "$line" | tee -a "$OUT"
  if [[ "$rc" != 0 ]]; then
    echo "== warning: rc=$rc for ranks=$ranks (allocation may be smaller than $ranks CPUs) ==" >&2
    printf '%s\n' "$out" | tail -20 >&2
  fi
done

echo "Done $(date -Is). TSV: $OUT"
