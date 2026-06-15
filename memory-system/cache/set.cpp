#include "set.h"

#include <algorithm>
#include <cassert>


CacheLine* Set::lookup(Addr line_addr)
{
    for (auto& line : lines_) {
        if (line.lineAddr() == line_addr) {
            return &line;
        }
    }
    return nullptr;
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

void Set::touch(Addr line_addr)
{
    auto it = std::find_if(
        lines_.begin(), lines_.end(),
        [&](const CacheLine& l) { return l.lineAddr() == line_addr; });
    if (it != lines_.end()) {
        lines_.splice(lines_.end(), lines_, it);
    }
}

