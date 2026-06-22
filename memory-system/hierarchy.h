#pragma once

#include "../policies.h"
#include "cache/cache.h"
#include "mainmem/mainmem.h"
#include "memory_object.h"
#include "prng/prng.h"
#include "prng_fifo/prng_fifo.h"
#include "scratchpad/scratchpad.h"


// Sits between L1 and L2: L1 misses that land inside the on-demand PRNG
// window are served by the PrngDev; everything else falls through to L2.
// (FIFO MMIO traffic is short-circuited at MemoryHierarchy::access and
// never reaches L1 -- so this router never sees it.)
class AddrRouter : public MemoryObject
{
  public:
    AddrRouter(PrngDev& prng, MemoryObject& fallthrough)
        : MemoryObject(0), prng_(prng), fallthrough_(fallthrough) {}

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

  private:
    PrngDev&      prng_;
    MemoryObject& fallthrough_;
};


// Hub for the memory subsystem. Not a MemoryObject itself -- there is only
// one, and the polymorphism would buy nothing. Callers route every memory
// request through access(), which decides MMIO vs L1-path at the top.
class MemoryHierarchy
{
  public:
    struct Parameters {
        Cache::InitParameters l1;
        uint l1_access_cycles;
        Policy l1_policy;
        Cache::InitParameters l2;
        uint l2_access_cycles;
        Policy l2_policy;
        uint mem_access_cycles;
        PrngDev::InitParameters prng;
        PrngFifoDev::InitParameters prng_fifo;
        uint sp_access_cycles;
        uint sp_banks;
        uint sp_word_size_bytes;
    };

    explicit MemoryHierarchy(Parameters p, const size_t& cpu_cycles);

    // Single entry point for every CPU memory operation. FIFO MMIO addresses
    // bypass L1 entirely; all other traffic goes through L1 -> Router ->
    // {PrngDev | L2 -> MainMemory}.
    void access(Addr addr, size_t size, bool is_write, Trace& trace);

    // Overload for parallel tile accesses (specifically scratchpad banking conflict simulation)
    uint access(Addr base_addr, uint t_width, uint t_height, uint stride,
                uint elem_width, bool is_write, Trace& trace);

    const Cache&          l1()         const { return l1_; }
    const Cache&          l2()         const { return l2_; }
    const PrngDev&        prng()       const { return prng_; }
    const PrngFifoDev&    prng_fifo()  const { return prng_fifo_; }
    PrngFifoDev&          prng_fifo()        { return prng_fifo_; }
    const ScratchpadDev&  scratchpad() const { return scratchpad_; }

  private:
    MainMemory    mem_;
    Cache         l2_;
    PrngDev       prng_;
    PrngFifoDev   prng_fifo_;
    ScratchpadDev scratchpad_;
    AddrRouter    router_;
    Cache         l1_;
};
