# Data inventory for one-page scaling figures

Paths are relative to repo root.

## `results/combined_w_thr_nodes/nodes_1_2_4_w1_grid_recommender.tsv`

| graph | nodes | w | threads | time_s | notes |
|-------|-------|---|-----------|--------|-------|
| recommender_medium | 1,2,4 | 1 | 1 | OK | strong scaling Panel 1 |
| recommender_medium | 1,2,4 | 1 | 8 | OK | Panel 3 thread sweep |
| grid_1e9_sparse | 1,4 | 1 | 1,8 | OK | Panel 4 sparse bar |
| grid_1e9_sparse | 2 | 1 | * | NA exit 143 | omit 2-node sparse w=1 |

## `results/geom_w_compare/w1_w5_nodes.tsv`

| graph | nodes | w | threads | time_s |
|-------|-------|---|-----------|--------|
| recommender_medium | 1,2,4 | 1,5 | 1 | all OK | Panel 2 overlay |
| social_embedding_dense | 1,2,4 | 1,5 | 1 | all OK | optional narrative |

## `results/sweep_w_threads/sweep.tsv`

| graph key | nodes | w | threads | time_s | notes |
|-----------|-------|---|-----------|--------|-------|
| n1e9_sparse | 1,2,4 | 3,5 | 1,2,32,128 | OK | Panel 5 sparse |
| n1e9_sparse | * | 1 | * | mostly NA | do not plot |
| n1e9_dense | 1 | 1,3,5 | 1,2,32,128 | OK (w=1 dense 1-node) | Panel 5 dense |
| n1e9_dense | 2,4 | 1 | * | NA exit 143 | use w>=3 for multi-node dense in other plots |

## `results/combined_w_thr_nodes/geom_1e8_compute_heavy_parallel_neighbors_omp1_8_64.tsv`

| threads | time_s | notes |
|---------|--------|-------|
| 1,8,64 | OK | Panel 4 compute-heavy (1 rank, 1e8 parallel geom spec) |

## `paper/data/geom_medium_2n_load_balance.tsv` (curated)

Two-node, 1 thread/rank, geom recommender medium w=1: baseline MPI vs donation steal (same harness as main binary comparison).
