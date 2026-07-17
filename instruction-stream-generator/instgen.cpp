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
      reg_m_(p.reg_m), reg_n_(p.reg_n), reg_k_(p.reg_k), seed_bytes_(p.seed_bytes),
      num_prefill_(p.num_prefill ? p.num_prefill : 1) {
  if (A_.width != B_.height) {
    std::cerr << "invalid matrix dimensions for multiplication" << std::endl;
    exit(1);
  }
}

static void checkTileDivides(const InstGenerator::GhostMat &A,
                              const InstGenerator::GhostMat &B,
                              const InstGenerator::TileShape ts) {
  if (A.height % ts.m != 0 || B.width % ts.n != 0 || A.width % ts.k != 0) {
    std::cerr << "matrix dimensions must be divisible by tile dimensions" << std::endl;
    exit(1);
  }
}

void InstGenerator::generate(TileShape ts, std::ostream &os, Dataflow df,
                             bool b_fifo, bool b_fifo_pipelined,
                             bool b_fifo_col_major) const {
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

  if (b_fifo_pipelined) {
    emitPipelinedBStationary(A_, B_, C, ts, os);
  } else if (b_fifo_col_major) {
    emitMultiLevelOutputStationaryColMajorFifo(A_, B_, C, ts, os);
  } else {
    emitTrace(A_, B_, C, ts, os, df, b_fifo);
  }
}

void InstGenerator::emitTrace(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                               TileShape tile, std::ostream &os,
                               Dataflow df, bool b_fifo) const {
  if (reg_m_ > 0) {
    switch (df) {
    case Dataflow::AStationary:
      emitMultiLevelAStationary(A, B, C, tile, os);
      break;
    case Dataflow::BStationary:
      emitMultiLevelBStationary(A, B, C, tile, os, b_fifo);
      break;
    case Dataflow::OutputStationary:
      emitMultiLevelOutputStationary(A, B, C, tile, os, b_fifo);
      break;
    }
  } else {
    switch (df) {
    case Dataflow::AStationary:
      emitSingleLevelAStationary(A, B, C, tile, os);
      break;
    case Dataflow::BStationary:
      emitSingleLevelBStationary(A, B, C, tile, os, b_fifo);
      break;
    case Dataflow::OutputStationary:
      emitSingleLevelOutputStationary(A, B, C, tile, os, b_fifo);
      break;
    }
  }
}

// ── Multi-level (3D-register) implementations ────────────────────────────────

// A-stationary: A reg-tile loaded into %ra; for each A, B columns cycle
// through L1; C is load/stored per (rti, rtj) sub-tile.
// FIFO is not supported: B column access is non-sequential with FIFO generation.
void InstGenerator::emitMultiLevelAStationary(const GhostMat &A, const GhostMat &B,
                                               const GhostMat &C, TileShape tile,
                                               std::ostream &os) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        // A outer: each A reg-tile is held in %ra across all B columns.
        for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
          for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
            load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                 reg_k_, reg_m_, a_id);

            for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
              load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_,
                   reg_n_, reg_k_, b_id);
              load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                   reg_n_, reg_m_, c_id);
              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
              store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                    reg_n_, reg_m_, c_id);
            }
          }
        }
      }
    }
  }
}

// B-stationary: B reg-tile loaded into %rb (from FIFO or L1); A rows cycle;
// C is load/stored per (rti, rtj) sub-tile.
void InstGenerator::emitMultiLevelBStationary(const GhostMat &A, const GhostMat &B,
                                               const GhostMat &C, TileShape tile,
                                               std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        if (b_fifo) emitFifoStart(os, tk, tj, N_tiles, b_id);

        // B outer: each B reg-tile is held in %rb across all A rows.
        for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
          for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
            if (b_fifo)
              emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
            else
              load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_,
                   reg_n_, reg_k_, b_id);

            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                   reg_k_, reg_m_, a_id);
              load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                   reg_n_, reg_m_, c_id);
              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
              store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                    reg_n_, reg_m_, c_id);
            }
          }
        }

        if (b_fifo) emitFifoStop(os, b_id);
      }
    }
  }
}

// Output-stationary: C reg-tile loaded into %rc ONCE and accumulated across
// ALL k; stored only after all k iterations. A and B stream each iteration.
//
// For FIFO: the full B tile is consumed on every (rti, rtj, tk) pass.
// Only the column matching the current rtj is used for tmulac; the others are
// consumed and discarded. This is the correct cost of OS with a sequential
// FIFO — it reflects the hardware overhead of regenerating B per C sub-tile.
void InstGenerator::emitMultiLevelOutputStationary(const GhostMat &A, const GhostMat &B,
                                                    const GhostMat &C, TileShape tile,
                                                    std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;
  const uint N_reg   = tile.n   / reg_n_;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      // C outer: process one C reg-sub-tile completely before moving to the next.
      for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
        for (uint rtj = 0; rtj < N_reg; ++rtj) {
          // Load C sub-tile once into %rc — it stays there for all k.
          load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
               reg_n_, reg_m_, c_id);

          for (uint tk = 0; tk < K_tiles; ++tk) {
            if (b_fifo) emitFifoStart(os, tk, tj, N_tiles, b_id);

            for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
              if (b_fifo) {
                // Consume the full B row (all N_reg sub-tiles) in order.
                // Only the rtj-th sub-tile contributes; the rest are discarded.
                for (uint rtj_consume = 0; rtj_consume < N_reg; ++rtj_consume) {
                  emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
                  if (rtj_consume == rtj) {
                    load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                         reg_k_, reg_m_, a_id);
                    os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
                  }
                }
              } else {
                load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_,
                     reg_n_, reg_k_, b_id);
                load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                     reg_k_, reg_m_, a_id);
                os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
              }
            }

            if (b_fifo) emitFifoStop(os, b_id);
          }

          // Store C sub-tile once after all k.
          store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                reg_n_, reg_m_, c_id);
        }
      }
    }
  }
}

// ── Single-level implementations ─────────────────────────────────────────────

// A-stationary single-level: A tile held across all B columns. Mem only.
void InstGenerator::emitSingleLevelAStationary(const GhostMat &A, const GhostMat &B,
                                                const GhostMat &C, TileShape tile,
                                                std::ostream &os) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        load(os, A, ti * tile.m, tk * tile.k, tile.k, tile.m, a_id);

        load(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k, b_id);
        load(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);
        os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
        store(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);
      }
    }
  }
}

// B-stationary single-level: B tile loaded once (or from FIFO per k-tile);
// all M rows consume it. K outer, N inner, M innermost.
void InstGenerator::emitSingleLevelBStationary(const GhostMat &A, const GhostMat &B,
                                                const GhostMat &C, TileShape tile,
                                                std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  for (uint tk = 0; tk < K_tiles; ++tk) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      if (b_fifo) {
        const Addr seed_mem_addr = B_.addr + (tk * N_tiles + tj) * seed_bytes_;
        emit(os, "ltea", seed_mem_addr, 1, 1, 1, seed_bytes_, b_id);
        emit(os, "tmov", SEED_REG,  1, 1, 1, seed_bytes_, b_id);
        emit(os, "tmov", START_REG, 1, 1, 1, seed_bytes_, b_id);
        emit(os, "ltea", DATA_REG, tile.n, tile.k, tile.n, B.elem_width, b_id);
      } else {
        load(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k, b_id);
      }

      for (uint ti = 0; ti < M_tiles; ++ti) {
        load(os, A, ti * tile.m, tk * tile.k, tile.k, tile.m, a_id);
        load(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);
        os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
        store(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);
      }

      if (b_fifo) emit(os, "tmov", STOP_REG, 1, 1, 1, seed_bytes_, b_id);
    }
  }
}

// Output-stationary single-level: C tile loaded once into %rc; A and B stream
// for all k; C stored once at the end. FIFO supported.
void InstGenerator::emitSingleLevelOutputStationary(const GhostMat &A, const GhostMat &B,
                                                     const GhostMat &C, TileShape tile,
                                                     std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      // C loaded once — lives in %rc for the entire k loop.
      load(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        load(os, A, ti * tile.m, tk * tile.k, tile.k, tile.m, a_id);

        if (b_fifo) {
          const Addr seed_mem_addr = B_.addr + (tk * N_tiles + tj) * seed_bytes_;
          emit(os, "ltea", seed_mem_addr, 1, 1, 1, seed_bytes_, b_id);
          emit(os, "tmov", SEED_REG,  1, 1, 1, seed_bytes_, b_id);
          emit(os, "tmov", START_REG, 1, 1, 1, seed_bytes_, b_id);
          emit(os, "ltea", DATA_REG, tile.n, tile.k, tile.n, B.elem_width, b_id);
        } else {
          load(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k, b_id);
        }

        os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";

        if (b_fifo) emit(os, "tmov", STOP_REG, 1, 1, 1, seed_bytes_, b_id);
      }

      // Store C once after all k.
      store(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m, c_id);
    }
  }
}

// ── Pipelined-prefill B-stationary ───────────────────────────────────────────

void InstGenerator::emitPipelinedBStationary(
    const GhostMat &A, const GhostMat &B, const GhostMat &C,
    TileShape tile, std::ostream &os) const
{
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  constexpr Addr PREF_SEED_REG  = 0xFF200000;
  constexpr Addr PREF_START_REG = 0xFF200004;
  constexpr Addr SWAP_REG       = 0xFF200008;
  constexpr Addr STOP_REG       = 0xFF20000C;
  constexpr Addr DATA_REG_P     = 0xFF200010;

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;
  const uint total   = M_tiles * N_tiles * K_tiles;

  auto seedAddrLin = [&](uint lin) -> Addr {
    const uint tk = lin % K_tiles;
    const uint tj = (lin / K_tiles) % N_tiles;
    return B.addr + (tk * N_tiles + tj) * seed_bytes_;
  };

  for (uint p = 0; p < num_prefill_ && p < total; ++p) {
    emit(os, "ltea", seedAddrLin(p), 1, 1, 1, seed_bytes_, b_id);
    emit(os, "tmov", PREF_SEED_REG,  1, 1, 1, seed_bytes_, b_id);
    emit(os, "tmov", PREF_START_REG, 1, 1, 1, seed_bytes_, b_id);
  }

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      for (uint tk = 0; tk < K_tiles; ++tk) {
        emit(os, "tmov", SWAP_REG, 1, 1, 1, seed_bytes_, b_id);

        const uint lin      = ti * (N_tiles * K_tiles) + tj * K_tiles + tk;
        const uint next_lin = lin + num_prefill_;
        if (next_lin < total) {
          emit(os, "ltea", seedAddrLin(next_lin), 1, 1, 1, seed_bytes_, b_id);
          emit(os, "tmov", PREF_SEED_REG,         1, 1, 1, seed_bytes_, b_id);
          emit(os, "tmov", PREF_START_REG,        1, 1, 1, seed_bytes_, b_id);
        }

        emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

        for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
          for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
            emit(os, "ltea", DATA_REG_P, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);

            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                   reg_k_, reg_m_, a_id);
              load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                   reg_n_, reg_m_, c_id);
              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
              store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                    reg_n_, reg_m_, c_id);
            }
          }
        }
      }
    }
  }

  emit(os, "tmov", STOP_REG, 1, 1, 1, seed_bytes_, b_id);
}

// ── Column-major output-stationary FIFO ──────────────────────────────────────
//
// True C-stationary: C in %rc across ALL k for each (rti, rtj). The FIFO is
// assumed to generate the full B tile in column-major order (software convention,
// no new hardware). One START per rti covers all N_reg columns; rtj iterates
// inside consuming columns sequentially with no restart between them.
//
// Row-major output-stationary discards N_reg-1 sub-tiles per rtk (ghost reads).
// Here every consumed element is used for mulacc.
//
// Restarts: M_reg per output tile (one per rti), vs M_reg × N_reg × K_tiles
// for row-major. No ghost reads.
void InstGenerator::emitMultiLevelOutputStationaryColMajorFifo(
    const GhostMat &A, const GhostMat &B, const GhostMat &C,
    TileShape tile, std::ostream &os) const
{
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;
  const uint N_reg   = tile.n   / reg_n_;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
        // One START per rti: FIFO generates full B tile in col-major order
        // (rtj=0 all k, rtj=1 all k, ...). rtj iterates inside consuming
        // columns sequentially — no restart between columns, only per rti.
        emitFifoStart(os, 0, tj, N_tiles, b_id);

        for (uint rtj = 0; rtj < N_reg; ++rtj) {
          // C held in %rc across all k — true C-stationary.
          load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
               reg_n_, reg_m_, c_id);

          for (uint tk = 0; tk < K_tiles; ++tk) {
            for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
              emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
                   reg_k_, reg_m_, a_id);
              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
            }
          }

          store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
                reg_n_, reg_m_, c_id);
        }

        emitFifoStop(os, b_id);
      }
    }
  }
}

// ── PRNG-FIFO helpers ─────────────────────────────────────────────────────────

void InstGenerator::emitFifoStart(std::ostream &os, uint tk, uint tj, uint n_tiles,
                                  const char *reg) const {
  const Addr seed_mem_addr = B_.addr + (tk * n_tiles + tj) * seed_bytes_;
  emit(os, "ltea", seed_mem_addr, 1, 1, 1, seed_bytes_, reg);
  emit(os, "tmov", SEED_REG, 1, 1, 1, seed_bytes_, reg);
  emit(os, "tmov", START_REG, 1, 1, 1, seed_bytes_, reg);
}

void InstGenerator::emitFifoStop(std::ostream &os, const char *reg) const {
  emit(os, "tmov", STOP_REG, 1, 1, 1, seed_bytes_, reg);
}

// ── Address and instruction helpers ──────────────────────────────────────────

Addr InstGenerator::tileAddr(const GhostMat &M, uint row, uint col) const {
  return M.addr + (row * M.width + col) * M.elem_width;
}

void InstGenerator::emit(std::ostream &os, const char *op, Addr addr, uint w,
                         uint h, uint stride, uint ew, const char *reg) const {
  os << op << " (0x" << std::hex << addr << std::dec << ", " << w << ", " << h
     << ", " << stride << ", " << ew << "), " << reg << "\n";
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
     << w << ", " << h << ", " << M.width << ", " << M.elem_width << ")\n";
}
