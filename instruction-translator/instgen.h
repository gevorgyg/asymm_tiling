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
  using ElemWidth = uint;
  using Addr = uint;

  static constexpr uint page_size = 4 * 1024;

  InstGenerator(uint a_width, uint a_height, uint a_elem_width, uint b_width,
                uint b_height, uint b_elem_width, bool is_prng_gen = false);

  // k is the tile width ratio
  void generate(int m, int n, int k, std::ostream &os) const;

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

  GhostMat A;
  GhostMat B;
  GhostMat C;

  bool is_prng_generator_ = false;
};

#endif
