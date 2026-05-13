// MPI + OpenMP distributed weighted A* with per-thread OPEN queues (HDA*-style partitioning).
// Within each MPI rank, vertex v is assigned to thread thread_of(v) using splitmix64 (Zobrist-style
// mixing); only that thread mutates gbest_t[t] and opens[t]. Cross-thread relaxes use a per-source
// row of buffers pending[src][dst] merged serially after each parallel wave (no locks on hot expand).
//
// MPI rank ownership of vertices matches main_mpi_fast (contiguous range).

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <limits>
#include <memory>
#include <optional>
#include <queue>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#include <mpi.h>
#include <omp.h>

#include "csr_graph.hpp"
#include "dary_heap.hpp"
#include "geom_implicit.hpp"
#include "grid_implicit.hpp"
#include "splitmix.hpp"

#pragma pack(push, 1)
struct RelaxMsg {
  uint64_t v;
  double g;
  double f;
  uint64_t parent;
};
#pragma pack(pop)

enum class GraphMode { Csr, Grid, Geom };

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "MPI+OpenMP A* — per-thread OPEN (Zobrist / splitmix partition within rank).\n"
               "Usage: same flags as astar_mpi_fast (--mode geom --spec PATH --start U --goal V ...)\n"
               "  --budget B   (default 256)\n",
               argv0);
}

static uint64_t parse_u64(const char* s) {
  char* end = nullptr;
  unsigned long long v = std::strtoull(s, &end, 10);
  if (!end || *end) throw std::runtime_error(std::string("bad uint64: ") + s);
  return static_cast<uint64_t>(v);
}

static double parse_double_arg(const char* s) {
  char* end = nullptr;
  double v = std::strtod(s, &end);
  if (!end || *end) throw std::runtime_error(std::string("bad double: ") + s);
  return v;
}

static inline size_t round_up64(size_t n) { return (n + 63u) & ~63u; }

struct AlignedBuf {
  void* p = nullptr;
  size_t n = 0;
  AlignedBuf() = default;
  explicit AlignedBuf(size_t bytes) { reset(bytes); }
  AlignedBuf(const AlignedBuf&) = delete;
  AlignedBuf& operator=(const AlignedBuf&) = delete;
  AlignedBuf(AlignedBuf&& o) noexcept : p(o.p), n(o.n) { o.p = nullptr; o.n = 0; }
  AlignedBuf& operator=(AlignedBuf&& o) noexcept {
    if (this != &o) {
      reset(0);
      p = o.p;
      n = o.n;
      o.p = nullptr;
      o.n = 0;
    }
    return *this;
  }
  ~AlignedBuf() { reset(0); }
  void reset(size_t bytes) {
    if (p) std::free(p);
    p = nullptr;
    n = 0;
    if (bytes == 0) return;
    size_t want = round_up64(bytes);
    p = std::aligned_alloc(64, want);
    if (!p) throw std::bad_alloc();
    n = want;
  }
  char* data() { return static_cast<char*>(p); }
  const char* data() const { return static_cast<const char*>(p); }
};

struct GraphHolder {
  GraphMode mode = GraphMode::Csr;
  std::unique_ptr<algo::CsrGraphU64> csr;
  std::unique_ptr<algo::GridImplicit> grid;
  std::unique_ptr<algo::GeomImplicit> geom;

  void neighbors(uint64_t u, std::vector<std::pair<uint64_t, double>>& out) const {
    switch (mode) {
      case GraphMode::Csr:
        csr->neighbors(u, out);
        return;
      case GraphMode::Grid:
        grid->neighbors(u, out);
        return;
      case GraphMode::Geom:
        geom->neighbors(u, out);
        return;
    }
  }

  double heuristic(uint64_t a, uint64_t goal) const {
    switch (mode) {
      case GraphMode::Csr:
        return csr->heuristic(a, goal);
      case GraphMode::Grid:
        return grid->heuristic(a, goal);
      case GraphMode::Geom:
        return geom->heuristic(a, goal);
    }
    return 0.0;
  }
};

static GraphHolder load_graph(GraphMode mode, const std::string& path) {
  GraphHolder g;
  g.mode = mode;
  switch (mode) {
    case GraphMode::Csr:
      g.csr = std::make_unique<algo::CsrGraphU64>(algo::CsrGraphU64::from_edge_list_undirected_unweighted(path));
      break;
    case GraphMode::Grid:
      g.grid = std::make_unique<algo::GridImplicit>(algo::GridImplicit::from_spec_file(path));
      break;
    case GraphMode::Geom:
      g.geom = std::make_unique<algo::GeomImplicit>(algo::GeomImplicit::from_spec_file(path));
      break;
    default:
      throw std::runtime_error("bad graph mode");
  }
  return g;
}

struct DistStateZob {
  int rank = 0;
  int nranks = 1;
  int nt = 1;
  uint64_t goal = 0;
  uint64_t zseed = 0x9E3779B97F4A7C15ULL ^ 0xC001D00DULL;
  int budget = 256;
  uint64_t max_supersteps = 50000000ULL;
  double h_weight = 1.0;
  /** GeomImplicit uses mutable scratch / heuristic caches; serialize neighbor generation for OMP. */
  bool geom_serial_neighbors = false;

  GraphHolder gh;
  uint64_t n_total = 0;
  uint64_t expansion_total = 0;

  using OpenEl = std::tuple<double, double, uint64_t>;
  enum class HeapMode { Stl, Dary4 };

  struct OpenQueue {
    HeapMode mode = HeapMode::Stl;
    std::priority_queue<OpenEl, std::vector<OpenEl>, std::greater<OpenEl>> stl;
    algo::DaryHeap<OpenEl, 4, std::greater<OpenEl>> d4;
    explicit OpenQueue(HeapMode m = HeapMode::Stl) : mode(m), stl(), d4(std::greater<OpenEl>()) {}
    bool empty() const { return mode == HeapMode::Stl ? stl.empty() : d4.empty(); }
    const OpenEl& top() const { return mode == HeapMode::Stl ? stl.top() : d4.top(); }
    void pop() { mode == HeapMode::Stl ? stl.pop() : d4.pop(); }
    void push(const OpenEl& e) { mode == HeapMode::Stl ? stl.push(e) : d4.push(e); }
    void emplace(double f, double g, uint64_t v) { mode == HeapMode::Stl ? stl.emplace(f, g, v) : d4.emplace(f, g, v); }
  };

  HeapMode heap_mode = HeapMode::Dary4;
  std::vector<OpenQueue> opens;
  std::vector<std::unordered_map<uint64_t, double>> gbest_t;

  std::vector<std::pair<uint64_t, double>> nbr;
  std::vector<std::vector<std::pair<uint64_t, double>>> nbr_per_thread;

  std::vector<std::vector<RelaxMsg>> mail;

  std::atomic<bool> goal_hit{false};
  bool found = false;
  double found_cost = std::numeric_limits<double>::infinity();
  uint64_t superstep = 0;

  DistStateZob(int r, int n, GraphHolder&& g, uint64_t gl, int bud, uint64_t maxss, double hw, HeapMode hm)
      : rank(r),
        nranks(n),
        nt(std::max(1, omp_get_max_threads())),
        goal(gl),
        zseed(0x9E3779B97F4A7C15ULL ^ (uint64_t)(unsigned)rank * 0x100000001ULL),
        budget(bud),
        max_supersteps(maxss),
        h_weight(hw),
        heap_mode(hm),
        gh(std::move(g)) {
    if (!(h_weight > 0.0) || std::isnan(h_weight) || std::isinf(h_weight)) {
      throw std::runtime_error("h_weight (-w) must be finite and > 0");
    }
    mail.assign((size_t)nranks, {});
    for (auto& mb : mail) mb.reserve(16384);
    opens.reserve((size_t)nt);
    gbest_t.resize((size_t)nt);
    for (int t = 0; t < nt; t++) {
      opens.emplace_back(heap_mode);
      gbest_t[(size_t)t].reserve(65536);
    }
    nbr.reserve(4096);
    nbr_per_thread.resize((size_t)nt);
    for (int t = 0; t < nt; t++) {
      nbr_per_thread[(size_t)t].reserve(4096);
    }
    if (gh.mode == GraphMode::Csr) {
      n_total = gh.csr->n;
    } else if (gh.mode == GraphMode::Grid) {
      n_total = gh.grid->num_nodes();
    } else {
      n_total = gh.geom->num_nodes();
    }
    geom_serial_neighbors = (gh.mode == GraphMode::Geom);
  }

  inline int owner(uint64_t v) const {
    if (nranks <= 1) return 0;
    __uint128_t num = static_cast<__uint128_t>(v) * static_cast<__uint128_t>(nranks);
    int rr = static_cast<int>(num / static_cast<__uint128_t>(n_total));
    if (rr < 0) rr = 0;
    if (rr >= nranks) rr = nranks - 1;
    return rr;
  }

  inline int thread_of(uint64_t v) const {
    if (nt <= 1) return 0;
    uint64_t h = algo::splitmix64(zseed ^ v);
    return static_cast<int>(h % static_cast<uint64_t>(nt));
  }

  void maybe_found(uint64_t v, double g) {
    if (v != goal) return;
#pragma omp critical(zob_found)
    {
      if (g < found_cost) {
        found_cost = g;
        found = true;
        goal_hit.store(true, std::memory_order_release);
      }
    }
  }

  bool any_open() const {
    for (int t = 0; t < nt; t++) {
      if (!opens[(size_t)t].empty()) return true;
    }
    return false;
  }

  void relax_same_thread(int dst, uint64_t v, double g, double f) {
    if (owner(v) != rank) return;
    if (thread_of(v) != dst) return;
    auto& gb = gbest_t[(size_t)dst];
    auto it = gb.find(v);
    if (it != gb.end() && !(g < it->second)) return;
    gb[v] = g;
    opens[(size_t)dst].emplace(f, g, v);
    maybe_found(v, g);
  }

  void expand_one_thread(int src_tid, uint64_t v, double g,
                         std::vector<std::vector<RelaxMsg>>& pend_row,
                         std::vector<std::pair<uint64_t, double>>& nbr_local) {
    auto& gmap = gbest_t[(size_t)src_tid];
    auto itg = gmap.find(v);
    if (itg == gmap.end() || g > itg->second) return;
    if (owner(v) != rank || thread_of(v) != src_tid) return;

    auto do_neighbors = [&]() {
      gh.neighbors(v, nbr_local);
      for (auto [to, w] : nbr_local) {
        if (!(w >= 0.0) || std::isnan(w)) continue;
        double tg = g + w;
        double tf = tg + h_weight * gh.heuristic(to, goal);
        int o = owner(to);
        if (o != rank) {
          mail[(size_t)o].push_back(RelaxMsg{to, tg, tf, v});
          continue;
        }
        int td = thread_of(to);
        if (td == src_tid) {
          relax_same_thread(src_tid, to, tg, tf);
        } else {
          pend_row[(size_t)td].push_back(RelaxMsg{to, tg, tf, v});
        }
      }
    };

    if (geom_serial_neighbors) {
#pragma omp critical(zob_geom_implicit)
      { do_neighbors(); }
    } else {
      do_neighbors();
    }
  }

  void drain_pending(std::vector<std::vector<std::vector<RelaxMsg>>>& pend) {
    for (int dst = 0; dst < nt; dst++) {
      for (int src = 0; src < nt; src++) {
        for (const auto& m : pend[(size_t)src][(size_t)dst]) {
          relax_same_thread(dst, m.v, m.g, m.f);
        }
      }
    }
  }

  void apply_messages_mpi(const std::vector<RelaxMsg>& in) {
    for (const RelaxMsg& m : in) {
      if (owner(m.v) != rank) continue;
      int dst = thread_of(m.v);
      relax_same_thread(dst, m.v, m.g, m.f);
    }
  }

  std::vector<std::vector<std::vector<RelaxMsg>>> pend_buf;

  int run_superstep() {
    int pops = 0;
    for (auto& v : mail) v.clear();

    if ((int)pend_buf.size() != nt) {
      pend_buf.assign((size_t)nt, std::vector<std::vector<RelaxMsg>>((size_t)nt));
    }

    int inner_guard = 0;
    while (pops < budget && !found && inner_guard < budget * 8) {
      inner_guard++;
      for (int s = 0; s < nt; s++) {
        for (int d = 0; d < nt; d++) {
          pend_buf[(size_t)s][(size_t)d].clear();
        }
      }
      std::vector<int> thread_pops((size_t)nt, 0);

#pragma omp parallel for schedule(static)
      for (int tid = 0; tid < nt; tid++) {
        if (goal_hit.load(std::memory_order_acquire)) {
          thread_pops[(size_t)tid] = 0;
          continue;
        }
        auto& pq = opens[(size_t)tid];
        if (pq.empty()) {
          thread_pops[(size_t)tid] = 0;
          continue;
        }
        OpenEl top = pq.top();
        pq.pop();
        double g = std::get<1>(top);
        uint64_t v = std::get<2>(top);
        auto itg = gbest_t[(size_t)tid].find(v);
        if (itg == gbest_t[(size_t)tid].end() || g > itg->second) {
          thread_pops[(size_t)tid] = 0;
          continue;
        }
        thread_pops[(size_t)tid] = 1;
        expand_one_thread(tid, v, g, pend_buf[(size_t)tid], nbr_per_thread[(size_t)tid]);
      }

      int wave = 0;
      for (int t = 0; t < nt; t++) wave += thread_pops[(size_t)t];
      pops += wave;
      expansion_total += static_cast<uint64_t>(wave);

      drain_pending(pend_buf);

      if (wave == 0 && !any_open()) break;
    }

    std::vector<int> sbytes((size_t)nranks, 0);
    std::vector<int> rbytes((size_t)nranks, 0);
    for (int r = 0; r < nranks; r++) {
      sbytes[(size_t)r] = static_cast<int>(mail[(size_t)r].size() * sizeof(RelaxMsg));
    }
    MPI_Alltoall(sbytes.data(), 1, MPI_INT, rbytes.data(), 1, MPI_INT, MPI_COMM_WORLD);

    int ssum = 0, rsum = 0;
    std::vector<int> sdis((size_t)nranks, 0), rdis((size_t)nranks, 0);
    for (int r = 0; r < nranks; r++) ssum += sbytes[(size_t)r];
    for (int r = 0; r < nranks; r++) {
      rsum += rbytes[(size_t)r];
      if (r > 0) sdis[(size_t)r] = sdis[(size_t)r - 1] + sbytes[(size_t)r - 1];
      if (r > 0) rdis[(size_t)r] = rdis[(size_t)r - 1] + rbytes[(size_t)r - 1];
    }

    AlignedBuf sbuf((size_t)std::max(1, ssum));
    AlignedBuf rbuf((size_t)std::max(1, rsum));
    for (int r = 0; r < nranks; r++) {
      if (sbytes[(size_t)r] > 0) {
        std::memcpy(sbuf.data() + sdis[(size_t)r], mail[(size_t)r].data(), (size_t)sbytes[(size_t)r]);
      }
    }
    MPI_Alltoallv(sbuf.data(), sbytes.data(), sdis.data(), MPI_BYTE, rbuf.data(), rbytes.data(), rdis.data(),
                  MPI_BYTE, MPI_COMM_WORLD);

    std::vector<RelaxMsg> incoming;
    incoming.resize((size_t)(rsum / (int)sizeof(RelaxMsg)));
    if (rsum > 0) std::memcpy(incoming.data(), rbuf.data(), (size_t)rsum);
    apply_messages_mpi(incoming);

    int lwork = pops + (rsum > 0 ? 1 : 0);
    int gwork = 0;
    MPI_Allreduce(&lwork, &gwork, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);

    int lopen = any_open() ? 1 : 0;
    int gopen = 0;
    MPI_Allreduce(&lopen, &gopen, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);

    int lfound = found ? 1 : 0;
    int gfound = 0;
    MPI_Allreduce(&lfound, &gfound, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);

    if (gfound) {
      double local_best = found ? found_cost : std::numeric_limits<double>::infinity();
      double global_best = std::numeric_limits<double>::infinity();
      MPI_Allreduce(&local_best, &global_best, 1, MPI_DOUBLE, MPI_MIN, MPI_COMM_WORLD);
      found_cost = global_best;
      found = true;
      return 0;
    }

    if (gwork == 0 && gopen == 0) return 0;
    superstep++;
    return 1;
  }

  std::optional<double> run(uint64_t start) {
    goal_hit.store(false, std::memory_order_relaxed);
    found = false;
    if (owner(start) == rank) {
      int dst = thread_of(start);
      double hg = gh.heuristic(start, goal);
      relax_same_thread(dst, start, 0.0, h_weight * hg);
    }

    for (uint64_t step = 0; step < max_supersteps; step++) {
      int cont = run_superstep();
      if (found) return std::optional<double>(found_cost);
      if (!cont) return std::nullopt;
    }
    return std::nullopt;
  }
};

int main(int argc, char** argv) {
  int provided = 0;
  MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provided);

  int rank = 0, nranks = 1;
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Comm_size(MPI_COMM_WORLD, &nranks);

  try {
    std::string mode_str;
    std::string path;
    uint64_t start = 0, goal = 0;
    int budget = 256;
    uint64_t maxss = 50000000ULL;
    double h_weight = 1.0;
    DistStateZob::HeapMode heap_mode = DistStateZob::HeapMode::Dary4;

    for (int i = 1; i < argc; i++) {
      const char* a = argv[i];
      if (!std::strcmp(a, "--mode")) mode_str = argv[++i];
      else if (!std::strcmp(a, "--edges") || !std::strcmp(a, "--spec")) path = argv[++i];
      else if (!std::strcmp(a, "--start")) start = parse_u64(argv[++i]);
      else if (!std::strcmp(a, "--goal")) goal = parse_u64(argv[++i]);
      else if (!std::strcmp(a, "-w")) h_weight = parse_double_arg(argv[++i]);
      else if (!std::strcmp(a, "--heap")) {
        const char* v = argv[++i];
        if (!std::strcmp(v, "stl")) heap_mode = DistStateZob::HeapMode::Stl;
        else if (!std::strcmp(v, "4ary")) heap_mode = DistStateZob::HeapMode::Dary4;
        else throw std::runtime_error("bad --heap (stl|4ary)");
      } else if (!std::strcmp(a, "--budget")) budget = (int)parse_u64(argv[++i]);
      else if (!std::strcmp(a, "--max-supersteps")) maxss = parse_u64(argv[++i]);
      else if (!std::strcmp(a, "-h") || !std::strcmp(a, "--help")) {
        if (rank == 0) usage(argv[0]);
        MPI_Finalize();
        return 0;
      } else {
        throw std::runtime_error(std::string("unknown arg: ") + a);
      }
    }

    if (mode_str.empty() || path.empty()) {
      if (rank == 0) usage(argv[0]);
      MPI_Finalize();
      return 2;
    }

    GraphMode gm = GraphMode::Csr;
    if (mode_str == "csr") gm = GraphMode::Csr;
    else if (mode_str == "grid") gm = GraphMode::Grid;
    else if (mode_str == "geom") gm = GraphMode::Geom;
    else
      throw std::runtime_error("unknown --mode");

    auto t0 = std::chrono::steady_clock::now();
    GraphHolder gh = load_graph(gm, path);

    if (gm == GraphMode::Grid) {
      if (goal >= gh.grid->num_nodes() || start >= gh.grid->num_nodes()) throw std::runtime_error("start/goal out of range");
      if (gh.grid->blocked(start) || gh.grid->blocked(goal)) throw std::runtime_error("start or goal blocked");
    } else if (gm == GraphMode::Geom) {
      if (goal >= gh.geom->num_nodes() || start >= gh.geom->num_nodes()) throw std::runtime_error("start/goal out of range");
    } else {
      if (goal >= gh.csr->n || start >= gh.csr->n) throw std::runtime_error("start/goal out of range");
    }

    DistStateZob st(rank, nranks, std::move(gh), goal, budget, maxss, h_weight, heap_mode);
    auto cost = st.run(start);
    auto t1 = std::chrono::steady_clock::now();
    double sec = std::chrono::duration<double>(t1 - t0).count();

    unsigned long long lexp = st.expansion_total;
    unsigned long long gexp = 0;
    MPI_Reduce(&lexp, &gexp, 1, MPI_UNSIGNED_LONG_LONG, MPI_SUM, 0, MPI_COMM_WORLD);

    if (rank == 0) {
      if (!cost.has_value()) {
        std::printf("no_path variant=zob_pq w_astar=%.6g expansions=%llu time_s=%.6f ranks=%d threads=%d\n", h_weight,
                    gexp, sec, nranks, omp_get_max_threads());
      } else {
        std::printf("cost=%.12g variant=zob_pq w_astar=%.6g expansions=%llu time_s=%.6f ranks=%d threads=%d\n",
                    *cost, h_weight, gexp, sec, nranks, omp_get_max_threads());
      }
    }

    MPI_Finalize();
    return cost.has_value() ? 0 : 1;
  } catch (const std::exception& e) {
    if (rank == 0) std::fprintf(stderr, "error: %s\n", e.what());
    MPI_Abort(MPI_COMM_WORLD, 2);
    return 2;
  }
}
