#pragma once

#include "../utils.h"
#include "action.h"

#include <cstddef>


// Anything the CPU can address -- caches, terminal memory, the PRNG facade,
// etc. Holds its own per-access cost. Successor pointers (if any) belong to
// the derived classes that actually use them; the base stays topology-free.
class MemoryObject
{
  public:
    explicit MemoryObject(uint access_cycles) : access_cycles_(access_cycles) {}

    virtual ~MemoryObject() = default;

    uint accessCycles() const { return access_cycles_; }

    virtual Trace read(Addr addr, size_t size)  = 0;
    virtual Trace write(Addr addr, size_t size) = 0;

  protected:
    uint access_cycles_;
};
