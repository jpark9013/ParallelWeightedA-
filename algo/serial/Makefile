# Serial A* (no OpenMP; no MPI).
# Perlmutter CPU nodes: 2× AMD EPYC 7763 @ 64 cores/socket → 128 physical cores/node (256 hardware threads with SMT).
# GPU nodes: 1× EPYC 7763 → 64 physical cores/node (128 hardware threads with SMT).
# See: https://docs.nersc.gov/systems/perlmutter/architecture/

CXX ?= g++
CXXFLAGS ?= -O3 -std=c++17 -march=znver3 -DNDEBUG
CPPFLAGS += -I../common

TARGET := astar_serial

.PHONY: all clean
all: $(TARGET)

$(TARGET): main.cpp
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -o $@ main.cpp

clean:
	rm -f $(TARGET)
