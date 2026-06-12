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
  };

  explicit InstGenerator(Params p);

  void generate(TileShape tile, std::ostream &os, bool b_stationary = false) const;

private:
  void emitTrace(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                 TileShape tile, std::ostream &os, bool b_stationary) const;

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

  const GhostMat A_;
  const GhostMat B_;
};

#endif
