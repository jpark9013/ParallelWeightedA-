#!/bin/bash
# Geom recommender medium n=1e9, w=1 — MPI strong-scaling sweep (1 rank : 1 core, OMP=1).
# Series A: 1 node, ranks 1,2,4,8,16,32,64,128
# Series B: 2 nodes, total ranks 2,4,8,16,32,64,128,256  (×2 relative to per-node pattern)
# Plot: x = cores per node (1-node: ranks; 2-node: ranks/2), log2; y = time (s), log; ideals T(1)/c, T(2)/c.
#
# Run inside a 2-node Slurm allocation with enough CPUs for the largest case, e.g.:
#   salloc -N2 --exclusive --ntasks=256 --cpus-per-task=1 --time=03:00:00 \
#     --qos=interactive --constraint=cpu --account=m4341 \
#     bash scripts/bench_geom_mpi_scaling_lines.sh
#
# Env: BINARY, SPEC, START, GOAL, W, RESET_BENCH_TSV, OUTDIR
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

OUTDIR="${OUTDIR:-$REPO/results/geom_mpi_scaling}"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/bench.tsv"
STAMP="$(date -Is)"

if [[ "$RESET_BENCH_TSV" == "1" ]] || [[ ! -s "$OUT" ]]; then
  echo -e "stamp\tseries\tnodes\tmpi_ranks\tomp_threads\tcpus_per_task\ttime_s\texpansions\tcost\trc\tline" >"$OUT"
fi

extract_line () {
  { printf '%s\n' "$1" | grep -E '^(cost=|no_path )' | tail -1; } || true
}

run_case () {
  local series="$1" nodes="$2" ranks="$3"
  export OMP_NUM_THREADS=1
  echo "=== $series  nodes=$nodes  ranks=$ranks  -c1 OMP=1 ==="
  set +e
  out="$(srun -N"$nodes" -n"$ranks" -c1 --cpu-bind=cores \
    "$BINARY" --mode geom --spec "$SPEC" --start "$START" --goal "$GOAL" -w "$W" 2>&1)"
  rc=$?
  set -e
  line="$(extract_line "$out")"
  time_s="$(printf '%s\n' "$line" | sed -n 's/.*time_s=\([0-9.eE+-]*\).*/\1/p')"
  exp="$(printf '%s\n' "$line" | sed -n 's/.*expansions=\([0-9]*\).*/\1/p')"
  cost="$(printf '%s\n' "$line" | sed -n 's/^cost=\([^ ]*\).*/\1/p')"
  [[ -n "$cost" ]] || cost="NA"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$STAMP" "$series" "$nodes" "$ranks" 1 1 "${time_s:-NA}" "${exp:-NA}" "${cost:-NA}" "$rc" "$line" | tee -a "$OUT"
}

echo "== bench_geom_mpi_scaling_lines STAMP=$STAMP OUT=$OUT =="
if [[ -n "${SLURM_JOB_NUM_NODES:-}" ]]; then
  echo "== SLURM_JOB_NUM_NODES=$SLURM_JOB_NUM_NODES (need >=2 for 2-node series) =="
fi

for R in 1 2 4 8 16 32 64 128; do
  run_case "1node" 1 "$R"
done

for R in 2 4 8 16 32 64 128 256; do
  run_case "2node" 2 "$R"
done

echo "Done $(date -Is). Plot:"
echo "  python3 $REPO/scripts/plot_geom_mpi_scaling_lines.py --input $OUT"
python3 "$REPO/scripts/plot_geom_mpi_scaling_lines.py" --input "$OUT" >>"$OUTDIR/plot_render.log" 2>&1 || true
python3 "$REPO/scripts/render_geom_mpi_scaling_svg.py" >>"$OUTDIR/plot_render.log" 2>&1 || true
