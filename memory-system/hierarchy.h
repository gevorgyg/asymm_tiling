#pragma once

#include "cache/cache.h"
#include "mainmem.h"
#include "memory_object.h"


// PRNG device will live here later
class MemoryHierarchy : public MemoryObject
{
  public:
    struct Parameters {
        Cache::InitParameters l1;
        uint                  l1_access_cycles;
        uint                  mem_access_cycles;
    };

    explicit MemoryHierarchy(Parameters p);

    Trace read(Addr addr, size_t size)  override;
    Trace write(Addr addr, size_t size) override;

    size_t l1Hits()   const { return l1_.hits(); }
    size_t l1Misses() const { return l1_.misses(); }

  private:
    MainMemory mem_;
    Cache      l1_;
};
