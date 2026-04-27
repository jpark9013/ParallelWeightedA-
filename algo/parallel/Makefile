# Hybrid MPI + OpenMP Hash-Distributed A* (superstep).
#
# Perlmutter (NERSC) reference:
# - CPU nodes: 2× AMD EPYC 7763 (Milan), 64 cores/socket → 128 physical cores/node, 4 NUMA domains/socket.
# - GPU nodes: 1× EPYC 7763 → 64 physical cores/node.
# - Slurm allocates logical CPUs (hardware threads); for compute-bound OpenMP, prefer 1 thread per physical core.
#   See: https://docs.nersc.gov/systems/perlmutter/architecture/
#   Affinity: https://docs.nersc.gov/jobs/affinity/
#
# Typical CPU-node hybrid on one node (128 physical cores):
#   export OMP_NUM_THREADS=16
#   srun --cpu-bind=cores -n 8 -c 16 ./astar_mpi ...
# (8 MPI ranks × 16 OpenMP threads = 128 cores)

# Do not use `?=` here: many environments export `CXX=g++`, which would defeat MPI wrappers.
CXX := mpicxx
CXXFLAGS ?= -O3 -std=c++17 -fopenmp -DNDEBUG
# Milan (EPYC 7763) uarch; use `module load craype-x86-milan` on Perlmutter if needed.
CXXFLAGS += -march=znver3
CPPFLAGS += -I../common
LDFLAGS += -fopenmp

TARGET := astar_mpi

.PHONY: all clean
all: $(TARGET)

$(TARGET): main_mpi.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main_mpi.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET)
