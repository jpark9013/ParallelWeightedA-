#pragma once
#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

#include "spec_parse.hpp"
#include "splitmix.hpp"

namespace algo {

struct GridImplicit {
  uint64_t w = 0;
  uint64_t h = 0;
  uint64_t seed = 0;
  double p_block = 0.0;
  int connectivity = 4;  // 4 or 8

  static GridImplicit from_spec_file(const std::string& path) {
    auto kv = read_key_value_file(path);
    if (kv["type"] != "grid_obstacles") throw std::runtime_error("not a grid_obstacles spec");
    GridImplicit g;
    g.w = parse_u64(kv.at("w"), "w");
    g.h = parse_u64(kv.at("h"), "h");
    g.seed = parse_u64(kv.at("seed"), "seed");
    g.p_block = parse_double(kv.at("p_block"), "p_block");
    g.connectivity = parse_int(kv.at("connectivity"), "connectivity");
    if (!(g.connectivity == 4 || g.connectivity == 8)) throw std::runtime_error("connectivity must be 4 or 8");
    if (g.w == 0 || g.h == 0) throw std::runtime_error("invalid w/h");
    return g;
  }

  uint64_t num_nodes() const { return w * h; }

  std::pair<uint64_t, uint64_t> xy(uint64_t id) const {
    uint64_t x = id % w;
    uint64_t y = id / w;
    return {x, y};
  }

  bool blocked(uint64_t id) const { return blocked_grid(seed, id, p_block); }

  double heuristic(uint64_t a, uint64_t b) const {
    auto [ax, ay] = xy(a);
    auto [bx, by] = xy(b);
    int64_t dx = (int64_t)ax - (int64_t)bx;
    int64_t dy = (int64_t)ay - (int64_t)by;
    dx = std::llabs(dx);
    dy = std::llabs(dy);
    if (connectivity == 4) {
      return static_cast<double>(dx + dy);
    }
    // 8-neighbor: octile distance (sqrt(2) diagonal steps + axis remainder)
    int64_t dmin = std::min(dx, dy);
    int64_t dmax = std::max(dx, dy);
    int64_t diag = dmin;
    int64_t straight = dmax - dmin;
    const double SQ2 = 1.4142135623730950488;
    return diag * SQ2 + straight;
  }

  void neighbors(uint64_t u, std::vector<std::pair<uint64_t, double>>& out) const {
    out.clear();
    if (blocked(u)) return;
    auto [x, y] = xy(u);

    const int dx4[4] = {1, -1, 0, 0};
    const int dy4[4] = {0, 0, 1, -1};
    for (int k = 0; k < 4; k++) {
      int nx = (int)x + dx4[k];
      int ny = (int)y + dy4[k];
      if (nx < 0 || ny < 0 || nx >= (int)w || ny >= (int)h) continue;
      uint64_t v = (uint64_t)ny * w + (uint64_t)nx;
      if (blocked(v)) continue;
      out.emplace_back(v, 1.0);
    }
    if (connectivity == 8) {
      const int dx4d[4] = {1, 1, -1, -1};
      const int dy4d[4] = {1, -1, 1, -1};
      for (int k = 0; k < 4; k++) {
        int nx = (int)x + dx4d[k];
        int ny = (int)y + dy4d[k];
        if (nx < 0 || ny < 0 || nx >= (int)w || ny >= (int)h) continue;
        uint64_t v = (uint64_t)ny * w + (uint64_t)nx;
        if (blocked(v)) continue;
        out.emplace_back(v, std::sqrt(2.0));
      }
    }
  }
};

}  // namespace algo
