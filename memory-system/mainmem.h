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

    Trace read(Addr addr, size_t size)  override;
    Trace write(Addr addr, size_t size) override;
};


// Records one access to main memory. No state to mutate -> perform() is a
// no-op; the device cost is snapshotted at construction.
class MemoryAccess : public Action
{
  public:
    MemoryAccess(uint cost, Addr addr) : addr_(addr), cost_(cost) {}

    void perform(Trace& /*trace*/) override {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "MemoryAccess"; }
    void        print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};
