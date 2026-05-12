#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

#include "spec_parse.hpp"
#include "splitmix.hpp"

namespace algo {

// Implicit geometric kNN graph: sample `candidates` random nodes, keep k nearest by squared distance,
// undirected-style unique neighbors, edge weight = Euclidean distance in [0,1]^2 embedding.
struct GeomImplicit {
  uint64_t n = 0;
  uint64_t seed = 0;
  uint64_t k = 0;
  uint64_t candidates = 64;

  struct NeighborCand {
    uint64_t v;
    double d2;
  };
  mutable std::vector<NeighborCand> neigh_work_;

  static GeomImplicit from_spec_file(const std::string& path) {
    auto kv = read_key_value_file(path);
    if (kv["type"] != "geom_hash_knn") throw std::runtime_error("not a geom_hash_knn spec");
    GeomImplicit g;
    g.n = parse_u64(kv.at("n"), "n");
    g.seed = parse_u64(kv.at("seed"), "seed");
    g.k = parse_u64(kv.at("k"), "k");
    g.candidates = parse_u64(kv.at("candidates"), "candidates");
    if (g.n == 0) throw std::runtime_error("n must be > 0");
    if (g.k == 0) throw std::runtime_error("k must be > 0");
    if (g.candidates < g.k) throw std::runtime_error("candidates must be >= k");
    return g;
  }

  uint64_t num_nodes() const { return n; }

  static std::pair<double, double> point(uint64_t seed, uint64_t i) {
    uint64_t a = splitmix64(seed ^ (i * 2ULL));
    uint64_t b = splitmix64(seed ^ (i * 2ULL + 1ULL));
    return {u01_from_u64(a), u01_from_u64(b)};
  }

  mutable uint64_t heur_b_node_ = UINT64_MAX;
  mutable double heur_bx_ = 0.0;
  mutable double heur_by_ = 0.0;

  double heuristic(uint64_t a, uint64_t b) const {
    if (heur_b_node_ != b) {
      auto pb = point(seed, b);
      heur_bx_ = pb.first;
      heur_by_ = pb.second;
      heur_b_node_ = b;
    }
    auto [ax, ay] = point(seed, a);
    double dx = ax - heur_bx_;
    double dy = ay - heur_by_;
    return std::sqrt(dx * dx + dy * dy);
  }

  void neighbors(uint64_t u, std::vector<std::pair<uint64_t, double>>& out) const {
    out.clear();
    if (u >= n) return;
    auto [ux, uy] = point(seed, u);

    auto& cands = neigh_work_;
    cands.clear();
    cands.reserve((size_t)candidates);

    for (uint64_t j = 0; j < candidates; j++) {
      uint64_t cand = splitmix64(seed ^ u ^ (j * 0x9E3779B97F4A7C15ULL)) % n;
      if (cand == u) continue;
      auto [vx, vy] = point(seed, cand);
      double dx = ux - vx;
      double dy = uy - vy;
      cands.push_back({cand, dx * dx + dy * dy});
    }
    if (cands.empty()) return;

    uint64_t kk = k;
    if (kk > cands.size()) kk = cands.size();
    std::nth_element(cands.begin(), cands.begin() + (ptrdiff_t)kk, cands.end(),
                     [](const NeighborCand& a, const NeighborCand& b) { return a.d2 < b.d2; });
    cands.resize((size_t)kk);

    std::sort(cands.begin(), cands.end(), [](const NeighborCand& a, const NeighborCand& b) {
      if (a.v != b.v) return a.v < b.v;
      return a.d2 < b.d2;
    });
    cands.erase(std::unique(cands.begin(), cands.end(),
                            [](const NeighborCand& a, const NeighborCand& b) { return a.v == b.v; }),
                cands.end());

    for (const auto& c : cands) {
      double w = std::sqrt(c.d2);
      if (w > 0.0) out.emplace_back(c.v, w);
    }
  }
};

}  // namespace algo
