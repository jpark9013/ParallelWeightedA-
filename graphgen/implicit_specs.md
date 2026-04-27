## Implicit graph specs (for A* benchmarks)

These are **constant-size** “graph definitions” for massive graphs where you do **not** store edges.
Your A* runner reads the spec and computes neighbors on-the-fly.

### 1) Grid with seeded obstacles (MovingAI-style idea)

Spec fields:
- `type=grid_obstacles`
- `w`, `h` (nodes \(n = w*h\))
- `seed` (uint64)
- `p_block` (0..1)
- `connectivity=4` or `8`
- `weight=1` (or `euclidean` for 8-neighbor)

Obstacle function (reproducible, no storage):
- `blocked(id) = (hash64(seed ^ id) < p_block * 2^64)`

Neighbors:
- computed from \((x,y)\) by bounds checks and `blocked()` checks

### 2) “Implicit geometric” kNN-by-hash (scales to 1e9+ nodes)

True random geometric graphs need a spatial index to be efficient at scale.
For huge-\(n\) A* stress tests, this pragmatic alternative preserves the key property you want:
**a consistent 2D embedding so Euclidean distance is an admissible heuristic**.

Spec fields:
- `type=geom_hash_knn`
- `n`
- `seed`
- `k` (fixed out-degree)
- `candidates` (how many candidate IDs sampled to pick k nearest; e.g. 64)
- `weight=euclidean`

Embedding:
- `point(i) = (u01(hash(seed ^ (i<<1))), u01(hash(seed ^ (i<<1) ^ 1)))` in \([0,1)^2\)

Neighbors:
- sample `candidates` node IDs deterministically from `hash(seed ^ i ^ j)`
- pick `k` closest by Euclidean distance in embedding

This gives you a **huge implicit graph** with **bounded degree** (memory-free adjacency).

### 3) Delaunay / road-like graphs

For “road-like planar” explicit benchmarks, prefer real road datasets (DIMACS / SNAP),
or generate modest-size planar-ish graphs (10^5–10^7) explicitly and stream to disk.
At 1e9 nodes, planar explicit storage is not realistic.

