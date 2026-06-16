#pragma once

#include "cache/cache.h"
#include "mainmem.h"
#include "memory_object.h"
#include "prng.h"
#include "prng_fifo.h"

#include <string>


// Sits between L1 and L2: addresses inside the PRNG/PRNG_FIFO windows are served
// by their respective generator devices, everything else falls through to L2.
class AddrRouter : public MemoryObject
{
  public:
    AddrRouter(PrngDev& prng, PrngFifoDev& prng_fifo, MemoryObject& fallthrough)
        : MemoryObject(0), prng_(prng), prng_fifo_(prng_fifo), fallthrough_(fallthrough)
    {
    }

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

  private:
    PrngDev&      prng_;
    PrngFifoDev&  prng_fifo_;
    MemoryObject& fallthrough_;
};


// L1 -> AddrRouter -> { PrngDev | PrngFifoDev | L2 -> MainMemory }.
class MemoryHierarchy : public MemoryObject
{
  public:
    struct Parameters {
        Cache::InitParameters l1;
        uint l1_access_cycles;
        std::string l1_policy;
        Cache::InitParameters l2;
        uint l2_access_cycles;
        std::string l2_policy;
        uint mem_access_cycles;
        PrngDev::InitParameters prng;
        PrngFifoDev::InitParameters prng_fifo;
    };


    explicit MemoryHierarchy(Parameters p, const size_t& cpu_cycles);

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

    const PrngFifoDev& prng_fifo() const
    {
        return prng_fifo_;
    }

    PrngFifoDev& prng_fifo()
    {
        return prng_fifo_;
    }

  private:
    MainMemory mem_;
    Cache l2_;
    PrngDev prng_;
    PrngFifoDev prng_fifo_;
    AddrRouter router_;
    Cache l1_;
};
