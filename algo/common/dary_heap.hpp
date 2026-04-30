#pragma once
#include <cstddef>
#include <utility>
#include <vector>

namespace algo {

// Cache-friendlier d-ary min-heap.
// Compare behaves like std::greater<T> for a min-heap:
//   comp(a,b) == true  <=>  a has lower priority than b (a > b for tuples).
template <typename T, int D, typename Compare>
class DaryHeap {
 public:
  explicit DaryHeap(Compare comp = Compare()) : comp_(comp) {}

  bool empty() const { return a_.empty(); }
  size_t size() const { return a_.size(); }
  const T& top() const { return a_.front(); }

  void push(const T& v) {
    a_.push_back(v);
    sift_up(a_.size() - 1);
  }
  void push(T&& v) {
    a_.push_back(std::move(v));
    sift_up(a_.size() - 1);
  }

  template <class... Args>
  void emplace(Args&&... args) {
    a_.emplace_back(std::forward<Args>(args)...);
    sift_up(a_.size() - 1);
  }

  void pop() {
    if (a_.empty()) return;
    if (a_.size() == 1) {
      a_.pop_back();
      return;
    }
    a_.front() = std::move(a_.back());
    a_.pop_back();
    sift_down(0);
  }

 private:
  std::vector<T> a_;
  Compare comp_;

  static inline size_t parent(size_t i) { return (i - 1) / (size_t)D; }
  static inline size_t child0(size_t i) { return i * (size_t)D + 1; }

  void sift_up(size_t i) {
    while (i > 0) {
      size_t p = parent(i);
      if (!comp_(a_[p], a_[i])) break;  // parent <= child => ok
      std::swap(a_[p], a_[i]);
      i = p;
    }
  }

  void sift_down(size_t i) {
    for (;;) {
      size_t c0 = child0(i);
      if (c0 >= a_.size()) return;
      size_t best = c0;
      size_t lim = c0 + (size_t)D;
      if (lim > a_.size()) lim = a_.size();
      for (size_t c = c0 + 1; c < lim; c++) {
        if (comp_(a_[best], a_[c])) best = c;  // best > c => c is better
      }
      if (!comp_(a_[i], a_[best])) return;  // i <= best => ok
      std::swap(a_[i], a_[best]);
      i = best;
    }
  }
};

}  // namespace algo

