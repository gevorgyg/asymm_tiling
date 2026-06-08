#pragma once

#include "cache.h"
#include "memory_object.h"


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


// Top-level facade the CPU talks to. For now: a single L1 (FIFO eviction)
// backed by main memory. Routing for the PRNG device hooks in here later.
// Policies live inside their Cache -- a hierarchy doesn't own one.
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
