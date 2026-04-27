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

struct GeomImplicit {
  uint64_t n = 0;
  uint64_t seed = 0;
  uint64_t k = 0;
  uint64_t candidates = 64;

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

  double heuristic(uint64_t a, uint64_t b) const {
    auto [ax, ay] = point(seed, a);
    auto [bx, by] = point(seed, b);
    double dx = ax - bx;
    double dy = ay - by;
    return std::sqrt(dx * dx + dy * dy);
  }

  void neighbors(uint64_t u, std::vector<std::pair<uint64_t, double>>& out) const {
    out.clear();
    if (u >= n) return;
    auto [ux, uy] = point(seed, u);

    struct Cand {
      uint64_t v;
      double d2;
    };
    std::vector<Cand> cands;
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
                     [](const Cand& a, const Cand& b) { return a.d2 < b.d2; });
    cands.resize((size_t)kk);

    std::sort(cands.begin(), cands.end(), [](const Cand& a, const Cand& b) {
      if (a.v != b.v) return a.v < b.v;
      return a.d2 < b.d2;
    });
    cands.erase(std::unique(cands.begin(), cands.end(),
                            [](const Cand& a, const Cand& b) { return a.v == b.v; }),
                cands.end());

    for (const auto& c : cands) {
      auto [vx, vy] = point(seed, c.v);
      double dx = ux - vx;
      double dy = uy - vy;
      double w = std::sqrt(dx * dx + dy * dy);
      if (w > 0.0) out.emplace_back(c.v, w);
    }
  }
};

}  // namespace algo
