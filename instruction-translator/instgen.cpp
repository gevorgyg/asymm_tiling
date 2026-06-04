#include "instgen.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>

const InstGenerator::Addr magic_addr = 0xFFFFF000;

InstGenerator::GhostMat::GhostMat(uint w, uint h, uint elem_w, Addr a)
    : width(w), height(h), elem_width(elem_w),
      total_elem_size(width * height),
      total_byte_size(width * height * elem_width), addr(a) {}

InstGenerator::InstGenerator(uint a_width, uint a_height, uint a_elem_width,
                             uint b_width, uint b_height, uint b_elem_width)
    : a_w_(a_width), a_h_(a_height), a_ew_(a_elem_width), b_w_(b_width),
      b_h_(b_height), b_ew_(b_elem_width) {
  if (a_width != b_height) {
    std::cerr << "invalid matrix dimensions for multiplication" << std::endl;
    exit(1);
  }
}

void InstGenerator::generate(TileShape ts, std::ostream &os) const {
  const Addr a_bytes = a_w_ * a_h_ * a_ew_;
  const Addr b_bytes = b_w_ * b_h_ * b_ew_;
  const uint c_ew = std::max(a_ew_, b_ew_);

  const GhostMat A{a_w_, a_h_, a_ew_, 0};
  const GhostMat B{b_w_, b_h_, b_ew_, a_bytes};
  const GhostMat C{a_h_, b_w_, c_ew, a_bytes + b_bytes};

  emitTrace(A, B, C, ts, os, false);
}

void InstGenerator::generatePrng(TileShape ts, std::ostream &os) const {
  const Addr a_bytes = a_w_ * a_h_ * a_ew_;
  const uint c_ew = std::max(a_ew_, b_ew_);

  const GhostMat A{a_w_, a_h_, a_ew_, 0};
  const GhostMat B{b_w_, b_h_, b_ew_, magic_addr};
  const GhostMat C{a_h_, b_w_, c_ew, a_bytes};

  emitTrace(A, B, C, ts, os, true);
}

void InstGenerator::emitTrace(const GhostMat &A, const GhostMat &B,
                              const GhostMat &C, TileShape tile,
                              std::ostream &os, bool prng) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  // Tile counts (ceil division so edge tiles aren't dropped).
  const uint M_tiles = (A.height + tile.m - 1) / tile.m;
  const uint N_tiles = (B.width  + tile.n - 1) / tile.n;
  const uint K_tiles = (A.width  + tile.k - 1) / tile.k;

  if (prng) {
    os << "strtrng 0x" << std::hex << B.addr << std::dec << std::endl;
  }

  for (uint ti = 0; ti < M_tiles; ++ti) {
    const uint cth = std::min(tile.m, A.height - ti * tile.m);

    for (uint tj = 0; tj < N_tiles; ++tj) {
      const uint ctw = std::min(tile.n, B.width - tj * tile.n);

      load(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        const uint atw = std::min(tile.k, A.width - tk * tile.k);

        load(os, A, ti * tile.m, tk * tile.k, atw, cth, a_id);

        if (prng) {
          // PRNG: B is the MMIO sentinel; same address every load, no offset.
          emit(os, "ltea", B.addr, ctw, atw, B.width, B.elem_width, b_id);
        } else {
          load(os, B, tk * tile.k, tj * tile.n, ctw, atw, b_id);
        }

        os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;
      }

      store(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);
    }
  }

  if (prng) {
    os << "stprng" << std::endl;
  }
}

InstGenerator::Addr InstGenerator::tileAddr(const GhostMat &M, uint row,
                                            uint col) {
  return M.addr + (row * M.width + col) * M.elem_width;
}

void InstGenerator::emit(std::ostream &os, const char *op, Addr addr, uint w,
                         uint h, uint stride, uint ew, const char *reg) {
  os << op << " (0x" << std::hex << addr << std::dec << ", " << w << ", " << h
     << ", " << stride << ", " << ew << "), " << reg << std::endl;
}

void InstGenerator::load(std::ostream &os, const GhostMat &M, uint row,
                         uint col, uint w, uint h, const char *reg) {
  emit(os, "ltea", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}

void InstGenerator::store(std::ostream &os, const GhostMat &M, uint row,
                          uint col, uint w, uint h, const char *reg) {
  emit(os, "tmov", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}
