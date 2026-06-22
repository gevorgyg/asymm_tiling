#pragma once

#include "../action.h"
#include "../memory_object.h"
#include "eviction_policy.h"
#include "set.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>


// Cache-emitted events live in cache_actions.h (TagLookup, LineFill, Evict).
// They are pure-data records: Cache::read/write does all the state mutation
// and then appends a witness.

enum class WritePolicy {
    WRITE_THROUGH,
    WRITE_BACK
};


class Cache : public MemoryObject
{
  public:
    struct InitParameters {
        const char* name;        // "L1", "L2" -- propagated into Actions
        size_t      size;        // total bytes
        size_t      line_size;   // bytes per line
        size_t      assoc;       // ways per set
        WritePolicy write_policy;
    };

    struct Stats {
        uint64_t tag_lookups = 0;
        uint64_t line_fills  = 0;
        uint64_t evicts      = 0;
        size_t   hits        = 0;
        size_t   misses      = 0;
    };

    Cache(uint access_cycles, InitParameters p,
          std::unique_ptr<EvictionPolicy> policy, MemoryObject* next_level);

    void read(Addr addr, size_t size, Trace& trace)  override;
    void write(Addr addr, size_t size, Trace& trace) override;

    const char*  name()  const { return name_; }
    const Stats& stats() const { return stats_; }

  private:
    // Tag-check the line containing `addr`. Updates stats and (on hit) LRU
    // order. Returns true iff the line is present.
    bool probe(Addr addr);

    // Install the line containing `addr` into its set, evicting and (if dirty)
    // writing back a victim if the set is full. Appends an Evict event (when
    // applicable) and a LineFill event to `trace`.
    void fillLine(Addr addr, Trace& trace);

    // Mark the line containing `addr` dirty. Caller guarantees it is resident.
    void markDirty(Addr addr);

    Addr lineAddr(Addr byte_addr) const;
    Set& setFor(Addr byte_addr);

    const char*                     name_;
    size_t                          size_;
    size_t                          line_size_;
    size_t                          assoc_;
    WritePolicy                     write_policy_;
    std::unique_ptr<EvictionPolicy> policy_;
    MemoryObject*                   next_level_;
    std::vector<Set>                sets_;

    Stats stats_;
};
