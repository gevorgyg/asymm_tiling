#pragma once

#include "cache/cache.h"
#include "mainmem.h"
#include "memory_object.h"
#include "prng.h"


// Sits between L1 and L2: addresses inside the PRNG window are served by the
// generator, everything else falls through to L2. Pure wiring, zero cost.
class AddrRouter : public MemoryObject
{
  public:
    AddrRouter(PrngDev& prng, MemoryObject& fallthrough)
        : MemoryObject(0), prng_(prng), fallthrough_(fallthrough)
    {
    }

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

  private:
    PrngDev&      prng_;
    MemoryObject& fallthrough_;
};


// L1 -> AddrRouter -> { PrngDev | L2 -> MainMemory }. PRNG data never reaches
// L2; an evicted PRNG line is clean and simply regenerated on the next miss.
class MemoryHierarchy : public MemoryObject
{
  public:
    struct Parameters {
        Cache::InitParameters l1;
        uint l1_access_cycles;
        Cache::InitParameters l2;
        uint l2_access_cycles;
        uint mem_access_cycles;
        PrngDev::InitParameters prng;
    };

    explicit MemoryHierarchy(Parameters p);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    const Cache& l1() const
    {
        return l1_;
    }

    const Cache& l2() const
    {
        return l2_;
    }

    const PrngDev& prng() const
    {
        return prng_;
    }

  private:
    MainMemory mem_;
    Cache l2_;
    PrngDev prng_;
    AddrRouter router_;
    Cache l1_;
};
