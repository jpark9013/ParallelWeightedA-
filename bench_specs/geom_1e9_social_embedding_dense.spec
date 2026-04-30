# Real-world analogy: social network *embedding* similarity graph (not explicit friend edges).
# Dense kNN: each user links to ~128 nearest neighbors among 1024 sampled candidates.
# This mimics dense affinity graphs used for clustering/community detection on embeddings.
type=geom_hash_knn
n=1000000000
seed=4242
k=128
candidates=1024
