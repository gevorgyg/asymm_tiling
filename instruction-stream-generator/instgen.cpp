#include "instgen.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>


void InstGenerator::emitFifoStart(std::ostream& os, Addr seed_mem_addr,
                                  const char* reg) const
{
    emit(os, "ltea", seed_mem_addr, 1, 1, 1, 8, reg);
    emit(os, "tmov", FIFO_SEED_ADDR, 1, 1, 1, 8, reg);
    emit(os, "tmov", FIFO_CTRL_START_ADDR, 1, 1, 1, 8, reg);
}

void InstGenerator::emitFifoStop(std::ostream& os, const char* reg) const
{
    emit(os, "tmov", FIFO_CTRL_STOP_ADDR, 1, 1, 1, 8, reg);
}

void InstGenerator::emitTileLoad(std::ostream& os, const GhostMat& M,
                                  uint dram_row, uint dram_col, uint w, uint h,
                                  Addr sp_addr, bool b_scratchpad,
                                  const char* reg) const
{
    if (!b_scratchpad) {
        load(os, M, dram_row, dram_col, w, h, reg);
    } else {
        emitDma(os, "dma_in", tileAddr(M, dram_row, dram_col), sp_addr,
                w, h, M.width, M.elem_width);
        emit(os, "ltea", sp_addr, w, h, w, M.elem_width, reg);
    }
}

void InstGenerator::emitTileStore(std::ostream& os, const GhostMat& M,
                                   uint dram_row, uint dram_col, uint w, uint h,
                                   Addr sp_addr, bool b_scratchpad,
                                   const char* reg) const
{
    if (!b_scratchpad) {
        store(os, M, dram_row, dram_col, w, h, reg);
    } else {
        emit(os, "tmov", sp_addr, w, h, w, M.elem_width, reg);
        emitDma(os, "dma_out", sp_addr, tileAddr(M, dram_row, dram_col),
                w, h, M.width, M.elem_width);
    }
}

void InstGenerator::emitLoadBSingleLevel(std::ostream& os, const GhostMat& B,
                                          uint dram_row_k, uint dram_col_j,
                                          Addr seed_addr, uint w, uint h,
                                          bool b_fifo, bool b_scratchpad,
                                          const char* reg) const
{
    if (!b_fifo) {
        emitTileLoad(os, B, dram_row_k, dram_col_j, w, h, SP_B_ADDR,
                     b_scratchpad, reg);
    } else {
        emitFifoStart(os, seed_addr, reg);
        if (!b_scratchpad) {
            emit(os, "ltea", FIFO_DATA_START_ADDR, w, h, w, B.elem_width, reg);
        } else {
            emitDma(os, "dma_in", FIFO_DATA_START_ADDR, SP_B_ADDR, w, h, w,
                    B.elem_width);
            emit(os, "ltea", SP_B_ADDR, w, h, w, B.elem_width, reg);
        }
    }
}

void InstGenerator::emitCacheTileSetup(std::ostream& os, const GhostMat& M,
                                        uint dram_row, uint dram_col,
                                        uint w, uint h,
                                        Addr sp_addr, bool b_scratchpad) const
{
    emitPrefetch(os, M, dram_row, dram_col, w, h);
    if (b_scratchpad) {
        emitDma(os, "dma_in", tileAddr(M, dram_row, dram_col), sp_addr,
                w, h, M.width, M.elem_width);
    }
}

void InstGenerator::emitRegTileLoadA(std::ostream& os, const GhostMat& A,
                                      TileShape tile,
                                      uint ti, uint rti, uint tk, uint rtk,
                                      bool b_scratchpad, const char* reg) const
{
    if (!b_scratchpad) {
        load(os, A, ti * tile.m + rti * reg_m_, tk * tile.k + rtk * reg_k_,
             reg_k_, reg_m_, reg);
    } else {
        emit(os, "ltea",
             SP_A_ADDR + (rti * reg_m_ * tile.k + rtk * reg_k_) * A.elem_width,
             reg_k_, reg_m_, tile.k, A.elem_width, reg);
    }
}

void InstGenerator::emitRegTileLoadB(std::ostream& os, const GhostMat& B,
                                      TileShape tile,
                                      uint tk, uint rtk, uint tj, uint rtj,
                                      bool b_fifo, bool b_scratchpad,
                                      const char* reg) const
{
    if (!b_scratchpad) {
        if (!b_fifo) {
            load(os, B, tk * tile.k + rtk * reg_k_, tj * tile.n + rtj * reg_n_,
                 reg_n_, reg_k_, reg);
        } else {
            emit(os, "ltea", FIFO_DATA_START_ADDR, reg_n_, reg_k_, reg_n_,
                 B.elem_width, reg);
        }
    } else {
        emit(os, "ltea",
             SP_B_ADDR + (rtk * reg_k_ * tile.n + rtj * reg_n_) * B.elem_width,
             reg_n_, reg_k_, tile.n, B.elem_width, reg);
    }
}

void InstGenerator::emitRegTileLoadC(std::ostream& os, const GhostMat& C,
                                      TileShape tile,
                                      uint ti, uint rti, uint tj, uint rtj,
                                      bool b_scratchpad, const char* reg) const
{
    if (!b_scratchpad) {
        load(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
             reg_n_, reg_m_, reg);
    } else {
        emit(os, "ltea",
             SP_C_ADDR + (rti * reg_m_ * tile.n + rtj * reg_n_) * C.elem_width,
             reg_n_, reg_m_, tile.n, C.elem_width, reg);
    }
}

void InstGenerator::emitRegTileStoreC(std::ostream& os, const GhostMat& C,
                                       TileShape tile,
                                       uint ti, uint rti, uint tj, uint rtj,
                                       bool b_scratchpad, const char* reg) const
{
    if (!b_scratchpad) {
        store(os, C, ti * tile.m + rti * reg_m_, tj * tile.n + rtj * reg_n_,
              reg_n_, reg_m_, reg);
    } else {
        emit(os, "tmov",
             SP_C_ADDR + (rti * reg_m_ * tile.n + rtj * reg_n_) * C.elem_width,
             reg_n_, reg_m_, tile.n, C.elem_width, reg);
    }
}

InstGenerator::GhostMat::GhostMat(uint w, uint h, uint elem_w, Addr a)
    : width(w), height(h), elem_width(elem_w),
      total_byte_size(width * height * elem_width), addr(a)
{
}

InstGenerator::InstGenerator(Params p)
    : A_(p.a_width, p.a_height, p.a_precision, 0),
      B_(p.b_width, p.a_width, p.b_precision, A_.total_byte_size),
      reg_m_(p.reg_m), reg_n_(p.reg_n), reg_k_(p.reg_k)
{
    if (A_.width != B_.height) {
        std::cerr << "invalid matrix dimensions for multiplication"
                  << std::endl;
        exit(1);
    }
}

void checkTileDivides(const InstGenerator::GhostMat& A,
                      const InstGenerator::GhostMat& B,
                      const InstGenerator::TileShape ts)
{
    if (A.height % ts.m != 0 || B.width % ts.n != 0 || A.width % ts.k != 0) {
        std::cerr << "matrix dimensions must be divisible by tile dimensions"
                  << std::endl;
        exit(1);
    }
}

void InstGenerator::generate(TileShape ts, std::ostream& os, bool b_stationary,
                             bool b_fifo, bool b_scratchpad) const
{
    checkTileDivides(A_, B_, ts);

    if (reg_m_ > 0) {
        if (ts.m % reg_m_ != 0 || ts.n % reg_n_ != 0 || ts.k % reg_k_ != 0) {
            std::cerr << "cache tile dimensions must be divisible by register "
                         "tile dimensions"
                      << std::endl;
            exit(1);
        }
    }

    const uint c_ew   = std::max(A_.elem_width, B_.elem_width);
    const Addr c_addr = A_.addr + A_.total_byte_size + B_.total_byte_size;

    const GhostMat C{B_.width, A_.height, c_ew, c_addr};

    emitTrace(A_, B_, C, ts, os, b_stationary, b_fifo, b_scratchpad);
}

void InstGenerator::emitTrace(const GhostMat& A, const GhostMat& B,
                              const GhostMat& C, TileShape tile,
                              std::ostream& os, bool b_stationary, bool b_fifo,
                              bool b_scratchpad) const
{
    if (reg_m_ > 0) {
        if (b_stationary) {
            emitTraceMultiLevelBStationary(A, B, C, tile, os, b_fifo,
                                           b_scratchpad);
        } else {
            emitTraceMultiLevelCStationary(A, B, C, tile, os, b_fifo,
                                           b_scratchpad);
        }
    } else {
        if (b_stationary) {
            emitTraceSingleLevelBStationary(A, B, C, tile, os, b_fifo,
                                            b_scratchpad);
        } else {
            emitTraceSingleLevelCStationary(A, B, C, tile, os, b_fifo,
                                            b_scratchpad);
        }
    }
}

void InstGenerator::emitTraceMultiLevelBStationary(
    const GhostMat& A, const GhostMat& B, const GhostMat& C, TileShape tile,
    std::ostream& os, bool b_fifo, bool b_scratchpad) const
{
    constexpr char a_id[] = "%ra";
    constexpr char b_id[] = "%rb";
    constexpr char c_id[] = "%rc";

    const uint M_tiles = A.height / tile.m;
    const uint N_tiles = B.width / tile.n;
    const uint K_tiles = A.width / tile.k;

    for (uint tk = 0; tk < K_tiles; ++tk) {
        for (uint tj = 0; tj < N_tiles; ++tj) {
            if (!b_fifo) {
                emitCacheTileSetup(os, B, tk * tile.k, tj * tile.n,
                                   tile.n, tile.k, SP_B_ADDR, b_scratchpad);
            } else {
                emitFifoStart(os, B.addr + (tk * N_tiles + tj) * 8, b_id);
                if (b_scratchpad)
                    emitDma(os, "dma_in", FIFO_DATA_START_ADDR, SP_B_ADDR,
                            tile.n, tile.k, tile.n, B.elem_width);
            }

            for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
                for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
                    emitRegTileLoadB(os, B, tile, tk, rtk, tj, rtj,
                                     b_fifo, b_scratchpad, b_id);

                    for (uint ti = 0; ti < M_tiles; ++ti) {
                        emitCacheTileSetup(os, A, ti * tile.m, tk * tile.k,
                                           tile.k, tile.m, SP_A_ADDR, b_scratchpad);
                        emitCacheTileSetup(os, C, ti * tile.m, tj * tile.n,
                                           tile.n, tile.m, SP_C_ADDR, b_scratchpad);

                        for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
                            emitRegTileLoadA(os, A, tile, ti, rti, tk, rtk,
                                             b_scratchpad, a_id);
                            emitRegTileLoadC(os, C, tile, ti, rti, tj, rtj,
                                             b_scratchpad, c_id);

                            os << "tmulac " << a_id << ", " << b_id << ", "
                               << c_id << std::endl;

                            emitRegTileStoreC(os, C, tile, ti, rti, tj, rtj,
                                              b_scratchpad, c_id);
                        }

                        if (b_scratchpad)
                            emitDma(os, "dma_out", SP_C_ADDR,
                                    tileAddr(C, ti * tile.m, tj * tile.n),
                                    tile.n, tile.m, C.width, C.elem_width);
                    }
                }
            }

            if (b_fifo)
                emitFifoStop(os, b_id);
        }
    }
}

void InstGenerator::emitTraceMultiLevelCStationary(
    const GhostMat& A, const GhostMat& B, const GhostMat& C, TileShape tile,
    std::ostream& os, bool b_fifo, bool b_scratchpad) const
{
    constexpr char a_id[] = "%ra";
    constexpr char b_id[] = "%rb";
    constexpr char c_id[] = "%rc";

    const uint M_tiles = A.height / tile.m;
    const uint N_tiles = B.width / tile.n;
    const uint K_tiles = A.width / tile.k;

    for (uint ti = 0; ti < M_tiles; ++ti) {
        for (uint tj = 0; tj < N_tiles; ++tj) {
            emitCacheTileSetup(os, C, ti * tile.m, tj * tile.n,
                               tile.n, tile.m, SP_C_ADDR, b_scratchpad);

            for (uint tk = 0; tk < K_tiles; ++tk) {
                emitCacheTileSetup(os, A, ti * tile.m, tk * tile.k,
                                   tile.k, tile.m, SP_A_ADDR, b_scratchpad);

                if (!b_fifo) {
                    emitCacheTileSetup(os, B, tk * tile.k, tj * tile.n,
                                       tile.n, tile.k, SP_B_ADDR, b_scratchpad);
                } else {
                    emitFifoStart(os, B.addr + (tk * N_tiles + tj) * 8, b_id);
                    if (b_scratchpad)
                        emitDma(os, "dma_in", FIFO_DATA_START_ADDR, SP_B_ADDR,
                                tile.n, tile.k, tile.n, B.elem_width);
                }

                for (uint rti = 0; rti < tile.m / reg_m_; ++rti) {
                    for (uint rtj = 0; rtj < tile.n / reg_n_; ++rtj) {
                        emitRegTileLoadC(os, C, tile, ti, rti, tj, rtj,
                                         b_scratchpad, c_id);

                        for (uint rtk = 0; rtk < tile.k / reg_k_; ++rtk) {
                            emitRegTileLoadA(os, A, tile, ti, rti, tk, rtk,
                                             b_scratchpad, a_id);
                            emitRegTileLoadB(os, B, tile, tk, rtk, tj, rtj,
                                             b_fifo, b_scratchpad, b_id);

                            os << "tmulac " << a_id << ", " << b_id << ", "
                               << c_id << std::endl;
                        }

                        emitRegTileStoreC(os, C, tile, ti, rti, tj, rtj,
                                          b_scratchpad, c_id);
                    }
                }

                if (b_fifo)
                    emitFifoStop(os, b_id);
            }

            if (b_scratchpad)
                emitDma(os, "dma_out", SP_C_ADDR,
                        tileAddr(C, ti * tile.m, tj * tile.n), tile.n, tile.m,
                        C.width, C.elem_width);
        }
    }
}

void InstGenerator::emitTraceSingleLevelBStationary(
    const GhostMat& A, const GhostMat& B, const GhostMat& C, TileShape tile,
    std::ostream& os, bool b_fifo, bool b_scratchpad) const
{
    constexpr char a_id[] = "%ra";
    constexpr char b_id[] = "%rb";
    constexpr char c_id[] = "%rc";

    const uint M_tiles = A.height / tile.m;
    const uint N_tiles = B.width / tile.n;
    const uint K_tiles = A.width / tile.k;

    for (uint tk = 0; tk < K_tiles; ++tk) {
        const uint atw = std::min(tile.k, A.width - tk * tile.k);

        for (uint tj = 0; tj < N_tiles; ++tj) {
            const uint ctw = std::min(tile.n, B.width - tj * tile.n);

            emitLoadBSingleLevel(os, B, tk * tile.k, tj * tile.n,
                                 B.addr + (tk * N_tiles + tj) * 8,
                                 ctw, atw, b_fifo, b_scratchpad, b_id);

            for (uint ti = 0; ti < M_tiles; ++ti) {
                const uint cth = std::min(tile.m, A.height - ti * tile.m);

                emitTileLoad(os, A, ti * tile.m, tk * tile.k, atw, cth,
                             SP_A_ADDR, b_scratchpad, a_id);
                emitTileLoad(os, C, ti * tile.m, tj * tile.n, ctw, cth,
                             SP_C_ADDR, b_scratchpad, c_id);

                os << "tmulac " << a_id << ", " << b_id << ", " << c_id
                   << std::endl;

                emitTileStore(os, C, ti * tile.m, tj * tile.n, ctw, cth,
                              SP_C_ADDR, b_scratchpad, c_id);
            }

            if (b_fifo)
                emitFifoStop(os, b_id);
        }
    }
}

void InstGenerator::emitTraceSingleLevelCStationary(
    const GhostMat& A, const GhostMat& B, const GhostMat& C, TileShape tile,
    std::ostream& os, bool b_fifo, bool b_scratchpad) const
{
    constexpr char a_id[] = "%ra";
    constexpr char b_id[] = "%rb";
    constexpr char c_id[] = "%rc";

    const uint M_tiles = A.height / tile.m;
    const uint N_tiles = B.width / tile.n;
    const uint K_tiles = A.width / tile.k;

    for (uint ti = 0; ti < M_tiles; ++ti) {
        const uint cth = std::min(tile.m, A.height - ti * tile.m);

        for (uint tj = 0; tj < N_tiles; ++tj) {
            const uint ctw = std::min(tile.n, B.width - tj * tile.n);

            emitTileLoad(os, C, ti * tile.m, tj * tile.n, ctw, cth,
                         SP_C_ADDR, b_scratchpad, c_id);

            for (uint tk = 0; tk < K_tiles; ++tk) {
                const uint atw = std::min(tile.k, A.width - tk * tile.k);

                emitTileLoad(os, A, ti * tile.m, tk * tile.k, atw, cth,
                             SP_A_ADDR, b_scratchpad, a_id);
                emitLoadBSingleLevel(os, B, tk * tile.k, tj * tile.n,
                                     B.addr + (tk * N_tiles + tj) * 8,
                                     ctw, atw, b_fifo, b_scratchpad, b_id);

                os << "tmulac " << a_id << ", " << b_id << ", " << c_id
                   << std::endl;

                if (b_fifo)
                    emitFifoStop(os, b_id);
            }

            emitTileStore(os, C, ti * tile.m, tj * tile.n, ctw, cth,
                          SP_C_ADDR, b_scratchpad, c_id);
        }
    }
}

Addr InstGenerator::tileAddr(const GhostMat& M, uint row, uint col) const
{
    return M.addr + (row * M.width + col) * M.elem_width;
}

void InstGenerator::emit(std::ostream& os, const char* op, Addr addr, uint w,
                         uint h, uint stride, uint ew, const char* reg) const
{
    os << op << " (0x" << std::hex << addr << std::dec << ", " << w << ", " << h
       << ", " << stride << ", " << ew << "), " << reg << std::endl;
}

void InstGenerator::emitDma(std::ostream& os, const char* op, Addr src,
                            Addr dst, uint w, uint h, uint stride,
                            uint ew) const
{
    os << op << " (0x" << std::hex << src << ", 0x" << dst << std::dec << ", "
       << w << ", " << h << ", " << stride << ", " << ew << ")" << std::endl;
}

void InstGenerator::load(std::ostream& os, const GhostMat& M, uint row,
                         uint col, uint w, uint h, const char* reg) const
{
    emit(os, "ltea", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}

void InstGenerator::store(std::ostream& os, const GhostMat& M, uint row,
                          uint col, uint w, uint h, const char* reg) const
{
    emit(os, "tmov", tileAddr(M, row, col), w, h, M.width, M.elem_width, reg);
}

void InstGenerator::emitPrefetch(std::ostream& os, const GhostMat& M, uint row,
                                 uint col, uint w, uint h) const
{
    os << "prefetch (0x" << std::hex << tileAddr(M, row, col) << std::dec
       << ", " << w << ", " << h << ", " << M.width << ", " << M.elem_width
       << ")" << std::endl;
}
