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

// Which operand is held in the processor register while the inner loops run.
// All modes prefetch the C tile into L1 at the start of each output tile.
//
//   AStationary:      A sub-tile in %ra; B and C cycle through L1.     Mem only.
//   BStationary:      B sub-tile in %rb; A and C cycle through L1.     Mem or FIFO.
//   OutputStationary: C sub-tile in %rc (accumulator); A and B stream. Mem or FIFO.
//
enum class Dataflow { AStationary, BStationary, OutputStationary };

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
    uint num_prefill = 1;  // parallel prefill buffers for pipelined mode
  };

  explicit InstGenerator(Params p);

  void generate(TileShape tile, std::ostream &os, Dataflow df,
                bool b_fifo = false, bool b_fifo_pipelined = false,
                bool b_fifo_col_major = false) const;

private:
  // MMIO ports of the PRNG-FIFO device (must match main.cpp's wiring).
  static constexpr Addr START_REG = 0xFF000000;
  static constexpr Addr SEED_REG  = 0xFF000004;
  static constexpr Addr DATA_REG  = 0xFF000008;
  static constexpr Addr STOP_REG  = 0xFF00000C;

  void emitTrace(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                 TileShape tile, std::ostream &os, Dataflow df, bool b_fifo) const;

  // Multi-level (3D-register) variants — all prefetch the C tile first.
  //
  // AStationary:      A reg-tile in %ra; for each A, B cols iterate; C load/store per (rti,rtj).
  // BStationary:      B reg-tile in %rb (from FIFO or L1); A rows iterate; C load/store per (rti,rtj).
  // OutputStationary: C reg-tile in %rc across ALL k; A and B stream; C touched only at tile boundary.
  //                   For FIFO: the full B tile is consumed once per (rti, rtj, tk) pass;
  //                   only the column matching rtj is fed to tmulac.
  void emitMultiLevelAStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                  TileShape tile, std::ostream &os) const;
  void emitMultiLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                  TileShape tile, std::ostream &os, bool b_fifo) const;
  void emitMultiLevelOutputStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                       TileShape tile, std::ostream &os, bool b_fifo) const;

  // Single-level variants (no register sub-tiling).
  void emitSingleLevelAStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                   TileShape tile, std::ostream &os) const;
  void emitSingleLevelBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                   TileShape tile, std::ostream &os, bool b_fifo) const;
  void emitSingleLevelOutputStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                        TileShape tile, std::ostream &os, bool b_fifo) const;

  // Pipelined-prefill variant (FIFO only, always multi-level, always B-stationary
  // at the register level with overlapped generation).
  void emitPipelinedBStationary(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                                 TileShape tile, std::ostream &os) const;

  // Column-major output-stationary with FIFO: one START per rti covers the full
  // B tile in col-major order; rtj iterates inside consuming columns sequentially.
  // M_reg starts per output tile, no ghost reads.
  void emitMultiLevelOutputStationaryColMajorFifo(
      const GhostMat &A, const GhostMat &B, const GhostMat &C,
      TileShape tile, std::ostream &os) const;

  // Pipelined col-major output-stationary: same structure as above but uses the
  // pipelined FIFO device. SWAP at the top of each rti; the previous rti's tile
  // is pre-generated in the background so each SWAP is stall-free.
  void emitPipelinedOutputStationaryColMajor(
      const GhostMat &A, const GhostMat &B, const GhostMat &C,
      TileShape tile, std::ostream &os) const;

  // PRNG-FIFO helpers.
  void emitFifoStart(std::ostream &os, uint tk, uint tj, uint n_tiles, const char *reg) const;
  void emitFifoStop(std::ostream &os, const char *reg) const;

  Addr tileAddr(const GhostMat &M, uint row, uint col) const;

  void emit(std::ostream &os, const char *op, Addr addr, uint w, uint h,
            uint stride, uint ew, const char *reg) const;
  void load(std::ostream &os, const GhostMat &M, uint row, uint col,
            uint w, uint h, const char *reg) const;
  void store(std::ostream &os, const GhostMat &M, uint row, uint col,
             uint w, uint h, const char *reg) const;
  void emitPrefetch(std::ostream &os, const GhostMat &M, uint row, uint col,
                    uint w, uint h) const;

  const GhostMat A_;
  const GhostMat B_;
  uint reg_m_;
  uint reg_n_;
  uint reg_k_;
  uint seed_bytes_;
  uint num_prefill_;
};

#endif
