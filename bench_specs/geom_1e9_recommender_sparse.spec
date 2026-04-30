# Real-world analogy: embedding similarity graph (recommender / IR candidate graph).
# Sparse-ish kNN: each item connects to ~24 most similar items among 256 sampled candidates.
# Vertices: 1e9 items/documents; weights: Euclidean distance in embedding space (proxy).
type=geom_hash_knn
n=1000000000
seed=4242
k=24
candidates=256
