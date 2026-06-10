#pragma once

#include "../action.h"
#include "../memory_object.h"
#include "eviction_policy.h"
#include "set.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>


// Cache-emitted actions are nested as Cache::TagLookup, Cache::LineFill,
// Cache::Evict. They have private access to Cache (nested classes are
// members), so Cache's public surface stays minimal -- read/write/stats.

class Cache : public MemoryObject
{
  public:
    struct InitParameters {
        const char* name;        // "L1", "L2" -- propagated into Actions
        size_t      size;        // total bytes
        size_t      line_size;   // bytes per line
        size_t      assoc;       // ways per set
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

    // Nested actions -- defined below.
    class TagLookup;
    class LineFill;
    class Evict;

  private:
    Addr lineAddr(Addr byte_addr) const;
    Set& setFor(Addr byte_addr);

    const char*                     name_;
    size_t                          size_;
    size_t                          line_size_;
    size_t                          assoc_;
    std::unique_ptr<EvictionPolicy> policy_;
    MemoryObject*                   next_level_;
    std::vector<Set>                sets_;

    Stats stats_;
};


// --- Cache::TagLookup ---------------------------------------------------

class Cache::TagLookup : public Action
{
  public:
    TagLookup(Cache& cache, Addr byte_addr);

    void perform(Trace& trace) override;

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "TagLookup"; }
    void        print(std::ostream& os) const override;

    bool wasHit() const { return hit_; }

  private:
    Cache& cache_;
    Addr   byte_addr_;
    uint   cost_;
    bool   hit_ = false;
};


// --- Cache::LineFill ----------------------------------------------------

class Cache::LineFill : public Action
{
  public:
    LineFill(Cache& cache, Addr byte_addr);

    void perform(Trace& trace) override;

    uint        cyclesToPerform() const override { return 0; }
    const char* name() const override            { return "LineFill"; }
    void        print(std::ostream& os) const override;

  private:
    Cache& cache_;
    Addr   byte_addr_;
};


// --- Cache::Evict -------------------------------------------------------

class Cache::Evict : public Action
{
  public:
    Evict(Cache& cache, Addr victim_line_addr, bool dirty);

    void perform(Trace& trace) override;

    uint        cyclesToPerform() const override { return 0; }
    const char* name() const override            { return "Evict"; }
    void        print(std::ostream& os) const override;

  private:
    Cache& cache_;
    Addr   victim_line_addr_;
    bool   dirty_;
};
