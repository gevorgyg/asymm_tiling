#pragma once

#include "../utils.h"

#include <cstddef>
#include <iosfwd>
#include <memory>
#include <numeric>
#include <vector>

// An Action is a record of one textbook-level step a memory device took while
// handling a read or write -- the kind of thing you'd point at in a computer-
// architecture diagram (tag lookup, line fill, eviction, writeback).
//
// A request returns a Trace = sequence of Actions. Summing cyclesToPerform()
// over the Trace gives the access time. Iterating it tells you what the model
// captured and -- by their absence -- what it elides.
class Action;
using Trace = std::vector<std::unique_ptr<Action>>;

class Action
{
  public:
    virtual ~Action() = default;

    virtual uint        cyclesToPerform() const       = 0;
    virtual const char* name() const                  = 0;
    virtual void        print(std::ostream& os) const = 0;

    // Mutates the device this action belongs to. May append further actions
    // (e.g. an Evict triggered by a LineFill on a full set) to `trace`.
    virtual void        perform(Trace& trace) = 0;
};

inline uint totalCycles(const Trace& trace)
{
    return std::accumulate(
        trace.begin(), trace.end(), 0u,
        [](uint acc, const std::unique_ptr<Action>& a) {
            return acc + a->cyclesToPerform();
        });
}


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
