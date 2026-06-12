#include "cache.h"

#include <cassert>
#include <ostream>


// --- Cache --------------------------------------------------------------

Cache::Cache(uint access_cycles, InitParameters p,
             std::unique_ptr<EvictionPolicy> policy, MemoryObject* next_level)
    : MemoryObject(access_cycles),
      name_(p.name),
      size_(p.size),
      line_size_(p.line_size),
      assoc_(p.assoc),
      policy_(std::move(policy)),
      next_level_(next_level)
{
    assert(this->line_size_ > 0);
    assert(this->assoc_ > 0);
    assert(this->size_ % (this->line_size_ * this->assoc_) == 0);
    assert(policy_ != nullptr);
    assert(next_level_ != nullptr);

    const size_t num_sets =
        this->size_ / (this->line_size_ * this->assoc_);
    sets_.reserve(num_sets);
    for (size_t i = 0; i < num_sets; ++i) {
        sets_.emplace_back(this->assoc_);
    }
}

Addr Cache::lineAddr(Addr byte_addr) const
{
    return byte_addr / this->line_size_;
}

Set& Cache::setFor(Addr byte_addr)
{
    return sets_[lineAddr(byte_addr) % sets_.size()];
}

void Cache::read(Addr addr, size_t size, Trace& trace)
{
    size_t start_idx = trace.size();

    trace.push_back(std::make_unique<TagLookup>(*this, addr));
    trace.back()->perform(trace);
    const bool hit = static_cast<TagLookup*>(trace[start_idx].get())->wasHit();

    if (hit) {
        return;
    }

    // Miss: defer to the next level, then append to trace.
    next_level_->read(addr, size, trace);

    // Install the line locally. LineFill::perform decides whether to evict.
    trace.push_back(std::make_unique<LineFill>(*this, addr));
    trace.back()->perform(trace);
}

void Cache::write(Addr addr, size_t size, Trace& trace)
{
    // Write-through + no-allocate: a TagLookup updates hit/miss stats, then
    // the write is forwarded to the next level regardless of the outcome.
    // We never install the line locally, so there's no LineFill / Evict on
    // the write path and the dirty bit stays unused.
    trace.push_back(std::make_unique<TagLookup>(*this, addr));
    trace.back()->perform(trace);

    next_level_->write(addr, size, trace);
}


// --- Cache::TagLookup ---------------------------------------------------

Cache::TagLookup::TagLookup(Cache& cache, Addr byte_addr)
    : cache_(cache), byte_addr_(byte_addr), cost_(cache.accessCycles())
{
}

void Cache::TagLookup::perform(Trace& /*trace*/)
{
    ++cache_.stats_.tag_lookups;

    const Addr line = cache_.lineAddr(byte_addr_);
    Set& set = cache_.setFor(byte_addr_);
    if (set.lookup(line)) {
        hit_ = true;
        ++cache_.stats_.hits;
        cache_.policy_->recordAccess(set, line);
    } else {
        hit_ = false;
        ++cache_.stats_.misses;
    }
}

void Cache::TagLookup::print(std::ostream& os) const
{
    os << cache_.name_ << " TagLookup @0x" << std::hex << byte_addr_
       << std::dec << " " << (hit_ ? "HIT" : "MISS") << " (" << cost_ << " cy)";
}


// --- Cache::LineFill ----------------------------------------------------

Cache::LineFill::LineFill(Cache& cache, Addr byte_addr)
    : cache_(cache), byte_addr_(byte_addr)
{
}

void Cache::LineFill::perform(Trace& trace)
{
    ++cache_.stats_.line_fills;

    Set& set = cache_.setFor(byte_addr_);

    if (set.isFull()) {
        CacheLine* victim     = cache_.policy_->pickVictim(set);
        const Addr victim_la  = victim->lineAddr();
        const bool victim_drt = victim->dirty();

        trace.push_back(
            std::make_unique<Evict>(cache_, victim_la, victim_drt));
        trace.back()->perform(trace);
    }

    set.insert(cache_.lineAddr(byte_addr_));
}

void Cache::LineFill::print(std::ostream& os) const
{
    os << cache_.name_ << " LineFill @0x" << std::hex << byte_addr_
       << std::dec;
}


// --- Cache::Evict -------------------------------------------------------

Cache::Evict::Evict(Cache& cache, Addr victim_line_addr, bool dirty)
    : cache_(cache), victim_line_addr_(victim_line_addr), dirty_(dirty)
{
}

void Cache::Evict::perform(Trace& /*trace*/)
{
    ++cache_.stats_.evicts;

    cache_.sets_[victim_line_addr_ % cache_.sets_.size()].remove(
        victim_line_addr_);
}

void Cache::Evict::print(std::ostream& os) const
{
    os << cache_.name_ << " Evict line=0x" << std::hex
       << victim_line_addr_ << std::dec
       << (dirty_ ? " (dirty)" : " (clean)");
}
