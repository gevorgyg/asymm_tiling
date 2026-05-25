#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <limits>
#include <random>

//
// LOAD_TILE <Tile ID> <Base Addr> <Width> <Height> <Stride> <Element Width>
// STORE_TILE <Tile ID> <Dest Addr> <Width> <Height> <Stride> <Element Width>
// TILE_MUL_ACC <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
//

using uint = unsigned int;

class InstGen
{
  public:
    using TileID    = uint;
    using Addr      = unsigned long;
    using ElemWidth = uint;

    static constexpr size_t page_size = 4 * 1024;

    InstGen(uint a_width, uint a_height, uint a_elem_width, uint b_width,
            uint b_height, uint b_elem_width)
    {
        using long_limit = std::numeric_limits<Addr>;

        if (a_width != b_height) {
            std::cerr << "invalid matrix dimantions for multiplication"
                      << std::endl;
            throw;
        }

        size_t a_byte_size = a_width * a_height * a_elem_width;
        size_t b_byte_size = b_width * b_height * b_elem_width;

        ElemWidth c_elem_width = std::max(a_elem_width, b_elem_width);
        size_t c_byte_size     = a_height * b_width * c_elem_width;

        // generate A address and make sure it leaves enough space for B
        std::mt19937_64 prng_addr_{std::random_device()()};
        std::uniform_int_distribution<Addr> distA(
            a_byte_size, long_limit::max() - b_byte_size - c_byte_size);

        // align A address
        Addr a_addr = distA(prng_addr_);

        Addr a_align = a_addr / page_size;
        a_addr       = a_align * page_size;
        if (a_addr < a_byte_size)
            a_addr += page_size;

        // put B close to A and align
        Addr b_addr = a_addr + a_byte_size;

        Addr b_align = b_addr / page_size;
        b_addr       = b_align * page_size;
        if (b_addr < a_addr + a_byte_size)
            b_addr += page_size;

        assert(b_addr - a_addr >= a_byte_size);

        // put C close to A,B and align
        Addr c_addr  = b_addr + b_byte_size;
        Addr c_align = c_addr / page_size;
        c_addr       = c_align * page_size;
        if (c_addr < b_addr + b_byte_size)
            c_addr += page_size;

        assert(c_addr - b_addr >= b_byte_size);

        A = GhostMat{a_width, a_height, a_elem_width, a_addr};
        B = GhostMat{b_width, b_height, b_elem_width, b_addr};
        C = GhostMat{a_height, b_width, c_elem_width, c_addr};
    }

    // LOAD_TILE <Tile ID><Base Addr><Width><Height><Stride><Element Size>

    // TODO: support a-sym tiles

    // k is the tile width ratio
    void generate(int k, std::ostream& os) const
    {
        static constexpr uint a_id = 0;
        static constexpr uint b_id = 1;
        static constexpr uint c_id = 2;

        int tile_width  = C.width / k;
        int tile_height = tile_width;

        int tci = 0;
        int tri = 0;

        while (tri * C.width * tile_height + tci * tile_width <
               C.total_elem_size) {

            Addr c_disp = tri * C.width * tile_height * C.elem_width;

            os << "LOAD_TILE" << ' ' << c_id << ", " << "0x" << std::hex //
               << C.addr + c_disp + tci * tile_width * C.elem_width      //
               << std::dec << ", " << tile_width << ", "                 //
               << tile_height << ", " << C.width << ", "                 //
               << C.elem_width << std::endl;                             //

            int in_tci = 0;
            int in_tri = 0;

            while (in_tci * tile_width < A.width) {
                Addr a_disp = tri * A.width * tile_height * A.elem_width;
                Addr b_disp = tci * tile_width * B.elem_width;

                os << "LOAD_TILE" << ' ' << a_id << ", " << "0x" << std::hex //
                   << A.addr + a_disp + in_tci * tile_width * A.elem_width   //
                   << std::dec << ", " << tile_width << ", "                 //
                   << tile_height << ", " << A.width << ", "                 //
                   << A.elem_width << std::endl;                             //

                os << "LOAD_TILE" << ' ' << b_id << ", " << "0x" << std::hex //
                   << B.addr + b_disp +                                      //
                          in_tri * B.width * tile_height * B.elem_width      //
                   << std::dec << ", " << tile_width << ", "                 //
                   << tile_height << ", " << B.width << ", "                 //
                   << B.elem_width << std::endl;                             //

                os << "TILE_MUL_ACC" << ' ' << a_id << ", " << b_id << ", "
                   << c_id << std::endl;

                ++in_tci;
                ++in_tri;
            }

            os << "STORE_TILE " << ' ' << c_id << ", " << "0x" << std::hex //
               << C.addr + tri * C.width * C.elem_width +                  //
                      tci * tile_width * C.elem_width                      //
               << std::dec << ", " << tile_width << ", "                   //
               << tile_height << ", " << C.width << ", "                   //
               << C.elem_width << std::endl;                               //

            ++tci;
            if (tci * tile_width >= C.width) {
                tci = 0;
                ++tri;
            }
        }
    }

  private:
    struct GhostMat {
        GhostMat() = default;

        GhostMat(uint w, uint h, uint elem_w, Addr a)
            : width(w), height(h), elem_width(elem_w),
              total_elem_size(width * height),
              total_byte_size(width * height * elem_width), addr(a)
        {
        }

        uint width;
        uint height;
        uint elem_width;

        size_t total_elem_size;
        size_t total_byte_size;

        Addr addr;
    };

    GhostMat A;
    GhostMat B;
    GhostMat C;
};

int main()
{
    InstGen gen{100, 100, 64, 100, 100, 8};

    std::ofstream ofs("matmul.matv");

    if (!ofs.is_open()) {
        std::cerr << "error opening file" << std::endl;
    }

    gen.generate(4, ofs);

    return 0;
};
