#include "cache.h"
#include "cache_actions.h"

#include <cassert>


Cache::Cache(uint access_cycles, InitParameters p, Policy policy,
             MemoryObject* next_level)
    : MemoryObject(access_cycles),
      name_(p.name),
      size_(p.size),
      line_size_(p.line_size),
      assoc_(p.assoc),
      write_policy_(p.write_policy),
      policy_(policy),
      next_level_(next_level)
{
    assert(line_size_ > 0);
    assert(assoc_ > 0);
    assert(size_ % (line_size_ * assoc_) == 0);
    assert(next_level_ != nullptr);

    const size_t num_sets = size_ / (line_size_ * assoc_);
    sets_.reserve(num_sets);
    for (size_t i = 0; i < num_sets; ++i) {
        sets_.emplace_back(assoc_, policy_);
    }
}

Addr Cache::lineAddr(Addr byte_addr) const
{
    return byte_addr / line_size_;
}

Set& Cache::setFor(Addr byte_addr)
{
    return sets_[lineAddr(byte_addr) % sets_.size()];
}

bool Cache::probe(Addr addr)
{
    ++stats_.tag_lookups;
    const Addr line = lineAddr(addr);
    Set& set = setFor(addr);
    if (set.lookup(line)) {
        ++stats_.hits;
        return true;
    }
    ++stats_.misses;
    return false;
}

void Cache::fillLine(Addr addr, Trace& trace)
{
    Set& set = setFor(addr);
    if (set.isFull()) {
        CacheLine* victim    = set.pickVictim();
        const Addr victim_la = victim->lineAddr();
        const bool dirty     = victim->dirty();
        if (dirty) {
            next_level_->write(victim_la * line_size_, line_size_, trace);
            ++stats_.writebacks;
            stats_.bytes_out += line_size_;
        }
        set.remove(victim_la);
        ++stats_.evicts;
        trace.push_back(std::make_unique<Evict>(name_, victim_la, dirty));
    }
    set.insert(lineAddr(addr));
    ++stats_.line_fills;
    stats_.bytes_in += line_size_;
    trace.push_back(std::make_unique<LineFill>(name_, addr));
}

void Cache::markDirty(Addr addr)
{
    Set& set = setFor(addr);
    CacheLine* line = set.lookup(lineAddr(addr));
    assert(line != nullptr);
    line->markDirty();
}

void Cache::flush(Trace& trace)
{
    for (Set& set : sets_) {
        for (Addr line_addr : set.collectDirty()) {
            next_level_->write(line_addr * line_size_, line_size_, trace);
            ++stats_.writebacks;
            stats_.bytes_out += line_size_;
        }
    }
}

void Cache::read(Addr addr, size_t size, Trace& trace)
{
    const bool hit = probe(addr);
    trace.push_back(std::make_unique<TagLookup>(name_, addr, accessCycles(), hit));
    if (hit) {
        return;
    }
    next_level_->read(addr, size, trace);
    fillLine(addr, trace);
}

void Cache::write(Addr addr, size_t size, Trace& trace)
{
    const bool hit = probe(addr);
    trace.push_back(std::make_unique<TagLookup>(name_, addr, accessCycles(), hit));

    if (write_policy_ == WritePolicy::WRITE_THROUGH) {
        // No-allocate: forward the write straight through.
        next_level_->write(addr, size, trace);
        stats_.bytes_out += size;
        return;
    }

    // Write-back.
    if (hit) {
        markDirty(addr);
        return;
    }
    // Write-allocate: fetch, install, then mark dirty.
    next_level_->read(addr, size, trace);
    fillLine(addr, trace);
    markDirty(addr);
}
