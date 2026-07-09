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
      reg_m_(p.reg_m), reg_n_(p.reg_n), reg_k_(p.reg_k), seed_bytes_(p.seed_bytes) {
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

void InstGenerator::generate(TileShape ts, std::ostream &os, bool b_stationary, bool b_fifo,
                             bool b_fifo_pipelined) const {
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
    emitTraceMultiLevelCStationaryOuterProductsPipelined(A_, B_, C, ts, os);
  } else {
    emitTrace(A_, B_, C, ts, os, b_stationary, b_fifo);
  }
}

void InstGenerator::emitTrace(const GhostMat &A, const GhostMat &B,
                              const GhostMat &C, TileShape tile,
                              std::ostream &os, bool b_stationary, bool b_fifo) const {
  if (reg_m_ > 0) {
    if (b_stationary) {
      emitTraceMultiLevelBStationary(A, B, C, tile, os, b_fifo);
    } else {
      emitTraceMultiLevelCStationary(A, B, C, tile, os, b_fifo);
    }
  } else {
    if (b_stationary) {
      emitTraceSingleLevelBStationary(A, B, C, tile, os, b_fifo);
    } else {
      emitTraceSingleLevelCStationary(A, B, C, tile, os, b_fifo);
    }
  }
}

void InstGenerator::emitFifoStart(std::ostream &os, uint tk, uint tj, uint n_tiles,
                                  const char *reg) const {
  const Addr seed_mem_addr = B_.addr + (tk * n_tiles + tj) * seed_bytes_;
  emit(os, "ltea", seed_mem_addr, 1, 1, 1, seed_bytes_, reg);  // fetch seed from storage
  emit(os, "tmov", SEED_REG, 1, 1, 1, seed_bytes_, reg);       // hand seed to device
  emit(os, "tmov", START_REG, 1, 1, 1, seed_bytes_, reg);      // begin generation
}

void InstGenerator::emitFifoStop(std::ostream &os, const char *reg) const {
  emit(os, "tmov", STOP_REG, 1, 1, 1, seed_bytes_, reg);
}

// C-stationary: prefetch the C tile, then for each k-slice stream an A
// subcolumn against B subrows as rank-1 updates. M outermost. Under FIFO,
// B is regenerated on every pass (no cache to reuse it from).
void InstGenerator::emitTraceMultiLevelCStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                                  TileShape tile, std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width / tile.n;
  const uint K_tiles = A.width / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        if (b_fifo) emitFifoStart(os, tk, tj, N_tiles, b_id);

        for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
          if (b_fifo) {
            // FIFO path: B outer, A inner — each FIFO element consumed exactly once.
            for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
              emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
              for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
                load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
                load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
                os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;
                store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
              }
            }
          } else {
            // Mem path: A outer, B inner — B hits in L1 across the rti loop.
            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
              for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
                load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_, reg_n_, reg_k_, b_id);
                load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
                os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;
                store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
              }
            }
          }
        }

        if (b_fifo) emitFifoStop(os, b_id);
      }
    }
  }
}

// B-stationary mirror: prefetch one B tile (or, under FIFO, generate each B
// subtile exactly once) and reuse it across the whole M stream while C
// accumulates across k. N outermost.
void InstGenerator::emitTraceMultiLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                                  TileShape tile, std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width / tile.n;
  const uint K_tiles = A.width / tile.k;

  for (uint tj = 0; tj < N_tiles; ++tj) {
    for (uint tk = 0; tk < K_tiles; ++tk) {
      if (b_fifo) emitFifoStart(os, tk, tj, N_tiles, b_id);
      else        emitPrefetch(os, B, tk * tile.k, tj * tile.n, tile.n, tile.k);

      for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
        for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
          // Bring this B subtile in once; reuse it across the entire M stream.
          if (b_fifo) emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);
          else        load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_, reg_n_, reg_k_, b_id);

          for (uint ti = 0; ti < M_tiles; ++ti) {
            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
              load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);

              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

              store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
            }
          }
        }
      }

      if (b_fifo) emitFifoStop(os, b_id);
    }
  }
}

void InstGenerator::emitTraceSingleLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                                   TileShape tile, std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  constexpr Addr START_REG = 0xFF000000;
  constexpr Addr SEED_REG  = 0xFF000004;
  constexpr Addr DATA_REG  = 0xFF000008;
  constexpr Addr STOP_REG  = 0xFF00000C;

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width / tile.n;
  const uint K_tiles = A.width / tile.k;

  for (uint tk = 0; tk < K_tiles; ++tk) {
    const uint atw = std::min(tile.k, A.width - tk * tile.k);

    for (uint tj = 0; tj < N_tiles; ++tj) {
      const uint ctw = std::min(tile.n, B.width - tj * tile.n);

      if (b_fifo) {
        Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
        emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
        emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
        emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
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
        emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
      }
    }
  }
}

void InstGenerator::emitTraceSingleLevelCStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                                   TileShape tile, std::ostream &os, bool b_fifo) const {
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  constexpr Addr START_REG = 0xFF000000;
  constexpr Addr SEED_REG  = 0xFF000004;
  constexpr Addr DATA_REG  = 0xFF000008;
  constexpr Addr STOP_REG  = 0xFF00000C;

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width / tile.n;
  const uint K_tiles = A.width / tile.k;

  for (uint ti = 0; ti < M_tiles; ++ti) {
    const uint cth = std::min(tile.m, A.height - ti * tile.m);

    for (uint tj = 0; tj < N_tiles; ++tj) {
      const uint ctw = std::min(tile.n, B.width - tj * tile.n);

      load(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);

      for (uint tk = 0; tk < K_tiles; ++tk) {
        const uint atw = std::min(tile.k, A.width - tk * tile.k);

        load(os, A, ti * tile.m, tk * tile.k, atw, cth, a_id);

        if (b_fifo) {
          Addr seed_mem_addr = B.addr + (tk * N_tiles + tj) * 8;
          emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, b_id);
          emit(os, "tmov", SEED_REG, 1, 1, 1, 8, b_id);
          emit(os, "tmov", START_REG, 1, 1, 1, 8, b_id);
          emit(os, "ltea", DATA_REG, ctw, atw, ctw, B.elem_width, b_id);
        } else {
          load(os, B, tk * tile.k, tj * tile.n, ctw, atw, b_id);
        }

        os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

        if (b_fifo) {
          emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
        }
      }

      store(os, C, ti * tile.m, tj * tile.n, ctw, cth, c_id);
    }
  }
}

void InstGenerator::emitTraceMultiLevelCStationaryOuterProductsPipelined(
    const GhostMat &A, const GhostMat &B, const GhostMat &C,
    TileShape tile, std::ostream &os) const
{
  constexpr char a_id[] = "%ra";
  constexpr char b_id[] = "%rb";
  constexpr char c_id[] = "%rc";

  // Pipelined FIFO device MMIO addresses (separate from the non-pipelined FIFO).
  constexpr Addr PREF_SEED_REG  = 0xFF200000;
  constexpr Addr PREF_START_REG = 0xFF200004;
  constexpr Addr SWAP_REG       = 0xFF200008;
  constexpr Addr STOP_REG       = 0xFF20000C;
  constexpr Addr DATA_REG       = 0xFF200010;

  const uint M_tiles = A.height / tile.m;
  const uint N_tiles = B.width  / tile.n;
  const uint K_tiles = A.width  / tile.k;

  // Helper: seed address for tile (ti, tj, tk) — same scheme as other emitters.
  auto seedAddr = [&](uint ti, uint tj, uint tk) -> Addr {
    (void)ti;   // ti is not part of the PRNG session index in this scheme
    return B.addr + (tk * N_tiles + tj) * 8;
  };

  // Bootstrap: start pre-generating tile (0,0,0) before the loop.
  // The window between PREF_START and the first SWAP is small (just the
  // seed-load instructions), but every subsequent tile gets a full previous-
  // session worth of prefill time.
  {
    emit(os, "ltea", seedAddr(0, 0, 0), 1, 1, 1, 8, b_id);
    emit(os, "tmov", PREF_SEED_REG, 1, 1, 1, 8, b_id);
    emit(os, "tmov", PREF_START_REG, 1, 1, 1, 8, b_id);
  }

  for (uint ti = 0; ti < M_tiles; ++ti) {
    for (uint tj = 0; tj < N_tiles; ++tj) {
      for (uint tk = 0; tk < K_tiles; ++tk) {
        // SWAP: make the pre-generated elements for this session available.
        emit(os, "tmov", SWAP_REG, 1, 1, 1, 8, b_id);

        // Immediately start pre-generating the NEXT session so it runs
        // concurrently with this session's computation.
        bool is_last = (ti == M_tiles - 1 && tj == N_tiles - 1 && tk == K_tiles - 1);
        if (!is_last) {
          uint nti = ti, ntj = tj, ntk = tk + 1;
          if (ntk == K_tiles) { ntk = 0; ++ntj; }
          if (ntj == N_tiles) { ntj = 0; ++nti; }
          emit(os, "ltea", seedAddr(nti, ntj, ntk), 1, 1, 1, 8, b_id);
          emit(os, "tmov", PREF_SEED_REG, 1, 1, 1, 8, b_id);
          emit(os, "tmov", PREF_START_REG, 1, 1, 1, 8, b_id);
        }

        // C-tile prefetch: its cycles add to the prefill window for this
        // session's data (the prefill is already running after PREF_START above).
        emitPrefetch(os, C, ti * tile.m, tj * tile.n, tile.n, tile.m);

        // Inner computation: B elements from the pipelined DATA_REG.
        for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
          for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
            emit(os, "ltea", DATA_REG, reg_n_, reg_k_, reg_n_, B.elem_width, b_id);

            for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
              load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_, reg_k_, reg_m_, a_id);
              load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
              os << "tmulac " << a_id << ", " << b_id << ", " << c_id << "\n";
              store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_, reg_n_, reg_m_, c_id);
            }
          }
        }
      }
    }
  }

  emit(os, "tmov", STOP_REG, 1, 1, 1, 8, b_id);
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
