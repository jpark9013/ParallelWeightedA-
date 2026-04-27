#pragma once
#include <cmath>
#include <cstdint>
#include <limits>
#include <optional>
#include <queue>
#include <unordered_map>
#include <utility>
#include <vector>

namespace algo {

template <typename Graph>
struct AstarOutcome {
  std::optional<double> cost;
  uint64_t expansions = 0;
};

template <typename Graph>
AstarOutcome<Graph> astar_lazy(const Graph& graph, uint64_t start, uint64_t goal,
                               uint64_t max_expansions = UINT64_MAX) {
  struct Node {
    double f;
    double g;
    uint64_t v;
  };
  struct Cmp {
    bool operator()(const Node& a, const Node& b) const {
      if (a.f != b.f) return a.f > b.f;
      if (a.g != b.g) return a.g > b.g;
      return a.v > b.v;
    }
  };

  std::priority_queue<Node, std::vector<Node>, Cmp> open;
  std::unordered_map<uint64_t, double> gbest;
  gbest.reserve(4096);

  std::vector<std::pair<uint64_t, double>> nbr;
  nbr.reserve(256);

  auto h = [&](uint64_t x) { return graph.heuristic(x, goal); };

  AstarOutcome<Graph> out;
  if (start == goal) {
    out.cost = 0.0;
    return out;
  }

  gbest[start] = 0.0;
  open.push({h(start), 0.0, start});

  while (!open.empty() && out.expansions < max_expansions) {
    Node cur = open.top();
    open.pop();
    auto itg = gbest.find(cur.v);
    if (itg == gbest.end() || cur.g > itg->second) continue;
    out.expansions++;
    if (cur.v == goal) {
      out.cost = cur.g;
      return out;
    }
    graph.neighbors(cur.v, nbr);
    for (auto [to, w] : nbr) {
      if (!(w >= 0.0) || std::isnan(w)) continue;
      double tg = cur.g + w;
      auto it = gbest.find(to);
      if (it != gbest.end() && !(tg < it->second)) continue;
      gbest[to] = tg;
      double f = tg + h(to);
      open.push({f, tg, to});
    }
  }
  out.cost = std::nullopt;
  return out;
}

}  // namespace algo
