#pragma once

#include "../../utils.h"
#include "eviction_policy.h"

#include <cstddef>
#include <list>
#include <random>
#include <vector>


class CacheLine
{
  public:
    explicit CacheLine(Addr line_addr) : line_addr_(line_addr) {}

    Addr lineAddr() const { return line_addr_; }
    bool dirty()    const { return dirty_; }
    void markDirty()      { dirty_ = true; }
    void clearDirty()     { dirty_ = false; }

  private:
    Addr line_addr_;
    bool dirty_ = false;
};


class Set
{
  public:
    Set(size_t assoc, Policy policy)
        : assoc_(assoc), policy_(policy), rng_(42) {}

    bool       isFull() const { return lines_.size() >= assoc_; }
    CacheLine* lookup(Addr line_addr);
    void       insert(Addr line_addr);
    void       remove(Addr line_addr);
    CacheLine* pickVictim();

    // Clear dirty bits, returning the line addrs that were dirty.
    std::vector<Addr> collectDirty();

  private:
    size_t               assoc_;
    Policy               policy_;
    std::list<CacheLine> lines_;
    std::mt19937         rng_;
};
