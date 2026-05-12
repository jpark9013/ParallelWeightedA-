# Hybrid MPI + OpenMP hash-distributed weighted A* (superstep model).
# NERSC: use `module load cray-mpich` (or PrgEnv-gnu) so `mpicxx` is in PATH.

CXX := mpicxx
CXXFLAGS ?= -O3 -std=c++17 -fopenmp -DNDEBUG
# Optional: -march=znver3 on AMD Milan / Perlmutter CPU nodes
CPPFLAGS += -I../common
LDFLAGS += -fopenmp

TARGET_FAST := astar_mpi_fast

.PHONY: all clean
all: $(TARGET_FAST)

$(TARGET_FAST): main_mpi_fast.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main_mpi_fast.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET_FAST)
