#pragma once

#include "set.h"

#include <memory>
#include <string>


// A policy looks at the lines in a (full) set and returns the one to evict.
// It never mutates the set itself -- the caller (LineFill::perform) does the
// removal via the cache's API.

class EvictionPolicy
{
  public:
    virtual ~EvictionPolicy() = default;

    virtual CacheLine*  pickVictim(Set& set) const = 0;
    virtual const char* name() const               = 0;
    virtual void        recordAccess(Set& set, Addr line_addr) const {}
};


class FifoPolicy : public EvictionPolicy
{
  public:
    CacheLine*  pickVictim(Set& set) const override;
    const char* name() const override { return "FIFO"; }
};


class LruPolicy : public EvictionPolicy
{
  public:
    CacheLine*  pickVictim(Set& set) const override;
    const char* name() const override { return "LRU"; }
    void        recordAccess(Set& set, Addr line_addr) const override;
};


std::unique_ptr<EvictionPolicy> createEvictionPolicy(const std::string& name);

