#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <stdexcept>

static void usage(const char* argv0) {
  std::fprintf(stderr,
               "Usage:\n"
               "  %s grid --w W --h H --p-block P --seed S --connectivity 4|8 --out PATH\n"
               "  %s geom --n N --k K --candidates C --seed S --out PATH\n",
               argv0, argv0);
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

int main(int argc, char** argv) {
  try {
    if (argc < 2) {
      usage(argv[0]);
      return 2;
    }

    std::string mode = argv[1];
    std::string out;

    if (mode == "grid") {
      uint64_t w = 0, h = 0, seed = 0;
      int conn = 4;
      double p_block = 0.0;

      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--w") == 0) w = parse_u64(argv[++i], "--w");
        else if (std::strcmp(a, "--h") == 0) h = parse_u64(argv[++i], "--h");
        else if (std::strcmp(a, "--p-block") == 0) p_block = parse_double(argv[++i], "--p-block");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--connectivity") == 0) conn = static_cast<int>(parse_u64(argv[++i], "--connectivity"));
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) {
          usage(argv[0]);
          return 0;
        } else {
          throw std::runtime_error(std::string("unknown arg: ") + a);
        }
      }

      if (w == 0 || h == 0) throw std::runtime_error("grid requires --w and --h > 0");
      if (!(conn == 4 || conn == 8)) throw std::runtime_error("--connectivity must be 4 or 8");
      if (!(p_block >= 0.0 && p_block <= 1.0)) throw std::runtime_error("--p-block must be in [0,1]");
      if (out.empty()) throw std::runtime_error("--out is required");

      std::FILE* fp = std::fopen(out.c_str(), "wb");
      if (!fp) throw std::runtime_error("failed to open output file");

      __uint128_t n128 = static_cast<__uint128_t>(w) * static_cast<__uint128_t>(h);
      std::fprintf(fp, "type=grid_obstacles\n");
      std::fprintf(fp, "w=%llu\n", (unsigned long long)w);
      std::fprintf(fp, "h=%llu\n", (unsigned long long)h);
      std::fprintf(fp, "n=%llu%llu\n",
                   (unsigned long long)(n128 / 1000000000000000000ULL),
                   (unsigned long long)(n128 % 1000000000000000000ULL)); // human-ish; ok if leading zeros absent
      std::fprintf(fp, "seed=%llu\n", (unsigned long long)seed);
      std::fprintf(fp, "p_block=%.10f\n", p_block);
      std::fprintf(fp, "connectivity=%d\n", conn);
      std::fprintf(fp, "weight=%s\n", conn == 4 ? "1" : "euclidean");
      std::fclose(fp);
      return 0;
    }

    if (mode == "geom") {
      uint64_t n = 0, seed = 0, k = 0, candidates = 64;
      for (int i = 2; i < argc; i++) {
        const char* a = argv[i];
        if (std::strcmp(a, "--n") == 0) n = parse_u64(argv[++i], "--n");
        else if (std::strcmp(a, "--k") == 0) k = parse_u64(argv[++i], "--k");
        else if (std::strcmp(a, "--candidates") == 0) candidates = parse_u64(argv[++i], "--candidates");
        else if (std::strcmp(a, "--seed") == 0) seed = parse_u64(argv[++i], "--seed");
        else if (std::strcmp(a, "--out") == 0) out = argv[++i];
        else if (std::strcmp(a, "--help") == 0 || std::strcmp(a, "-h") == 0) {
          usage(argv[0]);
          return 0;
        } else {
          throw std::runtime_error(std::string("unknown arg: ") + a);
        }
      }

      if (n == 0) throw std::runtime_error("geom requires --n > 0");
      if (k == 0) throw std::runtime_error("geom requires --k > 0");
      if (candidates < k) throw std::runtime_error("--candidates must be >= --k");
      if (out.empty()) throw std::runtime_error("--out is required");

      std::FILE* fp = std::fopen(out.c_str(), "wb");
      if (!fp) throw std::runtime_error("failed to open output file");
      std::fprintf(fp, "type=geom_hash_knn\n");
      std::fprintf(fp, "n=%llu\n", (unsigned long long)n);
      std::fprintf(fp, "seed=%llu\n", (unsigned long long)seed);
      std::fprintf(fp, "k=%llu\n", (unsigned long long)k);
      std::fprintf(fp, "candidates=%llu\n", (unsigned long long)candidates);
      std::fprintf(fp, "weight=euclidean\n");
      std::fclose(fp);
      return 0;
    }

    throw std::runtime_error("unknown mode (expected grid or geom)");
  } catch (const std::exception& e) {
    std::fprintf(stderr, "error: %s\n", e.what());
    usage(argv[0]);
    return 2;
  }
}

