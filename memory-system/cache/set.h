#pragma once

#include "../../utils.h"

#include <cstddef>
#include <list>


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
