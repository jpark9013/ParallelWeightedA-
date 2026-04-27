#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <stdexcept>
#include <utility>
#include <vector>

static inline uint64_t splitmix64(uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

static inline double u01(uint64_t x) {
  // 53 random bits -> double in [0,1)
  return (x >> 11) * (1.0 / 9007199254740992.0);
}

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "Usage:\n"
               "  %s grid50 --w W --h H --p-block P --seed S --out PATH [--conn 4|8]\n"
               "  %s geom50 --seed S --out PATH [--k K]\n"
               "  %s planar50 --seed S --out PATH\n"
               "\n"
               "  %s grid   --w W --h H --p-block P --seed S --out PATH [--conn 4|8]\n"
               "  %s geom   --n N --seed S --k K --out PATH\n"
               "  %s planar --n N --seed S --out PATH [--cands-per-node C]\n",
               argv0, argv0, argv0, argv0, argv0, argv0);
}

static uint64_t parse_u64(const char* s, const char* name) {
  if (!s || !*s) throw std::runtime_error(std::string("missing value for ") + name);
  char* end = nullptr;
  unsigned long long v = std::strtoull(s, &end, 10);
  if (!end || *end != '\0') throw std::runtime_error(std::string("invalid integer for ") + name + ": " + s);
  return static_cast<uint64_t>(v);
}

static double parse_double(const char* s, const char* name) {
  if (!s || !*s) throw std::runtime_error(std::string("missing value for ") + name);
  char* end = nullptr;
  double v = std::strtod(s, &end);
  if (!end || *end != '\0') throw std::runtime_error(std::string("invalid float for ") + name + ": " + s);
  return v;
}

static inline bool blocked_grid(uint64_t seed, uint64_t id, double p) {
  if (p <= 0.0) return false;
  if (p >= 1.0) return true;
  uint64_t h = splitmix64(seed ^ id);
  long double thresh = p * (long double)18446744073709551616.0L; // 2^64
  return (long double)h < thresh;
}

static void write_edges(const std::string& out, const std::vector<std::pair<int,int>>& edges) {
  std::FILE* fp = std::fopen(out.c_str(), "wb");
  if (!fp) throw std::runtime_error("failed to open output file");
  for (auto [u,v] : edges) std::fprintf(fp, "%d %d\n", u, v);
  std::fclose(fp);
}

static void gen_grid50(uint64_t w, uint64_t h, double p, uint64_t seed, int conn, const std::string& out) {
  const int n = 50;
  // choose a 10x5 by default, but enforce w*h==50 if user passes sizes.
  if (w * h != (uint64_t)n) throw std::runtime_error("grid50 requires w*h == 50");
  if (!(conn == 4 || conn == 8)) throw std::runtime_error("--conn must be 4 or 8");

  auto id = [w](int x, int y) { return y * (int)w + x; };

  std::vector<std::pair<int,int>> edges;
  edges.reserve(4 * n);

  for (int y = 0; y < (int)h; y++) {
    for (int x = 0; x < (int)w; x++) {
      int u = id(x, y);
      if (blocked_grid(seed, (uint64_t)u, p)) continue;

      const int dx4[4] = {1, -1, 0, 0};
      const int dy4[4] = {0, 0, 1, -1};
      for (int k = 0; k < 4; k++) {
        int nx = x + dx4[k], ny = y + dy4[k];
        if (0 <= nx && nx < (int)w && 0 <= ny && ny < (int)h) {
          int v = id(nx, ny);
          if (blocked_grid(seed, (uint64_t)v, p)) continue;
          if (u < v) edges.emplace_back(u, v);
        }
      }
      if (conn == 8) {
        const int dx4d[4] = {1, 1, -1, -1};
        const int dy4d[4] = {1, -1, 1, -1};
        for (int k = 0; k < 4; k++) {
          int nx = x + dx4d[k], ny = y + dy4d[k];
          if (0 <= nx && nx < (int)w && 0 <= ny && ny < (int)h) {
            int v = id(nx, ny);
            if (blocked_grid(seed, (uint64_t)v, p)) continue;
            if (u < v) edges.emplace_back(u, v);
          }
        }
      }
    }
  }
  write_edges(out, edges);
}

static void gen_grid(uint64_t w, uint64_t h, double p, uint64_t seed, int conn, const std::string& out) {
  if (w == 0 || h == 0) throw std::runtime_error("grid requires w,h > 0");
  if (!(conn == 4 || conn == 8)) throw std::runtime_error("--conn must be 4 or 8");
  const uint64_t n = w * h;
  if (n > (uint64_t)std::numeric_limits<int>::max()) throw std::runtime_error("grid too large for explicit edge list");

  auto id = [w](int x, int y) { return y * (int)w + x; };

  std::vector<std::pair<int, int>> edges;
  edges.reserve((size_t)(4 * n));

  for (int y = 0; y < (int)h; y++) {
    for (int x = 0; x < (int)w; x++) {
      int u = id(x, y);
      if (blocked_grid(seed, (uint64_t)u, p)) continue;

      const int dx4[4] = {1, -1, 0, 0};
      const int dy4[4] = {0, 0, 1, -1};
      for (int k = 0; k < 4; k++) {
        int nx = x + dx4[k], ny = y + dy4[k];
        if (0 <= nx && nx < (int)w && 0 <= ny && ny < (int)h) {
          int v = id(nx, ny);
          if (blocked_grid(seed, (uint64_t)v, p)) continue;
          if (u < v) edges.emplace_back(u, v);
        }
      }
      if (conn == 8) {
        const int dx4d[4] = {1, 1, -1, -1};
        const int dy4d[4] = {1, -1, 1, -1};
        for (int k = 0; k < 4; k++) {
          int nx = x + dx4d[k], ny = y + dy4d[k];
          if (0 <= nx && nx < (int)w && 0 <= ny && ny < (int)h) {
            int v = id(nx, ny);
            if (blocked_grid(seed, (uint64_t)v, p)) continue;
            if (u < v) edges.emplace_back(u, v);
          }
        }
      }
    }
  }
  write_edges(out, edges);
}

static std::pair<double,double> point2(uint64_t seed, uint64_t i) {
  uint64_t a = splitmix64(seed ^ (i * 2ULL));
  uint64_t b = splitmix64(seed ^ (i * 2ULL + 1ULL));
  return {u01(a), u01(b)};
}

static void gen_geom50(uint64_t seed, int k, const std::string& out) {
  const int n = 50;
  if (k <= 0) throw std::runtime_error("--k must be > 0");
  if (k >= n) k = n - 1;

  std::vector<std::pair<double,double>> pts(n);
  for (int i = 0; i < n; i++) pts[i] = point2(seed, (uint64_t)i);

  std::vector<std::pair<int,int>> edges;
  edges.reserve(n * k);

  for (int i = 0; i < n; i++) {
    std::vector<std::pair<double,int>> dist;
    dist.reserve(n-1);
    for (int j = 0; j < n; j++) if (j != i) {
      double dx = pts[i].first - pts[j].first;
      double dy = pts[i].second - pts[j].second;
      double d2 = dx*dx + dy*dy;
      dist.emplace_back(d2, j);
    }
    std::nth_element(dist.begin(), dist.begin() + k, dist.end());
    dist.resize(k);
    for (auto& [d2, j] : dist) {
      int u = i, v = j;
      if (v < u) std::swap(u, v);
      edges.emplace_back(u, v);
    }
  }
  std::sort(edges.begin(), edges.end());
  edges.erase(std::unique(edges.begin(), edges.end()), edges.end());
  write_edges(out, edges);
}

static void gen_geom(uint64_t n, uint64_t seed, int k, const std::string& out) {
  if (n == 0) throw std::runtime_error("geom requires --n > 0");
  if (n > (uint64_t)std::numeric_limits<int>::max()) throw std::runtime_error("geom too large for explicit edge list");
  int nn = (int)n;
  if (k <= 0) throw std::runtime_error("--k must be > 0");
  if (k >= nn) k = nn - 1;

  std::vector<std::pair<double,double>> pts((size_t)nn);
  for (int i = 0; i < nn; i++) pts[(size_t)i] = point2(seed, (uint64_t)i);

  std::vector<std::pair<int,int>> edges;
  edges.reserve((size_t)nn * (size_t)k);

  for (int i = 0; i < nn; i++) {
    std::vector<std::pair<double,int>> dist;
    dist.reserve((size_t)nn - 1);
    for (int j = 0; j < nn; j++) if (j != i) {
      double dx = pts[(size_t)i].first - pts[(size_t)j].first;
      double dy = pts[(size_t)i].second - pts[(size_t)j].second;
      double d2 = dx*dx + dy*dy;
      dist.emplace_back(d2, j);
    }
    std::nth_element(dist.begin(), dist.begin() + k, dist.end());
    dist.resize((size_t)k);
    for (auto& [d2, j] : dist) {
      (void)d2;
      int u = i, v = j;
      if (v < u) std::swap(u, v);
      edges.emplace_back(u, v);
    }
  }
  std::sort(edges.begin(), edges.end());
  edges.erase(std::unique(edges.begin(), edges.end()), edges.end());
  write_edges(out, edges);
}

static bool seg_intersect(double ax, double ay, double bx, double by,
                          double cx, double cy, double dx, double dy) {
  auto orient = [](double ax, double ay, double bx, double by, double cx, double cy) {
    return (bx-ax)*(cy-ay) - (by-ay)*(cx-ax);
  };
  auto on_seg = [](double ax, double ay, double bx, double by, double px, double py) {
    return std::min(ax,bx) <= px && px <= std::max(ax,bx) && std::min(ay,by) <= py && py <= std::max(ay,by);
  };
  double o1 = orient(ax,ay,bx,by,cx,cy);
  double o2 = orient(ax,ay,bx,by,dx,dy);
  double o3 = orient(cx,cy,dx,dy,ax,ay);
  double o4 = orient(cx,cy,dx,dy,bx,by);

  auto sgn = [](double v) { return (v > 0) - (v < 0); };
  int s1 = sgn(o1), s2 = sgn(o2), s3 = sgn(o3), s4 = sgn(o4);
  if (s1 != s2 && s3 != s4) return true;
  if (s1 == 0 && on_seg(ax,ay,bx,by,cx,cy)) return true;
  if (s2 == 0 && on_seg(ax,ay,bx,by,dx,dy)) return true;
  if (s3 == 0 && on_seg(cx,cy,dx,dy,ax,ay)) return true;
  if (s4 == 0 && on_seg(cx,cy,dx,dy,bx,by)) return true;
  return false;
}

static void gen_planar50(uint64_t seed, const std::string& out) {
  // Greedy planar-ish graph: random points, try to add short edges that don't cross.
  const int n = 50;
  std::vector<std::pair<double,double>> pts(n);
  for (int i = 0; i < n; i++) pts[i] = point2(seed, (uint64_t)i);

  struct Edge { int u,v; double d2; };
  std::vector<Edge> candidates;
  candidates.reserve(n*(n-1)/2);
  for (int i = 0; i < n; i++) for (int j = i+1; j < n; j++) {
    double dx = pts[i].first - pts[j].first;
    double dy = pts[i].second - pts[j].second;
    candidates.push_back({i,j,dx*dx+dy*dy});
  }
  std::sort(candidates.begin(), candidates.end(), [](const Edge& a, const Edge& b){ return a.d2 < b.d2; });

  std::vector<std::pair<int,int>> edges;
  edges.reserve(3*n);

  for (const auto& e : candidates) {
    // stop around ~3n edges (triangulation-ish density)
    if ((int)edges.size() >= 3*n) break;
    bool ok = true;
    double ax = pts[e.u].first, ay = pts[e.u].second;
    double bx = pts[e.v].first, by = pts[e.v].second;
    for (auto [p,q] : edges) {
      if (p == e.u || p == e.v || q == e.u || q == e.v) continue;
      double cx = pts[p].first, cy = pts[p].second;
      double dx = pts[q].first, dy = pts[q].second;
      if (seg_intersect(ax,ay,bx,by,cx,cy,dx,dy)) { ok = false; break; }
    }
    if (ok) edges.emplace_back(e.u, e.v);
  }
  write_edges(out, edges);
}

static void gen_planar(uint64_t n, uint64_t seed, int cands_per_node, const std::string& out) {
  if (n == 0) throw std::runtime_error("planar requires --n > 0");
  if (n > (uint64_t)std::numeric_limits<int>::max()) throw std::runtime_error("planar too large");
  int nn = (int)n;
  if (cands_per_node <= 0) throw std::runtime_error("--cands-per-node must be > 0");
  if (cands_per_node >= nn) cands_per_node = nn - 1;

  // Candidate edges: for each node, take cands_per_node nearest neighbors (O(n^2) but fine for n<=1000).
  std::vector<std::pair<double,double>> pts((size_t)nn);
  for (int i = 0; i < nn; i++) pts[(size_t)i] = point2(seed, (uint64_t)i);

  struct Edge { int u,v; double d2; };
  std::vector<Edge> candidates;
  candidates.reserve((size_t)nn * (size_t)cands_per_node);

  for (int i = 0; i < nn; i++) {
    std::vector<std::pair<double,int>> dist;
    dist.reserve((size_t)nn - 1);
    for (int j = 0; j < nn; j++) if (j != i) {
      double dx = pts[(size_t)i].first - pts[(size_t)j].first;
      double dy = pts[(size_t)i].second - pts[(size_t)j].second;
      dist.emplace_back(dx*dx + dy*dy, j);
    }
    std::nth_element(dist.begin(), dist.begin() + cands_per_node, dist.end());
    dist.resize((size_t)cands_per_node);
    for (auto& [d2, j] : dist) {
      int u = i, v = j;
      if (v < u) std::swap(u, v);
      candidates.push_back({u, v, d2});
    }
  }

  std::sort(candidates.begin(), candidates.end(), [](const Edge& a, const Edge& b) {
    if (a.d2 != b.d2) return a.d2 < b.d2;
    if (a.u != b.u) return a.u < b.u;
    return a.v < b.v;
  });
  candidates.erase(std::unique(candidates.begin(), candidates.end(), [](const Edge& a, const Edge& b) {
                     return a.u == b.u && a.v == b.v;
                   }),
                   candidates.end());

  std::vector<std::pair<int,int>> edges;
  edges.reserve((size_t)(3 * nn));

  for (const auto& e : candidates) {
    if ((int)edges.size() >= 3 * nn) break;
    bool ok = true;
    double ax = pts[(size_t)e.u].first, ay = pts[(size_t)e.u].second;
    double bx = pts[(size_t)e.v].first, by = pts[(size_t)e.v].second;
    for (auto [p,q] : edges) {
      if (p == e.u || p == e.v || q == e.u || q == e.v) continue;
      double cx = pts[(size_t)p].first, cy = pts[(size_t)p].second;
      double dx = pts[(size_t)q].first, dy = pts[(size_t)q].second;
      if (seg_intersect(ax,ay,bx,by,cx,cy,dx,dy)) { ok = false; break; }
    }
    if (ok) edges.emplace_back(e.u, e.v);
  }
  write_edges(out, edges);
}

int main(int argc, char** argv) {
  try {
    if (argc < 2) { usage(argv[0]); return 2; }
    std::string mode = argv[1];

    if (mode == "grid50") {
      uint64_t w = 10, h = 5, seed = 1;
      double p = 0.2;
      int conn = 4;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--w") == 0) w = parse_u64(argv[++i], "--w");
        else if (std::strcmp(a, "--h") == 0) h = parse_u64(argv[++i], "--h");
        else if (std::strcmp(a, "--p-block") == 0) p = parse_double(argv[++i], "--p-block");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--conn") == 0) conn = (int)parse_u64(argv[++i], "--conn");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_grid50(w,h,p,seed,conn,out);
      return 0;
    }

    if (mode == "geom50") {
      uint64_t seed = 1;
      int k = 6;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--k") == 0) k = (int)parse_u64(argv[++i], "--k");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_geom50(seed, k, out);
      return 0;
    }

    if (mode == "planar50") {
      uint64_t seed = 1;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_planar50(seed, out);
      return 0;
    }

    if (mode == "grid") {
      uint64_t w = 0, h = 0, seed = 1;
      double p = 0.2;
      int conn = 4;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--w") == 0) w = parse_u64(argv[++i], "--w");
        else if (std::strcmp(a, "--h") == 0) h = parse_u64(argv[++i], "--h");
        else if (std::strcmp(a, "--p-block") == 0) p = parse_double(argv[++i], "--p-block");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--conn") == 0) conn = (int)parse_u64(argv[++i], "--conn");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_grid(w, h, p, seed, conn, out);
      return 0;
    }

    if (mode == "geom") {
      uint64_t n = 0, seed = 1;
      int k = 8;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--n") == 0) n = parse_u64(argv[++i], "--n");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--k") == 0) k = (int)parse_u64(argv[++i], "--k");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_geom(n, seed, k, out);
      return 0;
    }

    if (mode == "planar") {
      uint64_t n = 0, seed = 1;
      int c = 24;
      std::string out;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--n") == 0) n = parse_u64(argv[++i], "--n");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--cands-per-node") == 0) c = (int)parse_u64(argv[++i], "--cands-per-node");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) { usage(argv[0]); return 0; }
        else throw std::runtime_error(std::string("unknown arg: ") + a);
      }
      if (out.empty()) throw std::runtime_error("--out required");
      gen_planar(n, seed, c, out);
      return 0;
    }

    throw std::runtime_error("unknown mode");
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    usage(argv[0]);
    return 2;
  }
}

