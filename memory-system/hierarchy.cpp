#include "hierarchy.h"
#include "address_map.h"
#include "scratchpad/scratchpad_action.h"


void AddrRouter::read(Addr addr, size_t size, Trace& trace)
{
    if (prng_.contains(addr)) {
        prng_.read(addr, size, trace);
    } else {
        fallthrough_.read(addr, size, trace);
    }
}

void AddrRouter::write(Addr addr, size_t size, Trace& trace)
{
    if (prng_.contains(addr)) {
        prng_.write(addr, size, trace);
    } else {
        fallthrough_.write(addr, size, trace);
    }
}

MemoryHierarchy::MemoryHierarchy(Parameters p, const size_t& cpu_cycles)
    : mem_(p.mem_access_cycles),
      l2_(p.l2_access_cycles, p.l2, p.l2_policy, &mem_),
      prng_(p.prng),
      prng_fifo_(p.prng_fifo, cpu_cycles),
      scratchpad_(p.sp_access_cycles, p.sp_banks, p.sp_word_size_bytes, SP_A_ADDR, SP_END),
      router_(prng_, l2_),
      l1_(p.l1_access_cycles, p.l1, p.l1_policy, &router_)
{
}

void MemoryHierarchy::access(Addr addr, size_t size, bool is_write, Trace& trace)
{
    if (scratchpad_.contains(addr)) {
        if (is_write) {
            scratchpad_.write(addr, size, trace);
        } else {
            scratchpad_.read(addr, size, trace);
        }
        return;
    }

    // FIFO MMIO is the only path that bypasses L1. Caches don't see these
    // addresses at all -- the device handles control/seed/data reads itself.
    if (prng_fifo_.contains(addr)) {
        if (is_write) prng_fifo_.write(addr, size, trace);
        else          prng_fifo_.read(addr, size, trace);
        return;
    }

    if (is_write) l1_.write(addr, size, trace);
    else          l1_.read(addr, size, trace);
}

uint MemoryHierarchy::access(Addr base_addr, uint t_width, uint t_height, uint stride,
                             uint elem_width, bool is_write, Trace& trace)
{
    return scratchpad_.accessTile(base_addr, t_width, t_height, stride, elem_width, is_write, trace);
}
