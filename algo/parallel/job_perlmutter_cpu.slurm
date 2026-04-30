#!/bin/bash
#SBATCH -J astar_mpi
#SBATCH -C cpu
#SBATCH -q regular
#SBATCH -N 1
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=16
#SBATCH --cpu-bind=cores
#SBATCH -t 00:15:00
#SBATCH -o astar-%j.out
#SBATCH -e astar-%j.err
##SBATCH -A mXXXX                 # <-- set your NERSC project

# Perlmutter CPU node: 2× AMD EPYC 7763 → 128 physical cores/node (256 logical CPUs with SMT).
# Keep cpus-per-task equal to OMP_NUM_THREADS for hybrid MPI+OpenMP jobs.
# https://docs.nersc.gov/systems/perlmutter/architecture/

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"

export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OMP_PLACES=cores
export OMP_PROC_BIND=spread

# Optional: enable MPI+threads (Cray MPICH)
export MPICH_GPU_SUPPORT_DISABLED=1

BIN="${BIN:-./astar_mpi}"

# Example: explicit edge list from graphgen (run from algo/parallel or set EDGES absolute)
EDGES="${EDGES:-../../graphgen/data/sample_planar50.txt}"

srun "${BIN}" --mode csr --edges "${EDGES}" --start 0 --goal 10 --budget 128
