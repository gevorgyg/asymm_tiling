#pragma once

#include "../action.h"
#include "../memory_object.h"


// Terminal main memory. Stateless -- a read/write emits a single
// MemoryAccess action with the configured cost.
class MainMemory : public MemoryObject
{
  public:
    explicit MainMemory(uint access_cycles) : MemoryObject(access_cycles) {}

    void read(Addr addr, size_t size, Trace& trace)  override;
    void write(Addr addr, size_t size, Trace& trace) override;
};
