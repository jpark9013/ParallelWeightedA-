#pragma once
#include <cstddef>
#include <functional>
#include <utility>
#include <vector>

namespace algo {

// d-ary min-heap: comparator `Compare` such that `Compare()(a,b)` is true when `a` is worse than `b`
// (same convention as std::priority_queue with std::greater for min-heap on scores).
template <typename T, int D, typename Compare>
struct DaryHeap {
  static_assert(D >= 2, "D must be >= 2");
  std::vector<T> a;
  Compare cmp;

  explicit DaryHeap(Compare c) : cmp(std::move(c)) {}

  bool empty() const { return a.empty(); }
  size_t size() const { return a.size(); }

  const T& top() const { return a.front(); }

  void clear() { a.clear(); }

  void push(const T& x) {
    a.push_back(x);
    swim(a.size() - 1);
  }

  template <typename... Args>
  void emplace(Args&&... args) {
    a.emplace_back(std::forward<Args>(args)...);
    swim(a.size() - 1);
  }

  void pop() {
    if (a.empty()) return;
    a.front() = std::move(a.back());
    a.pop_back();
    if (!a.empty()) sink(0);
  }

 private:
  static inline size_t parent(size_t i) { return (i - 1) / (size_t)D; }

  void swim(size_t i) {
    while (i > 0) {
      size_t p = parent(i);
      if (cmp(a[p], a[i])) {
        std::swap(a[p], a[i]);
        i = p;
      } else {
        break;
      }
    }
  }

  void sink(size_t i) {
    const size_t n = a.size();
    for (;;) {
      size_t best = i;
      size_t base = (size_t)D * i + 1;
      for (int k = 0; k < D; k++) {
        size_t c = base + (size_t)k;
        if (c < n && cmp(a[best], a[c])) best = c;
      }
      if (best == i) return;
      std::swap(a[i], a[best]);
      i = best;
    }
  }
};

}  // namespace algo
