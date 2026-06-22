#include "eviction_policy.h"

#include <cassert>


const char* policyName(Policy p)
{
    switch (p) {
        case Policy::LRU:  return "LRU";
        case Policy::FIFO: return "FIFO";
    }
    return "?";
}

// Both policies evict the front of the per-set insertion-ordered list:
// FIFO obviously, LRU because hits are spliced to the back.
CacheLine* pickVictim(Policy /*p*/, Set& set)
{
    assert(!set.lines().empty());
    return &set.lines().front();
}

// LRU promotes the touched line to MRU; FIFO ignores access order.
void recordAccess(Policy p, Set& set, Addr line_addr)
{
    if (p == Policy::LRU) {
        set.touch(line_addr);
    }
}
