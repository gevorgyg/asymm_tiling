#include <cassert>
#include <cstdio>
#include <iostream>
#include <limits>
#include <random>

//
// LOAD_TILE <Tile ID> <Base Addr> <Width> <Height> <Stride> <Element Width>
// STORE_TILE <Tile ID> <Dest Addr> <Width> <Height> <Stride> <Element Width>
// TILE_MUL_ACC <SrcTile1 ID> <SrcTile2 ID> <DestTile ID>
//

using uint = unsigned int;

struct Mat {
    uint width;
    uint height;
    uint elem_width;
};

class InstGen
{
  public:
    using TileID    = uint;
    using Addr      = unsigned long;
    using ElemWidth = uint;

    static constexpr size_t page_size = 4 * 1024;

    InstGen(Mat mat_a, Mat mat_b)
    {
        using long_limit = std::numeric_limits<Addr>;

        if (mat_a.width != mat_b.height) {
            std::cerr << "invalid matrix dimantions for multiplication"
                      << std::endl;
            throw;
        }

        size_t a_byte_size = mat_a.width * mat_a.height * mat_a.elem_width;
        size_t b_byte_size = mat_b.width * mat_b.height * mat_b.elem_width;

        ElemWidth c_elem_width = std::max(mat_a.elem_width, mat_b.elem_width);
        size_t c_byte_size     = mat_a.height * mat_b.width * c_elem_width;

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

        A = {mat_a.width, mat_a.height, mat_a.elem_width, a_addr};
        B = {mat_b.width, mat_b.height, mat_b.elem_width, b_addr};
        C = {mat_a.height, mat_b.width, c_elem_width, c_addr};
    }

    // LOAD_TILE <Tile ID><Base Addr><Width><Height><Stride><Element Size>

    // loading matrix A, from AB=C. The left matrix, so we need to shift the
    // tiles to the right, by using their width.
    void load_left() const
    {
        printf("LOAD_TILE %d, 0x%lX, %d, %d, %d, %d\n", 0, A.addr, A.width / 2,
               A.height / 2, A.width, A.elem_width);
    }

    // loading matrix B, from AB=C. The right matrix, so we need to shift the
    // tiles down, by using their height.
    void load_right() const
    {
        printf("LOAD_TILE %d, 0x%lX, %d, %d, %d, %d\n", 1, B.addr, B.width / 2,
               B.height / 2, B.width, B.elem_width);
    }

    void store() const;

    void mul_acc() const;

    void generate() const
    {
        constexpr int tile_width = 10;

        while (1) {
            load_left();
            load_right();

            mul_acc();
        }

        store();
    }

  private:
    struct GhostMat {
        uint width;
        uint height;
        uint elem_width;

        Addr addr;
    };

    GhostMat A;
    GhostMat B;
    GhostMat C;
};

int main()
{
    InstGen gen{{100, 100, 64}, {100, 100, 8}};
    gen.load_left();
    gen.load_right();

    return 0;
};
