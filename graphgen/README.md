## graphgen

Generated edge lists, specs, and samples live under **`data/`** (create it if missing).

Fast large-graph generator (C++) that writes edges as:

```
u v
u v
...
```

Nodes are labeled `0..n-1`.

### Build

```bash
g++ -O3 -march=native -std=c++17 -pipe -o graphgen graphgen.cpp
g++ -O3 -march=native -std=c++17 -pipe -o specgen specgen.cpp
g++ -O3 -march=native -std=c++17 -pipe -o samplegen samplegen.cpp
```

### Usage

#### Explicit edge list (streams to disk)

```bash
./graphgen --n 100000 --m 1000000 --out data/g_n1e5_m1e6.txt
```

Options:
- `--n <int>`: number of nodes
- `--m <int>`: number of edges
- `--out <path>`: output file path
- `--directed`: generate directed edges (default: undirected)
- `--allow-self-loops`: allow edges `u==v` (default: no)
- `--unique`: enforce no duplicate edges (can be slower / memory heavier)
- `--seed <uint64>`: RNG seed (default: random_device)
- `--header`: write first line as `n m` (default: no header)

Notes:
- Undirected mode outputs exactly `m` lines, each an unordered pair normalized as `min(u,v) max(u,v)`.
- `--unique` stores a hash set of edges (memory cost roughly proportional to `m`).

#### Implicit graph specs (for 1e9–1e10+ nodes)

These output a **tiny spec file** that defines a huge graph; your A* runner should compute neighbors on-the-fly.

- Grid with seeded obstacles:

```bash
./specgen grid --w 30000 --h 30000 --p-block 0.25 --seed 1 --connectivity 4 --out data/grid_30000x30000.spec
```

- Hash-embedded geometric kNN (bounded degree, admissible Euclidean heuristic):

```bash
./specgen geom --n 1000000000 --k 16 --candidates 64 --seed 1 --out data/geom_knn_1e9.spec
```

See `implicit_specs.md` for the intended semantics.

#### 50-node explicit samples (one per graph family)

```bash
./samplegen grid50  --w 10 --h 5 --p-block 0.25 --seed 1 --conn 4 --out data/sample_grid50.txt
./samplegen geom50  --seed 1 --k 6 --out data/sample_geom50.txt
./samplegen planar50 --seed 1 --out data/sample_planar50.txt
```

