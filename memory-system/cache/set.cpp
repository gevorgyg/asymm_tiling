#include "set.h"

#include <algorithm>
#include <cassert>


CacheLine* Set::lookup(Addr line_addr)
{
    auto it = std::find_if(
        lines_.begin(), lines_.end(),
        [&](const CacheLine& l) { return l.lineAddr() == line_addr; });
    if (it == lines_.end()) return nullptr;
    // LRU and MRU treat hits as a promotion to the MRU slot (back).
    if (policy_ == Policy::LRU || policy_ == Policy::MRU) {
        lines_.splice(lines_.end(), lines_, it);
        return &lines_.back();
    }
    return &*it;
}

void Set::insert(Addr line_addr)
{
    assert(!isFull());
    lines_.emplace_back(line_addr);
}

void Set::remove(Addr line_addr)
{
    auto it = std::find_if(
        lines_.begin(), lines_.end(),
        [&](const CacheLine& l) { return l.lineAddr() == line_addr; });
    assert(it != lines_.end());
    lines_.erase(it);
}

CacheLine* Set::pickVictim()
{
    assert(!lines_.empty());
    switch (policy_) {
        case Policy::LRU:
        case Policy::FIFO:
            return &lines_.front();
        case Policy::MRU:
            return &lines_.back();
        case Policy::Random: {
            std::uniform_int_distribution<size_t> dist(0, lines_.size() - 1);
            auto it = lines_.begin();
            std::advance(it, dist(rng_));
            return &*it;
        }
    }
    return &lines_.front();
}

