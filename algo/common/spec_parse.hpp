#pragma once
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>
#include <unordered_map>

namespace algo {

inline std::string trim(std::string s) {
  while (!s.empty() && std::isspace(static_cast<unsigned char>(s.front()))) s.erase(s.begin());
  while (!s.empty() && std::isspace(static_cast<unsigned char>(s.back()))) s.pop_back();
  return s;
}

inline std::unordered_map<std::string, std::string> read_key_value_file(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open spec: " + path);
  std::unordered_map<std::string, std::string> kv;
  std::string line;
  while (std::getline(in, line)) {
    line = trim(line);
    if (line.empty() || line[0] == '#') continue;
    auto eq = line.find('=');
    if (eq == std::string::npos) throw std::runtime_error("bad spec line: " + line);
    std::string k = trim(line.substr(0, eq));
    std::string v = trim(line.substr(eq + 1));
    kv[k] = v;
  }
  return kv;
}

inline uint64_t parse_u64(const std::string& s, const char* name) {
  if (s.empty()) throw std::runtime_error(std::string("missing ") + name);
  char* end = nullptr;
  unsigned long long v = std::strtoull(s.c_str(), &end, 10);
  if (!end || *end != '\0') throw std::runtime_error(std::string("bad uint64 for ") + name);
  return static_cast<uint64_t>(v);
}

inline double parse_double(const std::string& s, const char* name) {
  if (s.empty()) throw std::runtime_error(std::string("missing ") + name);
  char* end = nullptr;
  double v = std::strtod(s.c_str(), &end);
  if (!end || *end != '\0') throw std::runtime_error(std::string("bad double for ") + name);
  return v;
}

inline int parse_int(const std::string& s, const char* name) {
  if (s.empty()) throw std::runtime_error(std::string("missing ") + name);
  char* end = nullptr;
  long v = std::strtol(s.c_str(), &end, 10);
  if (!end || *end != '\0') throw std::runtime_error(std::string("bad int for ") + name);
  return static_cast<int>(v);
}

}  // namespace algo
