#pragma once

#include "memory_object.h"

#include <cstddef>
#include <list>
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
//
// A policy looks at the lines in a (full) set and returns the one to evict.
// It never mutates the set itself -- the caller (LineFill::perform) does the
// removal via the cache's API.

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

class Cache : public MemoryObject
{
  public:
    struct InitParameters {
        const char* name;        // "L1", "L2" -- propagated into Actions
        size_t      size;        // total bytes
        size_t      line_size;   // bytes per line
        size_t      assoc;       // ways per set
    };

    Cache(uint access_cycles, InitParameters p, EvictionPolicy& policy,
          MemoryObject* next_level);

    Trace read(Addr addr, size_t size)  override;
    Trace write(Addr addr, size_t size) override;

    // --- API used by Actions ------------------------------------------
    const char*     levelName() const { return name_; }
    Addr            lineAddr(Addr byte_addr) const;
    Set&            setFor(Addr byte_addr);
    EvictionPolicy& evictionPolicy()  { return policy_; }
    MemoryObject*   nextLevel()       { return next_level_; }

    CacheLine* lookup(Addr line_addr);
    void       installLine(Addr line_addr);
    void       removeLine(Addr line_addr);

    void       countHit()  { ++hits_; }
    void       countMiss() { ++misses_; }

    size_t hits()   const { return hits_; }
    size_t misses() const { return misses_; }

  private:
    const char*      name_;
    size_t           size_;
    size_t           line_size_;
    size_t           assoc_;
    EvictionPolicy&  policy_;
    MemoryObject*    next_level_;
    std::vector<Set> sets_;

    size_t hits_   = 0;
    size_t misses_ = 0;
};


// --- Cache-emitted actions ----------------------------------------------
//
// Each action holds a Cache& and mutates it inside perform(). The driver
// (Cache::read / LineFill::perform) is responsible for appending the action
// to the trace; perform() only handles state changes and any sub-actions it
// triggers (e.g. LineFill -> Evict).

class TagLookup : public Action
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


class LineFill : public Action
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


class Evict : public Action
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
