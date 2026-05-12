#pragma once
#include <cmath>
#include <cstdint>
#include <functional>
#include <limits>
#include <optional>
#include <queue>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

namespace algo {

template <typename Graph>
struct AstarLazyResult {
  std::optional<double> cost;
  uint64_t expansions = 0;
};

// Weighted A* on implicit graph: open priority uses f = g + w*h(node).
template <typename Graph>
AstarLazyResult<Graph> astar_lazy(const Graph& g, uint64_t start, uint64_t goal, uint64_t max_expansions,
                                  double h_weight) {
  using OpenEl = std::tuple<double, double, uint64_t>;  // f, g, v
  std::priority_queue<OpenEl, std::vector<OpenEl>, std::greater<OpenEl>> open;
  std::unordered_map<uint64_t, double> gbest;
  gbest.reserve(4096);

  std::vector<std::pair<uint64_t, double>> nbr;
  nbr.reserve(1024);

  auto relax = [&](uint64_t v, double gv, double fv) {
    auto it = gbest.find(v);
    if (it != gbest.end() && !(gv < it->second)) return;
    gbest[v] = gv;
    open.emplace(fv, gv, v);
  };

  double hs = g.heuristic(start, goal);
  relax(start, 0.0, h_weight * hs);

  uint64_t expansions = 0;
  while (!open.empty() && expansions < max_expansions) {
    auto [f, gv, v] = open.top();
    open.pop();
    auto itg = gbest.find(v);
    if (itg == gbest.end() || gv > itg->second) continue;
    expansions++;
    if (v == goal) {
      return AstarLazyResult<Graph>{gv, expansions};
    }
    g.neighbors(v, nbr);
    for (auto [to, w] : nbr) {
      if (!(w >= 0.0) || std::isnan(w)) continue;
      double tg = gv + w;
      double tf = tg + h_weight * g.heuristic(to, goal);
      relax(to, tg, tf);
    }
  }

  return AstarLazyResult<Graph>{std::nullopt, expansions};
}

}  // namespace algo
