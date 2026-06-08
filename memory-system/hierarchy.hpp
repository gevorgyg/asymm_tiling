#include "memory_object.hpp"
#include <stdexcept>

#pragma once

#include "memory_object.hpp"

#include <cassert>
#include <unordered_set>

class CacheL1 : public MemoryObject
{
  public:
    CacheL1(Cycles access_cycles, size_t line_size, MemoryObject* next_level)
        : MemoryObject(access_cycles, next_level), line_size_(line_size) {
        assert(line_size_ > 0);
        assert(next_ != nullptr);
    }


    Cycles read(Addr addr, size_t size) override
    {
        return access(addr, size);
    }

    Cycles write(Addr addr, size_t size) override
    {
        return access(addr, size);
    }

    size_t hits() const { return hits_; }
    size_t misses() const { return misses_; }

  private:
    Cycles access(Addr addr, size_t size)
    {
      throw std::runtime_error("not implemented");
    }

    size_t                   line_size_;
    std::unordered_set<Addr> lines_;
    size_t                   hits_   = 0;
    size_t                   misses_ = 0;
};

class Memory: MemoryObject {
  public:
    Memory(Cycles access_cycles) : MemoryObject(access_cycles, nullptr) {}
};
