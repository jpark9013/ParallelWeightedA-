#include <cstdio>
#include <cstdint>
#include <cstring>
#include <string>
#include <random>
#include <stdexcept>
#include <limits>
#include <unordered_set>

struct Options {
  uint64_t n = 0;
  uint64_t m = 0;
  std::string out;
  bool directed = false;
  bool allow_self_loops = false;
  bool unique = false;
  bool header = false;
  bool seed_set = false;
  uint64_t seed = 0;
};

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "Usage: %s --n N --m M --out PATH [--directed] [--allow-self-loops] [--unique] [--seed S] [--header]\n",
               argv0);
}

static uint64_t parse_u64(const char* s, const char* name) {
  if (!s || !*s) throw std::runtime_error(std::string("missing value for ") + name);
  char* end = nullptr;
  unsigned long long v = std::strtoull(s, &end, 10);
  if (!end || *end != '\0') throw std::runtime_error(std::string("invalid integer for ") + name + ": " + s);
  return static_cast<uint64_t>(v);
}

static Options parse_args(int argc, char** argv) {
  Options opt;
  for (int i = 1; i < argc; i++) {
    const char* a = argv[i];
    if (std::strcmp(a, "--n") == 0) {
      if (i + 1 >= argc) throw std::runtime_error("missing --n value");
      opt.n = parse_u64(argv[++i], "--n");
    } else if (std::strcmp(a, "--m") == 0) {
      if (i + 1 >= argc) throw std::runtime_error("missing --m value");
      opt.m = parse_u64(argv[++i], "--m");
    } else if (std::strcmp(a, "--out") == 0) {
      if (i + 1 >= argc) throw std::runtime_error("missing --out value");
      opt.out = argv[++i];
    } else if (std::strcmp(a, "--directed") == 0) {
      opt.directed = true;
    } else if (std::strcmp(a, "--allow-self-loops") == 0) {
      opt.allow_self_loops = true;
    } else if (std::strcmp(a, "--unique") == 0) {
      opt.unique = true;
    } else if (std::strcmp(a, "--header") == 0) {
      opt.header = true;
    } else if (std::strcmp(a, "--seed") == 0) {
      if (i + 1 >= argc) throw std::runtime_error("missing --seed value");
      opt.seed = parse_u64(argv[++i], "--seed");
      opt.seed_set = true;
    } else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) {
      usage(argv[0]);
      std::exit(0);
    } else {
      throw std::runtime_error(std::string("unknown arg: ") + a);
    }
  }

  if (opt.n == 0) throw std::runtime_error("--n must be > 0");
  if (opt.out.empty()) throw std::runtime_error("--out is required");
  if (!opt.directed && opt.n < 2 && opt.m > 0) throw std::runtime_error("undirected graph needs n>=2 for edges");
  if (!opt.allow_self_loops && opt.n == 1 && opt.m > 0) throw std::runtime_error("n=1 with no self-loops cannot have edges");
  if (opt.unique) {
    // sanity upper bounds
    __uint128_t N = opt.n;
    __uint128_t max_edges = 0;
    if (opt.directed) {
      max_edges = opt.allow_self_loops ? (N * N) : (N * (N - 1));
    } else {
      // undirected unique edges: choose( n, 2 ) plus optional self-loops
      max_edges = (N * (N - 1)) / 2;
      if (opt.allow_self_loops) max_edges += N;
    }
    if (static_cast<__uint128_t>(opt.m) > max_edges) {
      throw std::runtime_error("--unique requested but m exceeds max possible unique edges for given flags");
    }
  }
  return opt;
}

static inline uint64_t splitmix64(uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

// Pack an (u,v) pair into a 64-bit key (fast) for hashing.
// Assumes u,v < 2^32.
static inline uint64_t pack_u32pair(uint32_t u, uint32_t v) {
  return (static_cast<uint64_t>(u) << 32) | static_cast<uint64_t>(v);
}

int main(int argc, char** argv) {
  try {
    Options opt = parse_args(argc, argv);

    // Use a fast deterministic PRNG (splitmix64) seeded either from user or random_device.
    uint64_t seed = opt.seed_set ? opt.seed : (static_cast<uint64_t>(std::random_device{}()) << 32) ^ std::random_device{}();
    uint64_t state = splitmix64(seed);
    auto next_u64 = [&]() -> uint64_t {
      state = splitmix64(state);
      return state;
    };

    if (opt.n > std::numeric_limits<uint32_t>::max()) {
      throw std::runtime_error("--n too large for this generator (must fit in uint32)");
    }

    std::FILE* fp = std::fopen(opt.out.c_str(), "wb");
    if (!fp) throw std::runtime_error("failed to open output file for writing");

    // Large buffer for fewer syscalls.
    static constexpr size_t BUF_SZ = 1u << 20; // 1 MiB
    char* buf = static_cast<char*>(std::malloc(BUF_SZ));
    if (buf) std::setvbuf(fp, buf, _IOFBF, BUF_SZ);

    if (opt.header) {
      std::fprintf(fp, "%llu %llu\n",
                   static_cast<unsigned long long>(opt.n),
                   static_cast<unsigned long long>(opt.m));
    }

    std::unordered_set<uint64_t> seen;
    if (opt.unique) {
      // Reserve to reduce rehashing; keep load factor conservative.
      seen.reserve(static_cast<size_t>(opt.m * 1.3) + 1024);
      seen.max_load_factor(0.7f);
    }

    const uint32_t n32 = static_cast<uint32_t>(opt.n);

    uint64_t written = 0;
    while (written < opt.m) {
      uint32_t u = static_cast<uint32_t>(next_u64() % n32);
      uint32_t v = static_cast<uint32_t>(next_u64() % n32);

      if (!opt.allow_self_loops) {
        if (u == v) continue;
      }

      if (!opt.directed) {
        // normalize order
        if (v < u) {
          uint32_t tmp = u;
          u = v;
          v = tmp;
        }
      }

      if (opt.unique) {
        uint64_t key = pack_u32pair(u, v);
        if (!seen.insert(key).second) continue;
      }

      std::fprintf(fp, "%u %u\n", u, v);
      written++;
    }

    std::fclose(fp);
    if (buf) std::free(buf);
    return 0;
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    usage(argv[0]);
    return 2;
  }
}

