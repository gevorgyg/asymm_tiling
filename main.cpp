#include "instruction-stream-generator/instgen.h"
#include "interpreter/interpeter.h"
#include "memory-system/cache/cache.h"
#include "memory-system/hierarchy.h"
#include "utils.h"

#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>

constexpr char instruction_path[] = "./matmul.matv";

void generateInstructions(uint m, uint n, uint k) {
  InstGenerator::GhostMat A{100, 100, 8, 0};
  InstGenerator::GhostMat B{100, 100, 2, (uint)A.total_byte_size};
  InstGenerator gen{A, B};

  std::ofstream ofs(instruction_path);

  if (!ofs.is_open()) {
    std::cerr << "error opening file" << std::endl;
  }

  InstGenerator::TileShape tile{m, n, k};
  gen.generate(tile, ofs);
}

void generatePrngInstructions(uint m, uint n, uint k) {
  InstGenerator::GhostMat A{100, 100, 8, 0};
  InstGenerator::GhostMat B{100, 100, 2, 0};
  InstGenerator gen{A, B};

  std::ofstream ofs(instruction_path);

  if (!ofs.is_open()) {
    std::cerr << "error opening file" << std::endl;
  }

  InstGenerator::TileShape tile{m, n, k};
  gen.generatePrng(tile, ofs);
}

int main(int argc, char *argv[]) {

  bool b_generated = false;
  uint dims[3];
  int positional = 0;
  std::string trace_file_path;

  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--Bgenerated") {
      b_generated = true;
    } else if (arg == "--trace_file") {
      if (i + 1 >= argc) {
        std::cerr << "--trace_file requires a filename" << std::endl;
        exit(1);
      }
      trace_file_path = argv[++i];
    } else if (positional < 3) {
      dims[positional++] = std::atoi(argv[i]);
    } else {
      std::cerr << "unexpected argument: " << arg << std::endl;
      exit(1);
    }
  }

  if (positional != 3) {
    std::cerr << "usage: " << argv[0]
              << " [--Bgenerated] [--trace_file <file>] <m> <n> <k>"
              << std::endl;
    exit(1);
  }

  // L2 is not modelled yet -- a single L1 + main memory for now
  MemoryHierarchy::Parameters mp{
      .l1               = {.name      = "L1",
                           .size      = 1u << 8,
                           .line_size = 1u << 4,
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

  Interpeter inter(instruction_path, mem, trace_file_path);

  std::cout << "----------------------------" << std::endl;

  std::cout << dims[0] << ' ' << dims[1] << ' ' << dims[2] << std::endl;

  std::cout << "----------------------------" << std::endl;

  inter.run();

  const Cache::Stats& s = mem.l1().stats();
  const size_t total    = s.hits + s.misses;
  const double hit_rate = total ? (double)s.hits / (double)total : 0.0;

  printf("--- %s ---\n", mem.l1().name());
  printf("Hit rate:  %.03f\n", hit_rate);
  printf("TagLookup: %llu\n", (unsigned long long)s.tag_lookups);
  printf("LineFill:  %llu\n", (unsigned long long)s.line_fills);
  printf("Evict:     %llu\n", (unsigned long long)s.evicts);

  return 0;
}
