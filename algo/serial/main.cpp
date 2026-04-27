#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdexcept>
#include <string>

#include "astar_lazy.hpp"
#include "csr_graph.hpp"
#include "geom_implicit.hpp"
#include "grid_implicit.hpp"

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "Usage:\n"
               "  %s --mode csr   --edges PATH --start U --goal V\n"
               "  %s --mode grid  --spec  PATH --start U --goal V\n"
               "  %s --mode geom  --spec  PATH --start U --goal V\n",
               argv0, argv0, argv0);
}

static uint64_t parse_u64_arg(const char* s) {
  char* end = nullptr;
  unsigned long long v = std::strtoull(s, &end, 10);
  if (!end || *end) throw std::runtime_error(std::string("bad uint64: ") + s);
  return static_cast<uint64_t>(v);
}

int main(int argc, char** argv) {
  try {
    std::string mode;
    std::string path;
    uint64_t start = 0, goal = 0;
    for (int i = 1; i < argc; i++) {
      const char* a = argv[i];
      if (!std::strcmp(a, "--mode")) mode = argv[++i];
      else if (!std::strcmp(a, "--edges") || !std::strcmp(a, "--spec")) path = argv[++i];
      else if (!std::strcmp(a, "--start")) start = parse_u64_arg(argv[++i]);
      else if (!std::strcmp(a, "--goal")) goal = parse_u64_arg(argv[++i]);
      else if (!std::strcmp(a, "-h") || !std::strcmp(a, "--help")) {
        usage(argv[0]);
        return 0;
      } else {
        throw std::runtime_error(std::string("unknown arg: ") + a);
      }
    }
    if (mode.empty() || path.empty()) {
      usage(argv[0]);
      return 2;
    }

    auto t0 = std::chrono::steady_clock::now();

    if (mode == "csr") {
      algo::CsrGraphU64 g = algo::CsrGraphU64::from_edge_list_undirected_unweighted(path);
      auto res = algo::astar_lazy(g, start, goal);
      auto t1 = std::chrono::steady_clock::now();
      double sec = std::chrono::duration<double>(t1 - t0).count();
      if (!res.cost.has_value()) {
        std::printf("no_path expansions=%llu time_s=%.6f\n", (unsigned long long)res.expansions, sec);
        return 1;
      }
      std::printf("cost=%.12g expansions=%llu time_s=%.6f nodes=%llu edges=%zu\n", *res.cost,
                  (unsigned long long)res.expansions, sec, (unsigned long long)g.n, g.col.size());
      return 0;
    }

    if (mode == "grid") {
      algo::GridImplicit g = algo::GridImplicit::from_spec_file(path);
      if (start >= g.num_nodes() || goal >= g.num_nodes()) throw std::runtime_error("start/goal out of range");
      if (g.blocked(start) || g.blocked(goal)) throw std::runtime_error("start or goal is blocked");
      auto res = algo::astar_lazy(g, start, goal);
      auto t1 = std::chrono::steady_clock::now();
      double sec = std::chrono::duration<double>(t1 - t0).count();
      if (!res.cost.has_value()) {
        std::printf("no_path expansions=%llu time_s=%.6f\n", (unsigned long long)res.expansions, sec);
        return 1;
      }
      std::printf("cost=%.12g expansions=%llu time_s=%.6f w=%llu h=%llu\n", *res.cost,
                  (unsigned long long)res.expansions, sec, (unsigned long long)g.w, (unsigned long long)g.h);
      return 0;
    }

    if (mode == "geom") {
      algo::GeomImplicit g = algo::GeomImplicit::from_spec_file(path);
      if (start >= g.num_nodes() || goal >= g.num_nodes()) throw std::runtime_error("start/goal out of range");
      auto res = algo::astar_lazy(g, start, goal);
      auto t1 = std::chrono::steady_clock::now();
      double sec = std::chrono::duration<double>(t1 - t0).count();
      if (!res.cost.has_value()) {
        std::printf("no_path expansions=%llu time_s=%.6f\n", (unsigned long long)res.expansions, sec);
        return 1;
      }
      std::printf("cost=%.12g expansions=%llu time_s=%.6f n=%llu\n", *res.cost,
                  (unsigned long long)res.expansions, sec, (unsigned long long)g.n);
      return 0;
    }

    throw std::runtime_error("unknown --mode (csr|grid|geom)");
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    usage(argv[0]);
    return 2;
  }
}
