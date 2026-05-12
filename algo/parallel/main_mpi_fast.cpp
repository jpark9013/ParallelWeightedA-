#include <algorithm>
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

#include "astar_lazy.hpp"
#include "csr_graph.hpp"
#include "dary_heap.hpp"
#include "geom_implicit.hpp"
#include "grid_implicit.hpp"
#include "mpi_expand_tls.hpp"

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
               "Hybrid MPI+OpenMP Hash-Distributed A* (superstep) — tuned binary.\n"
               "Usage:\n"
               "  %s --mode csr   --edges PATH --start U --goal V [-w W] [--budget B] [--max-supersteps S]\n"
               "  %s --mode grid  --spec  PATH --start U --goal V [-w W] [--budget B] [--max-supersteps S]\n"
               "  %s --mode geom  --spec  PATH --start U --goal V [-w W] [--budget B] [--max-supersteps S]\n"
               "Optional:\n"
               "  --heap  stl|4ary            (default: 4ary)\n"
               "  --inbox critical|localpq|sharded    (default: sharded)\n"
               "Notes:\n"
               "  - Reuses thread-local neighbor staging (no per-expand nested vector alloc).\n"
               "  - `sharded` partitions inbound relaxations by v%%nt so gbest/open updates avoid\n"
               "    per-message omp critical sections on large inboxes.\n"
               "  - Weighted A*: priority uses f = g + W*h (default W=1).\n",
               argv0, argv0, argv0);
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

struct DistState {
  int rank = 0;
  int nranks = 1;
  uint64_t goal = 0;
  int budget = 128;
  uint64_t max_supersteps = 50000000ULL;
  double h_weight = 1.0;

  GraphHolder gh;
  uint64_t n_total = 0;
  uint64_t expansion_total = 0;

  using OpenEl = std::tuple<double, double, uint64_t>;
  enum class HeapMode { Stl, Dary4 };
  enum class InboxMode { Critical, LocalPQMerge, Sharded };

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
  InboxMode inbox_mode = InboxMode::Sharded;
  OpenQueue open;

  std::unordered_map<uint64_t, double> gbest;

  std::vector<std::pair<uint64_t, double>> nbr;
  std::vector<std::vector<RelaxMsg>> mail;

  MpiExpandTls<RelaxMsg> expand_tls;
  std::vector<RelaxMsg> inbox_work;
  std::vector<RelaxMsg> shard_buf;

  bool found = false;
  double found_cost = std::numeric_limits<double>::infinity();
  uint64_t superstep = 0;

  DistState(int r, int n, GraphHolder&& g, uint64_t gl, int bud, uint64_t maxss, double hw, HeapMode hm, InboxMode im)
      : rank(r),
        nranks(n),
        goal(gl),
        budget(bud),
        max_supersteps(maxss),
        h_weight(hw),
        heap_mode(hm),
        inbox_mode(im),
        open(hm),
        gh(std::move(g)) {
    if (!(h_weight > 0.0) || std::isnan(h_weight) || std::isinf(h_weight)) {
      throw std::runtime_error("h_weight (-w) must be finite and > 0");
    }
    mail.assign((size_t)nranks, {});
    gbest.reserve(1024);
    nbr.reserve(4096);
    inbox_work.reserve(4096);
    shard_buf.reserve(4096);
    if (gh.mode == GraphMode::Csr) {
      n_total = gh.csr->n;
    } else if (gh.mode == GraphMode::Grid) {
      n_total = gh.grid->num_nodes();
    } else {
      n_total = gh.geom->num_nodes();
    }
  }

  inline int owner(uint64_t v) const {
    if (nranks <= 1) return 0;
    __uint128_t num = static_cast<__uint128_t>(v) * static_cast<__uint128_t>(nranks);
    int r = static_cast<int>(num / static_cast<__uint128_t>(n_total));
    if (r < 0) r = 0;
    if (r >= nranks) r = nranks - 1;
    return r;
  }

  void maybe_found(uint64_t v, double g) {
    if (v == goal) {
      if (g < found_cost) {
        found_cost = g;
        found = true;
      }
    }
  }

  void relax_local_owned(uint64_t v, double g, double f, uint64_t /*parent*/) {
    if (owner(v) != rank) return;
    auto it = gbest.find(v);
    if (it != gbest.end() && !(g < it->second)) return;
    gbest[v] = g;
    open.emplace(f, g, v);
    maybe_found(v, g);
  }

  void expand_one(uint64_t v, double g) {
    auto itg = gbest.find(v);
    if (itg == gbest.end() || g > itg->second) return;
    if (owner(v) != rank) return;

    gh.neighbors(v, nbr);
    const int deg = static_cast<int>(nbr.size());
    const int use_omp = (deg >= 32 && omp_get_max_threads() > 1) ? 1 : 0;

    if (!use_omp) {
      for (auto [to, w] : nbr) {
        if (!(w >= 0.0) || std::isnan(w)) continue;
        double tg = g + w;
        double tf = tg + h_weight * gh.heuristic(to, goal);
        int o = owner(to);
        if (o == rank) {
          relax_local_owned(to, tg, tf, v);
        } else {
          mail[(size_t)o].push_back(RelaxMsg{to, tg, tf, v});
        }
      }
      return;
    }

    const int nt = std::max(1, omp_get_max_threads());
    expand_tls.ensure(nt, nranks);
    expand_tls.clear_all(nt, nranks);

#pragma omp parallel for schedule(static)
    for (int i = 0; i < deg; i++) {
      auto [to, w] = nbr[(size_t)i];
      if (!(w >= 0.0) || std::isnan(w)) continue;
      double tg = g + w;
      double tf = tg + h_weight * gh.heuristic(to, goal);
      int tid = omp_get_thread_num();
      int o = owner(to);
      if (o == rank) {
        expand_tls.thread_buckets(tid)[(size_t)rank].push_back(RelaxMsg{to, tg, tf, v});
      } else {
        expand_tls.thread_buckets(tid)[(size_t)o].push_back(RelaxMsg{to, tg, tf, v});
      }
    }

    for (int t = 0; t < nt; t++) {
      for (int o = 0; o < nranks; o++) {
        auto& src = expand_tls.thread_buckets(t)[(size_t)o];
        if (o == rank) {
          for (const auto& m : src) relax_local_owned(m.v, m.g, m.f, m.parent);
        } else if (!src.empty()) {
          auto& dst = mail[(size_t)o];
          dst.insert(dst.end(), src.begin(), src.end());
        }
      }
    }
  }

  void apply_messages_critical(const std::vector<RelaxMsg>& in) {
    const size_t n = in.size();
    if (n == 0) return;
    if (omp_get_max_threads() <= 1) {
      for (size_t i = 0; i < n; i++) {
        const RelaxMsg& m = in[i];
        if (owner(m.v) != rank) continue;
        auto it = gbest.find(m.v);
        if (it != gbest.end() && !(m.g < it->second)) continue;
        gbest[m.v] = m.g;
        open.emplace(m.f, m.g, m.v);
        maybe_found(m.v, m.g);
      }
      return;
    }
#pragma omp parallel for schedule(static)
    for (ptrdiff_t i = 0; i < static_cast<ptrdiff_t>(n); i++) {
      const RelaxMsg& m = in[(size_t)i];
      if (owner(m.v) != rank) continue;
#pragma omp critical(distastar_relax)
      {
        auto it = gbest.find(m.v);
        if (it != gbest.end() && !(m.g < it->second)) {
        } else {
          gbest[m.v] = m.g;
          open.emplace(m.f, m.g, m.v);
          maybe_found(m.v, m.g);
        }
      }
    }
  }

  void apply_messages_localpq_merge(const std::vector<RelaxMsg>& in) {
    const size_t n = in.size();
    if (n == 0) return;
    const int nt = std::max(1, omp_get_max_threads());
    if (nt <= 1) {
      OpenQueue local(heap_mode);
      for (size_t i = 0; i < n; i++) {
        const RelaxMsg& m = in[i];
        if (owner(m.v) != rank) continue;
        auto it = gbest.find(m.v);
        if (it != gbest.end() && !(m.g < it->second)) continue;
        gbest[m.v] = m.g;
        local.emplace(m.f, m.g, m.v);
      }
      while (!local.empty()) {
        const OpenEl& e = local.top();
        open.push(e);
        local.pop();
      }
      return;
    }

    std::vector<OpenQueue> localqs;
    localqs.reserve((size_t)nt);
    for (int t = 0; t < nt; t++) localqs.emplace_back(heap_mode);

#pragma omp parallel for schedule(static)
    for (ptrdiff_t i = 0; i < static_cast<ptrdiff_t>(n); i++) {
      const RelaxMsg& m = in[(size_t)i];
      if (owner(m.v) != rank) continue;
      const int tid = omp_get_thread_num();
      bool accept = false;
#pragma omp critical(distastar_relax_gbest)
      {
        auto it = gbest.find(m.v);
        if (it != gbest.end() && !(m.g < it->second)) {
        } else {
          gbest[m.v] = m.g;
          accept = true;
        }
      }
      if (accept) {
        localqs[(size_t)tid].emplace(m.f, m.g, m.v);
      }
    }

    for (int t = 0; t < nt; t++) {
      while (!localqs[(size_t)t].empty()) {
        const OpenEl& e = localqs[(size_t)t].top();
        open.push(e);
        localqs[(size_t)t].pop();
      }
    }
  }

  void apply_messages_sharded(const std::vector<RelaxMsg>& in) {
    const size_t n = in.size();
    if (n == 0) return;

    inbox_work.clear();
    inbox_work.reserve(n);
    for (size_t i = 0; i < n; i++) {
      const RelaxMsg& m = in[i];
      if (owner(m.v) == rank) inbox_work.push_back(m);
    }
    const size_t m = inbox_work.size();
    if (m == 0) return;

    const int nt = std::max(1, omp_get_max_threads());
    if (nt <= 1 || m < 512) {
      for (size_t i = 0; i < m; i++) {
        const RelaxMsg& msg = inbox_work[i];
        auto it = gbest.find(msg.v);
        if (it != gbest.end() && !(msg.g < it->second)) continue;
        gbest[msg.v] = msg.g;
        open.emplace(msg.f, msg.g, msg.v);
        maybe_found(msg.v, msg.g);
      }
      return;
    }

    std::vector<size_t> sizes((size_t)nt, 0);
    for (size_t i = 0; i < m; i++) {
      int b = static_cast<int>(inbox_work[i].v % static_cast<uint64_t>(nt));
      sizes[(size_t)b]++;
    }

    std::vector<size_t> off((size_t)nt + 1, 0);
    for (int b = 0; b < nt; b++) off[(size_t)b + 1] = off[(size_t)b] + sizes[(size_t)b];

    shard_buf.resize(m);
    std::vector<size_t> cur((size_t)nt);
    for (int b = 0; b < nt; b++) cur[(size_t)b] = off[(size_t)b];
    for (size_t i = 0; i < m; i++) {
      const RelaxMsg& msg = inbox_work[i];
      int b = static_cast<int>(msg.v % static_cast<uint64_t>(nt));
      shard_buf[cur[(size_t)b]++] = msg;
    }

#pragma omp parallel for schedule(dynamic, 1)
    for (int b = 0; b < nt; b++) {
      size_t start = off[(size_t)b];
      size_t end = off[(size_t)b + 1];
      if (start == end) continue;
      auto lo = shard_buf.begin() + static_cast<std::ptrdiff_t>(start);
      auto hi = shard_buf.begin() + static_cast<std::ptrdiff_t>(end);
      std::sort(lo, hi, [](const RelaxMsg& a, const RelaxMsg& b) {
        if (a.v != b.v) return a.v < b.v;
        return a.g < b.g;
      });
    }

    // gbest / open are not concurrent-safe; apply deduped relaxes serially after parallel sorts.
    for (int b = 0; b < nt; b++) {
      size_t start = off[(size_t)b];
      size_t end = off[(size_t)b + 1];
      for (size_t p = start; p < end;) {
        uint64_t vv = shard_buf[p].v;
        double best_g = shard_buf[p].g;
        double best_f = shard_buf[p].f;
        size_t q = p + 1;
        while (q < end && shard_buf[q].v == vv) {
          if (shard_buf[q].g < best_g) {
            best_g = shard_buf[q].g;
            best_f = shard_buf[q].f;
          }
          q++;
        }
        auto it = gbest.find(vv);
        if (it != gbest.end() && !(best_g < it->second)) {
          p = q;
          continue;
        }
        gbest[vv] = best_g;
        open.emplace(best_f, best_g, vv);
        maybe_found(vv, best_g);
        p = q;
      }
    }
  }

  void apply_messages(const std::vector<RelaxMsg>& in) {
    if (inbox_mode == InboxMode::Critical) return apply_messages_critical(in);
    if (inbox_mode == InboxMode::LocalPQMerge) return apply_messages_localpq_merge(in);
    return apply_messages_sharded(in);
  }

  int run_superstep() {
    int pops = 0;
    for (auto& v : mail) v.clear();

    while (pops < budget && !open.empty()) {
      OpenEl top = open.top();
      open.pop();
      double g = std::get<1>(top);
      uint64_t v = std::get<2>(top);
      auto itg = gbest.find(v);
      if (itg == gbest.end() || g > itg->second) continue;
      pops++;
      expand_one(v, g);
      if (found) break;
    }
    expansion_total += static_cast<uint64_t>(pops);

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
    apply_messages(incoming);

    int lwork = pops + (rsum > 0 ? 1 : 0);
    int gwork = 0;
    MPI_Allreduce(&lwork, &gwork, 1, MPI_INT, MPI_SUM, MPI_COMM_WORLD);

    int lopen = !open.empty() ? 1 : 0;
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
    if (owner(start) == rank) {
      double hg = gh.heuristic(start, goal);
      relax_local_owned(start, 0.0, h_weight * hg, start);
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
    int budget = 128;
    uint64_t maxss = 50000000ULL;
    double h_weight = 1.0;
    DistState::HeapMode heap_mode = DistState::HeapMode::Dary4;
    DistState::InboxMode inbox_mode = DistState::InboxMode::Sharded;

    for (int i = 1; i < argc; i++) {
      const char* a = argv[i];
      if (!std::strcmp(a, "--mode")) mode_str = argv[++i];
      else if (!std::strcmp(a, "--edges") || !std::strcmp(a, "--spec")) path = argv[++i];
      else if (!std::strcmp(a, "--start")) start = parse_u64(argv[++i]);
      else if (!std::strcmp(a, "--goal")) goal = parse_u64(argv[++i]);
      else if (!std::strcmp(a, "-w")) h_weight = parse_double_arg(argv[++i]);
      else if (!std::strcmp(a, "--heap")) {
        const char* v = argv[++i];
        if (!std::strcmp(v, "stl")) heap_mode = DistState::HeapMode::Stl;
        else if (!std::strcmp(v, "4ary")) heap_mode = DistState::HeapMode::Dary4;
        else throw std::runtime_error("bad --heap (stl|4ary)");
      } else if (!std::strcmp(a, "--inbox")) {
        const char* v = argv[++i];
        if (!std::strcmp(v, "critical")) inbox_mode = DistState::InboxMode::Critical;
        else if (!std::strcmp(v, "localpq")) inbox_mode = DistState::InboxMode::LocalPQMerge;
        else if (!std::strcmp(v, "sharded")) inbox_mode = DistState::InboxMode::Sharded;
        else throw std::runtime_error("bad --inbox (critical|localpq|sharded)");
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

    DistState st(rank, nranks, std::move(gh), goal, budget, maxss, h_weight, heap_mode, inbox_mode);
    auto cost = st.run(start);
    auto t1 = std::chrono::steady_clock::now();
    double sec = std::chrono::duration<double>(t1 - t0).count();

    unsigned long long lexp = st.expansion_total;
    unsigned long long gexp = 0;
    MPI_Reduce(&lexp, &gexp, 1, MPI_UNSIGNED_LONG_LONG, MPI_SUM, 0, MPI_COMM_WORLD);

    if (rank == 0) {
      if (!cost.has_value()) {
        std::printf("no_path w_astar=%.6g expansions=%llu time_s=%.6f ranks=%d threads=%d\n", h_weight, gexp, sec,
                    nranks, omp_get_max_threads());
      } else {
        std::printf("cost=%.12g w_astar=%.6g expansions=%llu time_s=%.6f ranks=%d threads=%d\n", *cost, h_weight,
                    gexp, sec, nranks, omp_get_max_threads());
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
