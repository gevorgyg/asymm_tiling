#pragma once

#include "memory_object.h"

#include <cstddef>
#include <cstdint>
#include <list>
#include <memory>
#include <vector>


// --- Cache storage primitives -------------------------------------------

class CacheLine
{
  public:
    explicit CacheLine(Addr line_addr) : line_addr_(line_addr) {}

    Addr lineAddr() const { return line_addr_; }
    bool dirty()    const { return dirty_; }
    void markDirty()      { dirty_ = true; }

  private:
    Addr line_addr_;
    bool dirty_ = false;
};


class Set
{
  public:
    explicit Set(size_t assoc) : assoc_(assoc) {}

    bool       isFull() const { return lines_.size() >= assoc_; }
    CacheLine* lookup(Addr line_addr);
    void       insert(Addr line_addr);
    void       remove(Addr line_addr);

    // Exposed so eviction policies can iterate in insertion order
    // (front = oldest, back = newest).
    std::list<CacheLine>&       lines()       { return lines_; }
    const std::list<CacheLine>& lines() const { return lines_; }

  private:
    size_t               assoc_;
    std::list<CacheLine> lines_;
};


// --- Eviction policy ----------------------------------------------------

class EvictionPolicy
{
  public:
    virtual ~EvictionPolicy() = default;

    virtual CacheLine*  pickVictim(Set& set) const = 0;
    virtual const char* name() const               = 0;
};


class FifoPolicy : public EvictionPolicy
{
  public:
    CacheLine*  pickVictim(Set& set) const override;
    const char* name() const override { return "FIFO"; }
};


// --- Cache --------------------------------------------------------------
//
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

    Cache(uint access_cycles, InitParameters p,
          std::unique_ptr<EvictionPolicy> policy, MemoryObject* next_level);

    Trace read(Addr addr, size_t size)  override;
    Trace write(Addr addr, size_t size) override;

    size_t hits()   const { return hits_; }
    size_t misses() const { return misses_; }

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

    size_t hits_   = 0;
    size_t misses_ = 0;
};


// --- Cache::TagLookup ---------------------------------------------------

class Cache::TagLookup : public Action
{
  public:
    inline static uint64_t count_ = 0;

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
    inline static size_t count_ = 0;

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
    inline static size_t count_ = 0;

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
