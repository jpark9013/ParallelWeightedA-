CSR n = 10^9 vs this benchmark
------------------------------
The CSR loader (algo/common/csr_graph.hpp) builds an adjacency list with one vector per vertex and
loads all edges into memory. A graph with ~10^9 vertices cannot be constructed this way on typical HPC nodes.

This sweep therefore uses the bundled planar test graph (~1000 vertices, planar_n1000.txt) as the CSR case.
For CSR mode the heuristic is h=0, so weighted A* uses f=g regardless of -w; w=1 vs w=5 should give the same
ordering (expect nearly identical time_s / expansions).

Grid case uses implicit grid_1e9_sparse.spec (10^9 vertices, 4-neighbour unit grid, no obstacles).
