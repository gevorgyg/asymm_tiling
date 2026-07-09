#ifndef INSTRUCTION_GENERATOR_H_
#define INSTRUCTION_GENERATOR_H_

#include "../utils.h"

#include <cstddef>
#include <iosfwd>

//
// LOAD_TILE <Tile ID> <Base Addr> <Width> <Height> <Stride> <Element Width>
// STORE_TILE <Tile ID> <Dest Addr> <Width> <Height> <Stride> <Element Width>
// TILE_MUL_ACC <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
//
// Whether B is memory-backed or PRNG-generated is a hardware property (the
// PRNG window covers B's addresses), so the instruction stream is identical
// in both modes.

class InstGenerator {
public:
  // Tile sizes in elements.
  //   m = output rows per tile      (M direction, A.height direction)
  //   n = output cols per tile      (N direction, B.width  direction)
  //   k = reduction depth per tile  (K direction, A.width  direction)
  struct TileShape {
    uint m;
    uint n;
    uint k;
  };

  struct GhostMat {
    GhostMat(uint w, uint h, uint elem_w, Addr a);

    uint width;
    uint height;
    uint elem_width;

    const uint total_byte_size;

    Addr addr;
  };

  // Driven entirely by main.cpp's config file. Addresses are laid out
  // sequentially with no alignment -- A at 0, B right after A.
  struct Params {
    uint a_height;
    uint a_width;
    uint b_width;
    uint a_precision;
    uint b_precision;
    uint reg_m = 0;
    uint reg_n = 0;
    uint reg_k = 0;
    uint seed_bytes = 8;   // bytes of PRNG-FIFO seed stored per B tile
  };

  explicit InstGenerator(Params p);

  void generate(TileShape tile, std::ostream &os, bool b_stationary = false, bool b_fifo = false,
                bool b_fifo_pipelined = false) const;

private:
  // MMIO ports of the PRNG-FIFO device (must match main.cpp's wiring).
  static constexpr Addr START_REG = 0xFF000000;
  static constexpr Addr SEED_REG  = 0xFF000004;
  static constexpr Addr DATA_REG  = 0xFF000008;
  static constexpr Addr STOP_REG  = 0xFF00000C;

  void emitTrace(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                 TileShape tile, std::ostream &os, bool b_stationary, bool b_fifo) const;

  // C-stationary: prefetch the C tile, stream A subcolumns x B subrows as
  // rank-1 updates (M outermost). B-stationary mirrors it: hold one B tile,
  // stream A over M while C accumulates (N outermost). Both register-tiled.
  void emitTraceMultiLevelCStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                      TileShape tile, std::ostream &os, bool b_fifo) const;
  void emitTraceMultiLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                      TileShape tile, std::ostream &os, bool b_fifo) const;
  // Pipelined prefill variant: pre-generates next session while computing
  // current session, overlapping generation latency with computation.
  void emitTraceMultiLevelCStationaryOuterProductsPipelined(const GhostMat &A, const GhostMat &B,
                                                             const GhostMat &C, TileShape tile,
                                                             std::ostream &os) const;
  void emitTraceSingleLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                       TileShape tile, std::ostream &os, bool b_fifo) const;
  void emitTraceSingleLevelCStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                       TileShape tile, std::ostream &os, bool b_fifo) const;

  // PRNG-FIFO helpers: seed the device for B tile (tk,tj) and start it; stop it.
  void emitFifoStart(std::ostream &os, uint tk, uint tj, uint n_tiles, const char *reg) const;
  void emitFifoStop(std::ostream &os, const char *reg) const;

  // Byte address of element (row, col) inside matrix M.
  Addr tileAddr(const GhostMat &M, uint row, uint col) const;

  // Emit one instruction: "<op> (0x<addr>, w, h, stride, ew), <reg>".
  void emit(std::ostream &os, const char *op, Addr addr, uint w, uint h,
                   uint stride, uint ew, const char *reg) const;

  // ltea convenience: load tile from M at (row, col) into <reg>.
  void load(std::ostream &os, const GhostMat &M, uint row, uint col,
                   uint w, uint h, const char *reg) const;

  // tmov convenience: store tile from <reg> into M at (row, col).
  void store(std::ostream &os, const GhostMat &M, uint row, uint col,
                     uint w, uint h, const char *reg) const;

  // prefetch convenience: prefetch cache tile from M at (row, col).
  void emitPrefetch(std::ostream &os, const GhostMat &M, uint row, uint col,
                    uint w, uint h) const;

  const GhostMat A_;
  const GhostMat B_;
  uint reg_m_;
  uint reg_n_;
  uint reg_k_;
  uint seed_bytes_;
};

#endif
