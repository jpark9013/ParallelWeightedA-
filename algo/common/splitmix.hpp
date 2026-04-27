#pragma once
#include <cstdint>

namespace algo {

inline uint64_t splitmix64(uint64_t x) {
  x += 0x9e3779b97f4a7c15ULL;
  x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
  x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
  return x ^ (x >> 31);
}

inline double u01_from_u64(uint64_t x) {
  return (x >> 11) * (1.0 / 9007199254740992.0);
}

inline bool blocked_grid(uint64_t seed, uint64_t id, double p) {
  if (p <= 0.0) return false;
  if (p >= 1.0) return true;
  uint64_t h = splitmix64(seed ^ id);
  long double thresh = p * (long double)18446744073709551616.0L;
  return (long double)h < thresh;
}

}  // namespace algo
