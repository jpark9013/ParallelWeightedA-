#!/bin/bash
#SBATCH -J astar_test
#SBATCH -C cpu
#SBATCH -q regular
#SBATCH -N 1
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=16
#SBATCH -t 00:05:00
#SBATCH -A m4341
#SBATCH -o astar-test-%j.out
#SBATCH -e astar-test-%j.err

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}/../.."

echo "pwd=$(pwd)"
echo "nodes=${SLURM_JOB_NUM_NODES} ntasks=${SLURM_NTASKS} cpus_per_task=${SLURM_CPUS_PER_TASK}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PLACES=cores
export OMP_PROC_BIND=spread

echo "=== build serial ==="
make -C algo/serial clean all

echo "=== build mpi ==="
make -C algo/parallel clean all

echo "=== serial sanity (CSR grid/geom/planar) ==="
./algo/serial/astar_serial --mode csr --edges graphgen/data/tests/grid_30x30_p015.txt --start 0 --goal 899 || true
./algo/serial/astar_serial --mode csr --edges graphgen/data/tests/geom_knn_n1000_k8.txt --start 0 --goal 999
./algo/serial/astar_serial --mode csr --edges graphgen/data/tests/planar_n1000.txt --start 0 --goal 999

echo "=== mpi sanity (1 rank) ==="
srun -N 1 -n 1 -c "${SLURM_CPUS_PER_TASK}" --cpu-bind=cores \
  ./algo/parallel/astar_mpi --mode csr --edges graphgen/data/tests/planar_n1000.txt --start 0 --goal 999

echo "=== mpi 1 node (8 ranks total) ==="
srun -N 1 --ntasks-per-node=8 -c "${SLURM_CPUS_PER_TASK}" --cpu-bind=cores \
  ./algo/parallel/astar_mpi --mode csr --edges graphgen/data/tests/planar_n1000.txt --start 0 --goal 999

echo "=== mpi 1 node (grid) ==="
srun -N 1 --ntasks-per-node=8 -c "${SLURM_CPUS_PER_TASK}" --cpu-bind=cores \
  ./algo/parallel/astar_mpi --mode csr --edges graphgen/data/tests/grid_30x30_p015.txt --start 0 --goal 899 || true

echo "done"

