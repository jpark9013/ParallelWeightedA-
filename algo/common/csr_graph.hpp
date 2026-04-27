#pragma once
#include <algorithm>
#include <cstdio>
#include <cstdint>
#include <fstream>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace algo {

struct CsrGraphU64 {
  uint64_t n = 0;
  std::vector<uint64_t> row_ptr;
  std::vector<uint64_t> col;
  std::vector<double> w;

  static CsrGraphU64 from_edge_list_undirected_unweighted(const std::string& path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open edge list: " + path);

    std::vector<std::pair<uint64_t, uint64_t>> edges;
    edges.reserve(1024);
    uint64_t max_id = 0;
    std::string line;
    while (std::getline(in, line)) {
      if (line.empty()) continue;
      unsigned long long uu = 0, vv = 0;
      if (std::sscanf(line.c_str(), "%llu %llu", &uu, &vv) != 2) {
        throw std::runtime_error("bad edge line (expected u v): " + line);
      }
      uint64_t u = static_cast<uint64_t>(uu);
      uint64_t v = static_cast<uint64_t>(vv);
      if (u == v) continue;
      if (u > v) std::swap(u, v);
      edges.emplace_back(u, v);
      max_id = std::max(max_id, std::max(u, v));
    }
    if (edges.empty()) throw std::runtime_error("no edges read");

    std::sort(edges.begin(), edges.end());
    edges.erase(std::unique(edges.begin(), edges.end()), edges.end());

    uint64_t num_nodes = max_id + 1;
    std::vector<std::vector<uint64_t>> adj(num_nodes);
    for (auto [u, v] : edges) {
      adj[u].push_back(v);
      adj[v].push_back(u);
    }
    for (auto& row : adj) {
      std::sort(row.begin(), row.end());
      row.erase(std::unique(row.begin(), row.end()), row.end());
    }

    CsrGraphU64 g;
    g.n = num_nodes;
    g.row_ptr.resize(num_nodes + 1, 0);
    for (uint64_t i = 0; i < num_nodes; i++) g.row_ptr[(size_t)i + 1] = g.row_ptr[(size_t)i] + (uint64_t)adj[(size_t)i].size();
    g.col.resize((size_t)g.row_ptr[num_nodes]);
    g.w.assign(g.col.size(), 1.0);
    for (uint64_t i = 0; i < num_nodes; i++) {
      uint64_t base = g.row_ptr[(size_t)i];
      for (size_t j = 0; j < adj[(size_t)i].size(); j++) {
        g.col[(size_t)(base + j)] = adj[(size_t)i][j];
      }
    }
    return g;
  }

  void neighbors(uint64_t u, std::vector<std::pair<uint64_t, double>>& out) const {
    out.clear();
    if (u >= n) return;
    uint64_t lo = row_ptr[(size_t)u];
    uint64_t hi = row_ptr[(size_t)u + 1];
    out.reserve((size_t)(hi - lo));
    for (uint64_t p = lo; p < hi; p++) out.emplace_back(col[(size_t)p], w[(size_t)p]);
  }

  double heuristic(uint64_t /*a*/, uint64_t /*b*/) const {
    // No geometry: use zero heuristic => Dijkstra / uniform-cost search.
    return 0.0;
  }
};

}  // namespace algo
