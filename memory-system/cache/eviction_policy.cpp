#include "eviction_policy.h"

#include <cassert>
#include <iostream>


CacheLine* FifoPolicy::pickVictim(Set& set) const
{
    // Insertion-order list: front was inserted first, so it's the FIFO victim.
    assert(!set.lines().empty());
    return &set.lines().front();
}

CacheLine* LruPolicy::pickVictim(Set& set) const
{
    // Front is the Least Recently Used element because hits are spliced to the back
    // and new lines are inserted at the back.
    assert(!set.lines().empty());
    return &set.lines().front();
}

void LruPolicy::recordAccess(Set& set, Addr line_addr) const
{
    set.touch(line_addr);
}

std::unique_ptr<EvictionPolicy> createEvictionPolicy(const std::string& name)
{
    if (name == "FIFO") {
        return std::make_unique<FifoPolicy>();
    } else if (name == "LRU") {
        return std::make_unique<LruPolicy>();
    } else {
        std::cerr << "error: unknown eviction policy: " << name << std::endl;
        exit(1);
    }
}

