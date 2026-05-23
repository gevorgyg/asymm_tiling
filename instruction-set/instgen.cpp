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
        Addr b_addr  = a_addr + b_byte_size;
        Addr b_align = b_addr / page_size;
        b_addr       = b_align * page_size;
        if (b_addr < a_addr + b_byte_size)
            b_addr += page_size;

        assert(b_addr - a_addr >= b_byte_size);

        // put C close to A,B and align
        Addr c_addr  = b_addr + c_byte_size;
        Addr c_align = c_addr / page_size;
        c_addr       = c_align * page_size;
        if (c_addr < b_addr + c_byte_size)
            c_addr += page_size;

        assert(c_addr - b_addr >= c_byte_size);

        A = {mat_a.width, mat_a.height, mat_a.elem_width, a_addr};
        B = {mat_b.width, mat_b.height, mat_b.elem_width, b_addr};
        C = {mat_a.height, mat_b.width, c_elem_width, c_addr};
    }

    // testing -----------
    // void load(TileID id, Addr src_addr, int width, int height, int stride,
    //           ElemWidth size)
    enum mat {
        a,
        b,
        c,
    };

    void load(mat m)
    {
        // LOAD_TILE <Tile ID><Base Addr><Width><Height><Stride><Element Size>

        const GhostMat* mat_ptr = pickMat(m);

        TileID nid = getNewId();
        printf("LOAD_TILE %d, 0x%.32lX, %d, %d, %d, %d\n", nid, mat_ptr->addr,
               mat_ptr->width / 2, mat_ptr->height / 2, mat_ptr->width,
               mat_ptr->elem_width);
    }
    // testing -----------

    void store(TileID id, Addr dest_addr, int width, int height, int stride,
               ElemWidth size);

    void mul_acc(TileID A, TileID B, TileID C);

  private:
    TileID getNewId()
    {
        TileID new_id = min_avail_id_;
        ++min_avail_id_;
        return new_id;
    }

    void releaseId()
    {
        --min_avail_id_;
    }

    inline static TileID min_avail_id_ = 0;

    struct GhostMat {
        uint width;
        uint height;
        uint elem_width;

        Addr addr;
    };

    GhostMat A;
    GhostMat B;
    GhostMat C;

    const GhostMat* pickMat(mat m) const
    {
        const GhostMat* mat_ptr;

        switch (m) {
        case a:
            mat_ptr = &A;
            break;
        case b:
            mat_ptr = &B;
            break;
        case c:
            mat_ptr = &C;
            break;
        }

        return mat_ptr;
    }
};

int main()
{
    InstGen gen{{100, 100, 64}, {100, 100, 8}};
    gen.load(InstGen::a);
    gen.load(InstGen::b);
    gen.load(InstGen::c);

    return 0;
};
