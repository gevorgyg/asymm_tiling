#include "interpeter.h"
#include "instgen.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

using std::filesystem::path;

const int block_size = 6;

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

Interpeter::Interpeter(path input_file, MemoryHierarchy &mem)
    : in_stream_(input_file), line_(0), prng_dev_(total_cycles_), mem_(mem) {
  if (!in_stream_.is_open()) {
    std::cerr << "error opening trace file" << std::endl;
    exit(1);
  }
}

void Interpeter::doRead(Addr addr) {
  Trace t = mem_.read(addr, 1);
  total_cycles_ += totalCycles(t);
}

void Interpeter::doWrite(Addr addr) {
  Trace t = mem_.write(addr, 1);
  total_cycles_ += totalCycles(t);
}

void Interpeter::run() {
  while (!in_stream_.eof()) {
    handleCmd();
  }
}

void Interpeter::stall(size_t amount) { total_cycles_ += amount; }

void Interpeter::handleTload() {
  Addr base_addr;
  uint tile_width;
  uint tile_height;
  uint stride;
  uint elem_width;
  uint dst_reg;

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

  std::string reg_name;
  in_stream_ >> reg_name;

  if (reg_name == "%ra") {
    dst_reg = 0;
  } else if (reg_name == "%rb") {
    dst_reg = 1;
  } else if (reg_name == "%rc") {
    dst_reg = 2;
  } else {
    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
  }

  vec_regs_[dst_reg] = {base_addr, tile_width, tile_height, stride, elem_width};

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  if (base_addr == magic_addr_) {
    prng_dev_.reseed();
    return;
  }

  for (int row = 0; row < tile_height; ++row) {
    for (int col = 0; col < tile_width; ++col) {
      long target = base_addr + (row * stride + col) * elem_width;

      doRead(target);
    }
  }
}

void Interpeter::handleTmove() {
  Addr base_addr;
  uint tile_width;
  uint tile_height;
  uint stride;
  uint elem_width;
  uint dst_reg;

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

  std::string reg_name;
  in_stream_ >> reg_name;

  if (reg_name == "%ra") {
    dst_reg = 0;
  } else if (reg_name == "%rb") {
    dst_reg = 1;
  } else if (reg_name == "%rc") {
    dst_reg = 2;
  } else {
    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
  }

  vec_regs_[dst_reg] = {base_addr, tile_width, tile_height, stride, elem_width};

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  for (int row = 0; row < tile_height; ++row) {
    for (int col = 0; col < tile_width; ++col) {
      long target = base_addr + (row * stride + col) * elem_width;

      doWrite(target);
    }
  }
}

// tmulac <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
void Interpeter::handleMulAcc() {
  int tile_1;
  int tile_2;
  int tile_3;

  std::string reg_name;
  in_stream_ >> reg_name;
  if (reg_name.back() == ',') {
    reg_name.pop_back();
  } else {
    std::cerr << "missing ',' after first register in line: " << line_
              << std::endl;
    exit(1);
  }

  if (reg_name == "%ra") {
    tile_1 = 0;
  } else if (reg_name == "%rb") {
    tile_1 = 1;
  } else if (reg_name == "%rc") {
    tile_1 = 2;
  } else {
    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
  }

  in_stream_ >> reg_name;
  if (reg_name.back() == ',') {
    reg_name.pop_back();
  } else {
    std::cerr << "missing ',' after first register in line: " << line_
              << std::endl;
    exit(1);
  }

  if (reg_name == "%ra") {
    tile_2 = 0;
  } else if (reg_name == "%rb") {
    tile_2 = 1;
  } else if (reg_name == "%rc") {
    tile_2 = 2;
  } else {
    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
  }

  in_stream_ >> reg_name;

  if (reg_name == "%ra") {
    tile_3 = 0;
  } else if (reg_name == "%rb") {
    tile_3 = 1;
  } else if (reg_name == "%rc") {
    tile_3 = 2;
  } else {
    std::cerr << "invalid register in line: " << line_ << std::endl;
    exit(1);
  }

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");

  const vec_reg &ra = vec_regs_[tile_1];
  const vec_reg &rb = vec_regs_[tile_2];
  const vec_reg &rc = vec_regs_[tile_3];

  bool use_magic = rb.base_addr == magic_addr_ ? true : false;
  bool ok = false;

  for (int a_row = 0; a_row < ra.t_height; ++a_row) {
    for (int b_col = 0; b_col < rb.t_width; ++b_col) {
      Addr target_c =
          rc.base_addr + (a_row * rc.stride + b_col) * rc.elem_width;

      for (int t = 0; t < ra.t_width; ++t) {
        Addr target_a = ra.base_addr + (a_row * ra.stride + t) * ra.elem_width;
        if (use_magic) {
          prng_dev_.pop();
        } else {
          Addr target_b =
              rb.base_addr + (t * rb.stride + b_col) * rb.elem_width;
          doRead(target_b);
        }

        doRead(target_a);
        // multiply A and B
      }

      doRead(target_c);
      doWrite(target_c);
      // accumulate in C
    }
  }
}

void Interpeter::startRng() {
  in_stream_ >> std::hex >> magic_addr_ >> seed_reg_;

  if (magic_addr_ == 0) {
    std::cerr << "invalid MMIO magic address in line: " << line_ << std::endl;
    exit(1);
  }

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
}

void Interpeter::stopRng() {
  magic_addr_ = 0;

  INTERPRETER_SYNTEX_CHECK('\n', "new line", "line");
}

void Interpeter::handleCmd() {
  cmd cur_cmd = readCmd();

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
  case start_rng:
    startRng();
    break;
  case stop_rng:
    stopRng();
    break;
  case eof:
    return;
    break;
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
  } else if (cmd == "strtrng") {
    return start_rng;
  } else if (cmd == "stprng") {
    return stop_rng;
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

constexpr char instruction_path[] = "./matmul.matv";

void generateInstructions(int m, int n, int k) {
  InstGenerator::GhostMat A{500, 500, 8, 0};
  InstGenerator::GhostMat B{500, 500, 1, (uint)A.total_byte_size};
  InstGenerator gen{A, B};

  std::ofstream ofs(instruction_path);

  if (!ofs.is_open()) {
    std::cerr << "error opening file" << std::endl;
  }

  InstGenerator::TileShape tile{(unsigned)m, (unsigned)n, (unsigned)k};
  gen.generate(tile, ofs);
}

void generatePrngInstructions(int m, int n, int k) {
  InstGenerator::GhostMat A{500, 500, 8, 0};
  InstGenerator::GhostMat B{500, 500, 1, 0};
  InstGenerator gen{A, B};

  std::ofstream ofs(instruction_path);

  if (!ofs.is_open()) {
    std::cerr << "error opening file" << std::endl;
  }

  InstGenerator::TileShape tile{(unsigned)m, (unsigned)n, (unsigned)k};
  gen.generatePrng(tile, ofs);
}

int main(int argc, char *argv[]) {

  bool b_generated = false;
  uint dims[3];
  int positional = 0;

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--Bgenerated") {
      b_generated = true;
    } else if (positional < 3) {
      dims[positional++] = std::atoi(argv[i]);
    } else {
      std::cerr << "unexpected argument: " << arg << std::endl;
      exit(1);
    }
  }

  if (positional != 3) {
    std::cerr << "usage: " << argv[0] << " [--Bgenerated] <m> <n> <k>"
              << std::endl;
    exit(1);
  }

  // Translation of the legacy Simulator config:
  //   block_size=6 -> line_size=2^6=64
  //   l1_size=15   -> 2^15=32768 bytes
  //   l1_assoc=2   -> 2^2=4 ways
  //   l1_cycles=4
  //   mem_cycles=180
  // L2 from the original (size=2^18, cycles=24) is not modelled in the new
  // MemoryHierarchy yet -- a single L1 + main memory for now.
  MemoryHierarchy::Parameters mp{
      .l1               = {.name      = "L1",
                           .size      = 1u << 15,
                           .line_size = 1u << block_size,
                           .assoc     = 1u << 2},
      .l1_access_cycles = 4,
      .mem_access_cycles = 180,
  };
  MemoryHierarchy mem(mp);

  if (b_generated) {
    generatePrngInstructions(dims[0], dims[1], dims[2]);
  } else {
    generateInstructions(dims[0], dims[1], dims[2]);
  }

  Interpeter inter(instruction_path, mem);

  std::cout << "----------------------------" << std::endl;

  std::cout << dims[0] << ' ' << dims[1] << ' ' << dims[2] << std::endl;

  std::cout << "----------------------------" << std::endl;

  inter.run();

  const size_t l1_hits   = mem.l1Hits();
  const size_t l1_misses = mem.l1Misses();
  const size_t l1_total  = l1_hits + l1_misses;
  const double hit_rate  = l1_total ? (double)l1_hits / (double)l1_total : 0.0;

  printf("--- L1 ---\n");
  printf("Hit rate:  %.03f\n", hit_rate);
  printf("TagLookup: %llu\n", (unsigned long long)Cache::TagLookup::count_);
  printf("LineFill:  %llu\n", (unsigned long long)Cache::LineFill::count_);
  printf("Evict:     %llu\n", (unsigned long long)Cache::Evict::count_);

  return 0;
};
