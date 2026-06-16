#include "interpeter.h"

#include <cstdlib>
#include <iostream>
#include <string>

extern uint getConfig(const std::string& key);
extern bool hasConfig(const std::string& key);

using std::filesystem::path;

#define INTERPRETER_SYNTEX_CHECK(ch, missing, error_msg)                       \
  do {                                                                         \
    int cur = in_stream_.get();                                                \
    while (cur != ch) {                                                        \
      if (cur != ' ') {                                                        \
        std::cerr << "missing " missing " after " error_msg " in line: "       \
                  << line_ << std::endl;                                       \
        exit(1);                                                               \
      }                                                                        \
      cur = in_stream_.get();                                                  \
    }                                                                          \
  } while (0)

Interpeter::Interpeter(path input_file, MemoryHierarchy &mem, Options opts,
                       size_t &cpu_cycles)
    : in_stream_(input_file), line_(0), cpu_cycles_(cpu_cycles),
      trace_level_(opts.trace_level), vec_regs_{}, mem_(mem) {
  if (!in_stream_.is_open()) {
    std::cerr << "error opening trace file" << std::endl;
    exit(1);
  }
  if (!opts.trace_file_path.empty()) {
    trace_out_.open(opts.trace_file_path, std::ios::trunc);
    if (!trace_out_.is_open()) {
      std::cerr << "error opening --trace_file: " << opts.trace_file_path
                << std::endl;
      exit(1);
    }
  }
}

void Interpeter::doRead(Addr addr, size_t size) {
  Trace t;
  mem_.read(addr, size, t);
  uint cycles = totalCycles(t);
  cpu_cycles_ += cycles;
  logAccess("read ", addr, cycles, t);
}

void Interpeter::doWrite(Addr addr, size_t size) {
  Trace t;
  mem_.write(addr, size, t);
  uint cycles = totalCycles(t);
  cpu_cycles_ += cycles;
  logAccess("write", addr, cycles, t);
}

void Interpeter::logAccess(const char *op, Addr addr, uint cycles,
                           const Trace &t) {
  if (!trace_out_.is_open() || trace_level_ < trace_accesses) return;

  inst_detail_ << "  " << op << " @0x" << std::hex << addr << std::dec << " ("
               << cycles << " cy)\n";

  if (trace_level_ < trace_actions) return;
  for (const auto &a : t) {
    inst_detail_ << "    ";
    a->print(inst_detail_);
    inst_detail_ << '\n';
  }
}

void Interpeter::run() {
  while (!in_stream_.eof()) {
    handleCmd();
  }
}

uint Interpeter::parseReg() {
  std::string reg_name;
  in_stream_ >> reg_name;
  if (!reg_name.empty() && reg_name.back() == ',') {
    reg_name.pop_back();
  }

  if (reg_name == "%ra") return 0;
  if (reg_name == "%rb") return 1;
  if (reg_name == "%rc") return 2;

  std::cerr << "invalid register in line: " << line_ << std::endl;
  exit(1);
}

void Interpeter::handleTload() {
  Addr base_addr;
  uint tile_width;
  uint tile_height;
  uint stride;
  uint elem_width;

  INTERPRETER_SYNTEX_CHECK('(', "opening parenthesis", "command name");

  in_stream_ >> std::hex >> base_addr;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "base address");

  in_stream_ >> std::dec >> tile_width;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile width");

  in_stream_ >> tile_height;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile height");

  in_stream_ >> stride;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "stride");

  in_stream_ >> elem_width;

  INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis", "source parameters");

  INTERPRETER_SYNTEX_CHECK(',', "comma", "source parameters pack");

  uint dst_reg = parseReg();

  // Enforce hardware register size constraints if configured
  if (hasConfig("REG_M")) {
      uint reg_m = getConfig("REG_M");
      uint reg_n = getConfig("REG_N");
      uint reg_k = getConfig("REG_K");
      if (tile_width != 1 || tile_height != 1) {
          if (dst_reg == 0) { // %ra
              if (tile_width != reg_k || tile_height != reg_m) {
                  std::cerr << "Error: register %ra load dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_K x REG_M (" << reg_k << "x" << reg_m << ")\n";
                  exit(1);
              }
          } else if (dst_reg == 1) { // %rb
              if (tile_width != reg_n || tile_height != reg_k) {
                  std::cerr << "Error: register %rb load dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_N x REG_K (" << reg_n << "x" << reg_k << ")\n";
                  exit(1);
              }
          } else if (dst_reg == 2) { // %rc
              if (tile_width != reg_n || tile_height != reg_m) {
                  std::cerr << "Error: register %rc load dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_N x REG_M (" << reg_n << "x" << reg_m << ")\n";
                  exit(1);
              }
          }
      }
  }

  vec_regs_[dst_reg] = {base_addr, tile_width, tile_height, stride, elem_width};

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  std::ostringstream h;
  h << "ltea (0x" << std::hex << base_addr << std::dec << ", " << tile_width
    << ", " << tile_height << ", " << stride << ", " << elem_width << "), %r"
    << "abc"[dst_reg];
  inst_header_ = h.str();

  // Generated tiles must consist of whole cache lines; partial-line rows are
  // deliberately unsupported for now.
  const PrngDev &prng = mem_.prng();
  if (prng.contains(base_addr) &&
      (tile_width * elem_width) % prng.lineSize() != 0) {
    std::cerr << "PRNG tile row of " << tile_width * elem_width
              << " bytes is not a multiple of the cache line size ("
              << prng.lineSize() << ") in line: " << line_ << std::endl;
    exit(1);
  }

  for (uint row = 0; row < tile_height; ++row) {
    for (uint col = 0; col < tile_width; ++col) {
      Addr target = base_addr + (row * stride + col) * elem_width;

      doRead(target, elem_width);
    }
  }
}

void Interpeter::handleTmove() {
  Addr base_addr;
  uint tile_width;
  uint tile_height;
  uint stride;
  uint elem_width;

  INTERPRETER_SYNTEX_CHECK('(', "opening parenthesis", "command name");

  in_stream_ >> std::hex >> base_addr;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "base address");

  in_stream_ >> std::dec >> tile_width;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile width");

  in_stream_ >> tile_height;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile height");

  in_stream_ >> stride;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "stride");

  in_stream_ >> elem_width;

  INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis", "source parameters");

  INTERPRETER_SYNTEX_CHECK(',', "comma", "source parameters pack");

  uint src_reg = parseReg();

  // Enforce hardware register size constraints if configured
  if (hasConfig("REG_M")) {
      uint reg_m = getConfig("REG_M");
      uint reg_n = getConfig("REG_N");
      uint reg_k = getConfig("REG_K");
      if (tile_width != 1 || tile_height != 1) {
          if (src_reg == 0) { // %ra
              if (tile_width != reg_k || tile_height != reg_m) {
                  std::cerr << "Error: register %ra store dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_K x REG_M (" << reg_k << "x" << reg_m << ")\n";
                  exit(1);
              }
          } else if (src_reg == 1) { // %rb
              if (tile_width != reg_n || tile_height != reg_k) {
                  std::cerr << "Error: register %rb store dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_N x REG_K (" << reg_n << "x" << reg_k << ")\n";
                  exit(1);
              }
          } else if (src_reg == 2) { // %rc
              if (tile_width != reg_n || tile_height != reg_m) {
                  std::cerr << "Error: register %rc store dimensions (" << tile_width << "x" << tile_height 
                            << ") do not match hardware config REG_N x REG_M (" << reg_n << "x" << reg_m << ")\n";
                  exit(1);
              }
          }
      }
  }

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  std::ostringstream h;
  h << "tmov (0x" << std::hex << base_addr << std::dec << ", " << tile_width
    << ", " << tile_height << ", " << stride << ", " << elem_width << "), %r"
    << "abc"[src_reg];
  inst_header_ = h.str();

  for (uint row = 0; row < tile_height; ++row) {
    for (uint col = 0; col < tile_width; ++col) {
      Addr target = base_addr + (row * stride + col) * elem_width;

      doWrite(target, elem_width);
    }
  }
}

void Interpeter::handlePrefetch() {
  Addr base_addr;
  uint tile_width;
  uint tile_height;
  uint stride;
  uint elem_width;

  INTERPRETER_SYNTEX_CHECK('(', "opening parenthesis", "command name");

  in_stream_ >> std::hex >> base_addr;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "base address");

  in_stream_ >> std::dec >> tile_width;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile width");

  in_stream_ >> tile_height;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "tile height");

  in_stream_ >> stride;
  INTERPRETER_SYNTEX_CHECK(',', "comma", "stride");

  in_stream_ >> elem_width;

  INTERPRETER_SYNTEX_CHECK(')', "closing parenthesis", "source parameters");

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  std::ostringstream h;
  h << "prefetch (0x" << std::hex << base_addr << std::dec << ", " << tile_width
    << ", " << tile_height << ", " << stride << ", " << elem_width << ")";
  inst_header_ = h.str();

  for (uint row = 0; row < tile_height; ++row) {
    for (uint col = 0; col < tile_width; ++col) {
      Addr target = base_addr + (row * stride + col) * elem_width;
      doRead(target, elem_width);
    }
  }
}

// tmulac %ra, %rb, %rc -- pure register-file compute: the tiles were brought
// into the vector registers by ltea, so no memory traffic (and no cycle cost)
// happens here.
void Interpeter::handleMulAcc() {
  uint a = parseReg();
  uint b = parseReg();
  uint c = parseReg();

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  const vec_reg &ra = vec_regs_[a];
  const vec_reg &rb = vec_regs_[b];
  const vec_reg &rc = vec_regs_[c];

  if (ra.t_width != rb.t_height || rc.t_height != ra.t_height ||
      rc.t_width != rb.t_width) {
    std::cerr << "tmulac tile shape mismatch (" << ra.t_height << "x"
              << ra.t_width << ") * (" << rb.t_height << "x" << rb.t_width
              << ") -> (" << rc.t_height << "x" << rc.t_width
              << ") in line: " << line_ << std::endl;
    exit(1);
  }

  std::ostringstream h;
  h << "tmulac %r" << "abc"[a] << ", %r" << "abc"[b] << ", %r" << "abc"[c];
  inst_header_ = h.str();

  if (hasConfig("MULAC_CYCLES")) {
      cpu_cycles_ += getConfig("MULAC_CYCLES");
  }
}

void Interpeter::handleCmd() {
  cmd cur_cmd = readCmd();
  if (cur_cmd == eof) {
    return;
  }

  inst_header_.clear();
  inst_detail_.str("");
  const size_t cycles_before = cpu_cycles_;

  switch (cur_cmd) {
  case load_tile:
    handleTload();
    break;
  case move_tile:
    handleTmove();
    break;
  case mul_acc:
    handleMulAcc();
    break;
  case prefetch_tile:
    handlePrefetch();
    break;
  case eof:
    return;
  }

  if (trace_out_.is_open()) {
    trace_out_ << inst_header_ << "    # " << (cpu_cycles_ - cycles_before)
               << " cy\n"
               << inst_detail_.str();
  }

  ++line_;
}

Interpeter::cmd Interpeter::readCmd() {
  trim_prefix_spaces();

  std::string cmd;
  std::getline(in_stream_, cmd, ' ');

  if (cmd == "ltea") {
    return load_tile;
  } else if (cmd == "tmulac") {
    return mul_acc;
  } else if (cmd == "tmov") {
    return move_tile;
  } else if (cmd == "prefetch") {
    return prefetch_tile;
  } else if (in_stream_.eof()) {
    return eof;
  } else {
    std::cerr << "invalid command" << std::endl;
    exit(1);
  }
}

void Interpeter::trim_prefix_spaces() {
  while (in_stream_.peek() == ' ') {
    in_stream_.ignore();
  }
}
