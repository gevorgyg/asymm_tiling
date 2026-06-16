#include "instgen.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>

InstGenerator::GhostMat::GhostMat(uint w, uint h, uint elem_w, Addr a)
    : width(w), height(h), elem_width(elem_w),
      total_byte_size(width * height * elem_width), addr(a) {}

InstGenerator::InstGenerator(Params p)
    : A_(p.a_width, p.a_height, p.a_precision, 0),
      B_(p.b_width, p.a_width, p.b_precision, A_.total_byte_size),
      reg_m_(p.reg_m), reg_n_(p.reg_n), reg_k_(p.reg_k) {
  if (A_.width != B_.height) {
    std::cerr << "invalid matrix dimensions for multiplication" << std::endl;
    exit(1);
  }
}

void checkTileDivides(const InstGenerator::GhostMat &A,
                             const InstGenerator::GhostMat &B,
                            const InstGenerator::TileShape ts) {
  if (A.height % ts.m != 0 || B.width % ts.n != 0 || A.width % ts.k != 0) {
    std::cerr << "matrix dimensions must be divisible by tile dimensions"
              << std::endl;
    exit(1);
  }
}

void InstGenerator::generate(TileShape ts, std::ostream &os, bool b_stationary, bool b_fifo) const {
  checkTileDivides(A_, B_, ts);

  if (reg_m_ > 0) {
    if (ts.m % reg_m_ != 0 || ts.n % reg_n_ != 0 || ts.k % reg_k_ != 0) {
      std::cerr << "cache tile dimensions must be divisible by register tile dimensions"
                << std::endl;
      exit(1);
    }
  }

  const uint c_ew = std::max(A_.elem_width, B_.elem_width);
  const Addr c_addr = A_.addr + A_.total_byte_size + B_.total_byte_size;

  const GhostMat C{B_.width, A_.height, c_ew, c_addr};

  emitTrace(A_, B_, C, ts, os, b_stationary, b_fifo);
}

void InstGenerator::emitTrace(const GhostMat &A, const GhostMat &B,
                              const GhostMat &C, TileShape tile,
                              std::ostream &os, bool b_stationary, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  constexpr Addr START_REG = 0xFF000000;
  constexpr Addr SEED_REG  = 0xFF000004;
  constexpr Addr DATA_REG  = 0xFF000008;
  constexpr Addr STOP_REG  = 0xFF00000C;

  // Tile counts (ceil division so edge tiles aren't dropped).
  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width / tile.n;
  const uint K_tiles = A.width / tile.k;

  if (reg_m_ > 0) {
    // --- MULTI-LEVEL TILING (Cache + Register Tiling) ---
    if (b_stationary) {
      for (uint tk = 0; tk < K_tiles; ++tk) {
        for (uint tj = 0; tj < N_tiles; ++tj) {
          if (!b_fifo) {
            emitPrefetch(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k);
          } else {
            // FIFO Mode: Load seed and start generator for B cache tile
            Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
            emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
            emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
            emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
          }

          // Register loops for stationary B tile
          for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
            for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
              // Load B register tile
              if (!b_fifo) {
                load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_, reg_n_, reg_k_, b_id);
              } else {
                emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
              }

              // Loop over A/C cache and register tiles
              for (uint ti = 0; ti < M_tiles; ++ti) {
                emitPrefetch(os, A, ti * tile.m, tk * tile.k, tile.k, tile.m);
                emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

                for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
                  load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
                  load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);

                  os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

                  store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
                }
              }
            }
          }

          if (b_fifo) {
            emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
          }
        }
      }
    } else {
      // C-Stationary
      for (uint ti = 0; ti < M_tiles; ++ti) {
        for (uint tj = 0; tj < N_tiles; ++tj) {
          // Prefetch C cache tile
          emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

          for (uint tk = 0; tk < K_tiles; ++tk) {
            emitPrefetch(os, A, ti * tile.m, tk * tile.k, tile.k, tile.m);
            if (!b_fifo) {
              emitPrefetch(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k);
            } else {
              // FIFO Mode: Load seed and start generator for B cache tile
              Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
              emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
              emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
              emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
            }

            // Register loops
            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
                // Load C register tile from cache
                load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);

                for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
                  load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
                  if (!b_fifo) {
                    load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_, reg_n_, reg_k_, b_id);
                  } else {
                    emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
                  }

                  os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;
                }

                // Store C register tile back to cache
                store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
              }
            }

            if (b_fifo) {
              emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
            }
          }
        }
      }
    }
  } else {
    // --- SINGLE-LEVEL TILING (Original Behavior) ---
    if (b_stationary) {
      for (uint tk = 0; tk < K_tiles; ++tk) {
        const uint atw = std::min(tile.k, A.width - tk * tile.k);

        for (uint tj = 0; tj < N_tiles; ++tj) {
          const uint ctw = std::min(tile.n, B.width - tj * tile.n);

          if (b_fifo) {
            // Load seed for tile (tk, tj) from Matrix B space
            Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
            emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
            // Write seed to seed register
            emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
            // Write start command to control register
            emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
            // Load B elements from the FIFO streaming register
            emit(os, "ltea", DATA_REG, ctw, atw, ctw, B.elem_width, b_id);
          } else {
            load(os, B, tk * tile.k, tj * tile.n, ctw, atw, b_id);
          }

          for (uint ti = 0; ti < M_tiles; ++ti) {
            const uint cth = std::min(tile.m, A.height - ti * tile.m);

            load(os, A, ti * tile.m, tk * tile.k, atw, cth, a_id);

            load(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);

            os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

            store(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);
          }

          if (b_fifo) {
            // Write stop command to control register
            emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
          }
        }
      }
    } else {
      for (uint ti = 0; ti < M_tiles; ++ti) {
        const uint cth = std::min(tile.m, A.height - ti * tile.m);

        for (uint tj = 0; tj < N_tiles; ++tj) {
          const uint ctw = std::min(tile.n, B.width - tj * tile.n);

          load(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);

          for (uint tk = 0; tk < K_tiles; ++tk) {
            const uint atw = std::min(tile.k, A.width - tk * tile.k);

            load(os, A, ti * tile.m, tk * tile.k, atw, cth, a_id);

            if (b_fifo) {
              // Load seed for tile (tk, tj) from Matrix B space
              Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
              emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
              // Write seed to seed register
              emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
              // Write start command to control register
              emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
              // Load B elements from the FIFO streaming register
              emit(os, "ltea", DATA_REG, ctw, atw, ctw, B.elem_width, b_id);
            } else {
              load(os, B, tk * tile.k, tj * tile.n, ctw, atw, b_id);
            }

            os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

            if (b_fifo) {
              // Write stop command to control register
              emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
            }
          }

          store(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);
        }
      }
    }
  }
}

Addr InstGenerator::tileAddr(const GhostMat &M, uint row,
                             uint col) const {
  return M.addr + (row * M.width + col) * M.elem_width;
}

void InstGenerator::emit(std::ostream &os, const char *op, Addr addr, uint w,
                         uint h, uint stride, uint ew, const char *reg) const {
  os << op << " (0x" << std::hex << addr << std::dec << ", " << w << ", " << h
     << ", " << stride << ", " << ew << "), " << reg << std::endl;
}

void InstGenerator::load(std::ostream &os, const GhostMat &M, uint row,
                         uint col, uint w, uint h, const char *reg) const {
  emit(os, "ltea", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}

void InstGenerator::store(std::ostream &os, const GhostMat &M, uint row,
                          uint col, uint w, uint h, const char *reg) const {
  emit(os, "tmov", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}

void InstGenerator::emitPrefetch(std::ostream &os, const GhostMat &M, uint row,
                                 uint col, uint w, uint h) const {
  os << "prefetch (0x" << std::hex << tileAddr(M, row, col) << std::dec << ", "
     << w << ", " << h << ", " << M.width << ", " << M.elem_width << ")" << std::endl;
}
