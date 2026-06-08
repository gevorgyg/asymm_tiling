#include "eviction_policy.h"

#include <cassert>


CacheLine* FifoPolicy::pickVictim(Set& set) const
{
    // Insertion-order list: front was inserted first, so it's the FIFO victim.
    assert(!set.lines().empty());
    return &set.lines().front();
}
