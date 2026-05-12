# `astar_mpi_fast` optimizations (geometric weighted A* unchanged)

The search is still **implicit geom kNN weighted A\*** with the same `f = g + w·h` rule, vertex ownership, supersteps, and `MPI_Alltoallv` message exchange as the classic driver.

These changes only affect **data structures and scheduling**:

1. **Reused TLS staging (`mpi_expand_tls.hpp`)**  
   Parallel neighbor relaxation no longer allocates `nt × nranks` nested `std::vector`s on every high-degree expansion.

2. **Sharded inbox (default `--inbox sharded`)**  
   Owned inbound relaxations are bucketed by `v % nt`, sorted in parallel per bucket, then merged so we avoid one OpenMP `critical` per message when the inbox is large.

3. **4-ary heap (default `--heap 4ary`)**  
   Cheaper `push`/`pop` than `std::priority_queue` for large OPEN sets.

4. **Lower OpenMP neighbor threshold** (`deg >= 16` with `OMP_NUM_THREADS > 1`)  
   For `k=64` geom graphs, neighbor work almost always uses the thread pool instead of paying single-thread neighbor scoring then merging rarely.

5. **Larger default superstep budget (256)**  
   More expansions per superstep ⇒ fewer global synchronizations (`MPI_Alltoallv` + reductions) for the same total work.

6. **Larger hash / mailbox reserves**  
   Fewer reallocations on `gbest` and per-rank outbound buffers during deep search.

Tune with `--budget`, `--heap`, `--inbox`, and `OMP_NUM_THREADS` without changing optimality of the shortest path under the distributed tie-breaking model.
