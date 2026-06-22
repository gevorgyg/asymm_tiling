#pragma once

#include "action.h"
#include "memory_object.h"

#include <iosfwd>


// Terminal main memory. Stateless -- a read/write emits a single
// MemoryAccess action with the configured cost.
class MainMemory : public MemoryObject
{
  public:
    explicit MainMemory(uint access_cycles) : MemoryObject(access_cycles) {}

    void read(Addr addr, size_t size, Trace& trace)  override;
    void write(Addr addr, size_t size, Trace& trace) override;
};


// Records one access to main memory. Pure data: the device cost is
// snapshotted at construction.
class MemoryAccess : public Action
{
  public:
    MemoryAccess(uint cost, Addr addr) : addr_(addr), cost_(cost) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "MemoryAccess"; }
    void        print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};
