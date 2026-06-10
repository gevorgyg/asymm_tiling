#pragma once

#include "../interpreter/prng_record.h"
#include "cache/cache.h"
#include "mainmem.h"
#include "memory_object.h"

// PRNG device will live here later
class MemoryHierarchy : public MemoryObject
{
  public:
    struct Parameters {
        Cache::InitParameters l1;
        uint l1_access_cycles;
        Cache::InitParameters l2;
        uint l2_access_cycles;
        uint mem_access_cycles;
    };

    explicit MemoryHierarchy(Parameters p, size_t& cpu_cycles);

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

    // Public MMIO window controls
    void startPrng(Addr magic_addr)
    {
        magic_addr_ = magic_addr;
    }
    void stopPrng()
    {
        magic_addr_ = 0;
    }
    void reseedPrng(Addr base_addr, Trace& trace);
    Addr getMagicAddr() const
    {
        return magic_addr_;
    }

    static constexpr Addr seed_mem_base = 0xFFFFD000;

  private:
    MainMemory mem_;
    Cache l2_;
    Cache l1_;

    PrngDevSim prng_dev_;
    Addr magic_addr_ = 0;
};
