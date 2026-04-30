#!/bin/bash
# Rerun sparse grid at 2 MPI ranks, w=1, threads 1 and 8 (needs long walltime — use batch).
#
#   cd $REPO && sbatch scripts/sbatch_rerun_sparse_grid_w1_node2.sh
#
#SBATCH --job-name=sparse_w1_n2
#SBATCH --qos=regular_0
#SBATCH --nodes=2
#SBATCH --ntasks=2
#SBATCH --cpus-per-task=128
#SBATCH --exclusive
#SBATCH --time=12:00:00
#SBATCH --constraint=cpu
#SBATCH --account=m4341
#SBATCH --output=results/combined_w_thr_nodes/sbatch_sparse_w1_node2_%j.out
#SBATCH --error=results/combined_w_thr_nodes/sbatch_sparse_w1_node2_%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR:-.}"
export GPU_SUPPORT_ENABLED=0

MPI="./algo/parallel/astar_mpi"
SPEC="bench_specs/grid_1e9_sparse.spec"
OUT="results/combined_w_thr_nodes/grid_geom_w_thr_nodes.tsv"
TO="${SPARSE_W1_TIMEOUT:-43200}"

mkdir -p results/combined_w_thr_nodes

extract_field() {
  local key="$1"
  sed -n "s/.*${key}=\([^ ]*\).*/\1/p" | head -1
}

run_case() {
  local t=$1 c=$2
  export OMP_NUM_THREADS="$t"
  set +e
  local out
  out="$(timeout "$TO" srun -N2 -n2 -c"$c" --cpu-bind=cores \
    "$MPI" --mode grid --spec "$SPEC" --start 0 --goal 999999999 -w 1 2>&1)"
  rc=$?
  set -e
  time_s="NA"
  exp="NA"
  if [[ "$rc" == "0" || "$rc" == "1" ]]; then
    line="$(printf '%s\n' "$out" | grep -E '^(cost=|no_path )' | tail -1)"
    time_s="$(printf '%s\n' "$line" | extract_field time_s)"
    exp="$(printf '%s\n' "$line" | extract_field expansions)"
    [[ -n "$time_s" ]] || time_s="NA"
    [[ -n "$exp" ]] || exp="NA"
  fi
  printf '%s\n' "$out"
  echo "RESULT threads=$t cpus=$c rc=$rc time_s=$time_s expansions=$exp"
}

echo "=== $(date -Is) threads=1 cpus=1 timeout=${TO}s ==="
run_case 1 1

echo "=== $(date -Is) threads=8 cpus=8 timeout=${TO}s ==="
run_case 8 8

# Parse RESULT lines from this job's stdout file (SBATCH --output)
SLURM_OUT="${SLURM_SUBMIT_DIR:-.}/results/combined_w_thr_nodes/sbatch_sparse_w1_node2_${SLURM_JOB_ID}.out"
python3 "${SLURM_SUBMIT_DIR:-.}/scripts/patch_sparse_grid_from_slurm_out.py" "$SLURM_OUT" "$OUT"

echo "Done $(date -Is)"
