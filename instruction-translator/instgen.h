#ifndef INSTRUCTION_GENERATOR_H_
#define INSTRUCTION_GENERATOR_H_

#include <cstddef>
#include <iosfwd>

//
// LOAD_TILE <Tile ID> <Base Addr> <Width> <Height> <Stride> <Element Width>
// STORE_TILE <Tile ID> <Dest Addr> <Width> <Height> <Stride> <Element Width>
// TILE_MUL_ACC <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
// START_PRNG_LOADER <magic address>
// PRNG_LOAD <magic address>
//

class InstGenerator {
public:
  using uint = unsigned int;
  using TileID = uint;
  using Addr = uint;

  // Tile sizes in elements.
  //   m = output rows per tile      (M direction, A.height direction)
  //   n = output cols per tile      (N direction, B.width  direction)
  //   k = reduction depth per tile  (K direction, A.width  direction)
  struct TileShape {
    uint m;
    uint n;
    uint k;
  };

  InstGenerator(uint a_width, uint a_height, uint a_elem_width, uint b_width,
                uint b_height, uint b_elem_width);

  void generate(TileShape tile, std::ostream &os) const;

  void generatePrng(TileShape tile, std::ostream &os) const;

private:
  struct GhostMat {
    GhostMat() = default;
    GhostMat(uint w, uint h, uint elem_w, Addr a);

    uint width = 0;
    uint height = 0;
    uint elem_width = 0;

    size_t total_elem_size = 0;
    size_t total_byte_size = 0;

    Addr addr = 0;
  };

  void emitTrace(const GhostMat &A, const GhostMat &B, const GhostMat &C,
                 TileShape tile, std::ostream &os, bool prng) const;

  // Byte address of element (row, col) inside matrix M.
  static Addr tileAddr(const GhostMat &M, uint row, uint col);

  // Emit one instruction: "<op> (0x<addr>, w, h, stride, ew), <reg>".
  static void emit(std::ostream &os, const char *op, Addr addr, uint w, uint h,
                   uint stride, uint ew, const char *reg);

  // ltea convenience: load tile from M at (row, col) into <reg>.
  static void load(std::ostream &os, const GhostMat &M, uint row, uint col,
                   uint w, uint h, const char *reg);

  // tmov convenience: store tile from <reg> into M at (row, col).
  static void store(std::ostream &os, const GhostMat &M, uint row, uint col,
                    uint w, uint h, const char *reg);

  // *_w = width
  // *_h = height
  // *_ew = element_width
  uint a_w_, a_h_, a_ew_;
  uint b_w_, b_h_, b_ew_;
};

#endif
