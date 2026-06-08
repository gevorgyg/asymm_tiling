#pragma once

#include "../utils.h"

#include <cstddef>

class MemoryObject
{
  public:
    using Cycles = unsigned long;

    explicit MemoryObject(Cycles access_cycles, MemoryObject* next) : access_cycles_(access_cycles), next_(next)
    {
    }

    virtual ~MemoryObject() = default;

    Cycles accessCycles() const { return access_cycles_; }

    virtual Cycles read(Addr addr, size_t size)  = 0;
    virtual Cycles write(Addr addr, size_t size) = 0;

  protected:
    Cycles access_cycles_;
    MemoryObject* next_;
};
