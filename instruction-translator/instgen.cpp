#include "instgen.h"

#include <cassert>
#include <cstdio>
#include <iostream>
#include <limits>
#include <random>

InstGenerator::GhostMat::GhostMat(uint w, uint h, uint elem_w, Addr a)
    : width(w), height(h), elem_width(elem_w),
      total_elem_size(width * height),
      total_byte_size(width * height * elem_width), addr(a) {}

// deterministic elements constructor
InstGenerator::InstGenerator(uint a_width, uint a_height, uint a_elem_width,
                             uint b_width, uint b_height, uint b_elem_width,
                             bool is_prng_gen)
    : is_prng_generator_(is_prng_gen) {
  using long_limit = std::numeric_limits<Addr>;

  if (a_width != b_height) {
    std::cerr << "invalid matrix dimantions for multiplication" << std::endl;
    throw;
  }

  size_t a_byte_size = a_width * a_height * a_elem_width;
  size_t b_byte_size = b_width * b_height * b_elem_width;

  ElemWidth c_elem_width = std::max(a_elem_width, b_elem_width);
  size_t c_byte_size = a_height * b_width * c_elem_width;

  std::mt19937 prng_addr_{std::random_device()()};

  if (is_prng_generator_) {
    std::uniform_int_distribution<Addr> uni_dist(
        a_byte_size, long_limit::max() - c_byte_size);

    // align A address
    Addr a_addr = uni_dist(prng_addr_);

    Addr a_align = a_addr / page_size;
    a_addr = a_align * page_size;
    if (a_addr < a_byte_size)
      a_addr += page_size;

    // put C close to A and align
    Addr c_addr = a_addr + a_byte_size;

    Addr c_align = c_addr / page_size;
    c_addr = c_align * page_size;
    if (c_addr < a_addr + a_byte_size)
      c_addr += page_size;

    assert(c_addr - a_addr >= a_byte_size);

    // TODO: think about a better way to get the magic address
    Addr magic_addr = 0;
    if (a_addr > 16) {
      magic_addr = a_addr - 16;
    } else {
      magic_addr = c_addr + c_byte_size + 16;
    }

    A = GhostMat{a_width, a_height, a_elem_width, a_addr};
    B = GhostMat{b_width, b_height, b_elem_width, magic_addr};
    C = GhostMat{a_height, b_width, c_elem_width, c_addr};

  } else {
    // generate A address and make sure it leaves enough space for B
    std::uniform_int_distribution<Addr> uni_dist(
        a_byte_size, long_limit::max() - b_byte_size - c_byte_size);

    // align A address
    Addr a_addr = uni_dist(prng_addr_);

    Addr a_align = a_addr / page_size;
    a_addr = a_align * page_size;
    if (a_addr < a_byte_size)
      a_addr += page_size;

    // put B close to A and align
    Addr b_addr = a_addr + a_byte_size;

    Addr b_align = b_addr / page_size;
    b_addr = b_align * page_size;
    if (b_addr < a_addr + a_byte_size)
      b_addr += page_size;

    assert(b_addr - a_addr >= a_byte_size);

    // put C close to A,B and align
    Addr c_addr = b_addr + b_byte_size;
    Addr c_align = c_addr / page_size;
    c_addr = c_align * page_size;
    if (c_addr < b_addr + b_byte_size)
      c_addr += page_size;

    assert(c_addr - b_addr >= b_byte_size);

    A = GhostMat{a_width, a_height, a_elem_width, a_addr};
    B = GhostMat{b_width, b_height, b_elem_width, b_addr};
    C = GhostMat{a_height, b_width, c_elem_width, c_addr};
  }
}

// LOAD_TILE <Base Addr><Width><Height><Stride><Element Size>
void InstGenerator::generate(int m, int n, int k, std::ostream &os) const {
  static constexpr char a_id[] = "%ra";
  static constexpr char b_id[] = "%rb";
  static constexpr char c_id[] = "%rc";

  const uint t_m = A.height / m;
  const uint t_n = B.width / n;
  const uint t_k = A.width / k;

  const uint a_tile_height = t_m;
  const uint a_tile_width = t_k;

  const uint b_tile_height = t_k;
  const uint b_tile_width = t_n;

  const uint c_tile_height = t_m;
  const uint c_tile_width = t_n;

  int tci = 0;
  int tri = 0;

  if (is_prng_generator_) {
    os << "strtrng" << ' ' << "0x" << std::hex << B.addr //
       << std::dec << std::endl;                         //
  }

  while (tri * C.width * c_tile_height + tci * c_tile_width <
         C.total_elem_size) {

    Addr c_disp = tri * C.width * c_tile_height * C.elem_width;

    uint ctw = std::min(c_tile_width, C.width - tci * c_tile_width);
    uint cth = std::min(c_tile_height, C.height - tri * c_tile_height);

    os << "ltea" << ' ' << '(' << "0x" << std::hex          //
       << C.addr + c_disp + tci * ctw * C.elem_width        //
       << std::dec << ", " << ctw << ", "                   //
       << cth << ", " << C.width << ", "                    //
       << C.elem_width << ')' << ", " << c_id << std::endl; //

    int in_tci = 0;
    int in_tri = 0;

    while (in_tci * a_tile_width < A.width) {
      Addr a_disp = tri * A.width * a_tile_height * A.elem_width;
      Addr b_disp = tci * b_tile_width * B.elem_width;

      uint atw = std::min(a_tile_width, A.width - in_tci * a_tile_width);
      uint ath = cth;

      uint btw = ctw;
      uint bth = atw;

      os << "ltea " << '(' << "0x" << std::hex                //
         << A.addr + a_disp + in_tci * atw * A.elem_width     //
         << std::dec << ", " << atw << ", "                   //
         << ath << ", " << A.width << ", "                    //
         << A.elem_width << ')' << ", " << a_id << std::endl; //

      if (is_prng_generator_) {
        os << "ltea " << '(' << "0x" << std::hex                //
           << B.addr                                            //
           << std::dec << ", " << btw << ", "                   //
           << bth << ", " << B.width << ", "                    //
           << B.elem_width << ')' << ", " << b_id << std::endl; //
      } else {
        os << "ltea " << '(' << "0x" << std::hex                //
           << B.addr + b_disp +                                 //
                  in_tri * B.width * bth * B.elem_width         //
           << std::dec << ", " << btw << ", "                   //
           << bth << ", " << B.width << ", "                    //
           << B.elem_width << ')' << ", " << b_id << std::endl; //
      }

      os << "tmulac " << a_id << ", " << b_id << ", " << c_id << std::endl;

      ++in_tci;
      ++in_tri;
    }

    os << "tmov " << '(' << "0x" << std::hex                //
       << C.addr + c_disp +                                 //
              tci * ctw * C.elem_width                      //
       << std::dec << ", " << ctw << ", "                   //
       << cth << ", " << C.width << ", "                    //
       << C.elem_width << ')' << ", " << c_id << std::endl; //

    ++tci;
    if (tci * ctw >= C.width) {
      tci = 0;
      ++tri;
    }
  }

  if (is_prng_generator_) {
    os << "stprng" << std::endl; //
  }
}
