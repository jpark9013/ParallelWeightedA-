#pragma once
// Reusable OpenMP staging for distributed A* neighbor expansion.
// Avoids allocating nt × nranks nested vectors on every high-degree expand_one().
#include <vector>

template <typename RelaxMsg>
struct MpiExpandTls {
  std::vector<std::vector<std::vector<RelaxMsg>>> data;
  int cached_nt = -1;
  int cached_nranks = -1;

  void ensure(int nt, int nranks) {
    if (nt <= 0) nt = 1;
    if (nranks <= 0) nranks = 1;
    if (nt == cached_nt && nranks == cached_nranks && !data.empty()) return;
    data.assign(static_cast<size_t>(nt), {});
    for (auto& row : data) row.assign(static_cast<size_t>(nranks), {});
    cached_nt = nt;
    cached_nranks = nranks;
  }

  void clear_all(int nt, int nranks) {
    for (int t = 0; t < nt; t++) {
      for (int o = 0; o < nranks; o++) data[static_cast<size_t>(t)][static_cast<size_t>(o)].clear();
    }
  }

  std::vector<std::vector<RelaxMsg>>& thread_buckets(int tid) { return data[static_cast<size_t>(tid)]; }
};
