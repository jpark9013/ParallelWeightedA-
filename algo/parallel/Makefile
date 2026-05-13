# Hybrid MPI + OpenMP hash-distributed weighted A* (superstep model).
# NERSC: use `module load cray-mpich` (or PrgEnv-gnu) so `mpicxx` is in PATH.

CXX := mpicxx
CXXFLAGS ?= -O3 -std=c++17 -fopenmp -DNDEBUG
# Optional: -march=znver3 on AMD Milan / Perlmutter CPU nodes
CPPFLAGS += -I../common
LDFLAGS += -fopenmp

TARGET_FAST := astar_mpi_fast
TARGET_ZOB := astar_mpi_zob

.PHONY: all clean
all: $(TARGET_FAST) $(TARGET_ZOB)

$(TARGET_FAST): main_mpi_fast.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main_mpi_fast.cpp $(LDFLAGS)

$(TARGET_ZOB): main_mpi_zob_pq.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main_mpi_zob_pq.cpp $(LDFLAGS)

clean:
	rm -f $(TARGET_FAST) $(TARGET_ZOB)
