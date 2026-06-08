#include "cache.h"

#include <algorithm>
#include <cassert>
#include <ostream>


// --- Set ----------------------------------------------------------------

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


// --- FifoPolicy ---------------------------------------------------------

CacheLine* FifoPolicy::pickVictim(Set& set) const
{
    // Insertion-order list: front was inserted first, so it's the FIFO victim.
    assert(!set.lines().empty());
    return &set.lines().front();
}


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

Trace Cache::read(Addr addr, size_t size)
{
    Trace trace;

    trace.push_back(std::make_unique<TagLookup>(*this, addr));
    trace.back()->perform(trace);
    const bool hit = static_cast<TagLookup*>(trace.back().get())->wasHit();

    if (hit) {
        return trace;
    }

    // Miss: defer to the next level, then splice its trace in.
    Trace below = next_level_->read(addr, size);
    for (auto& a : below) {
        trace.push_back(std::move(a));
    }

    // Install the line locally. LineFill::perform decides whether to evict.
    trace.push_back(std::make_unique<LineFill>(*this, addr));
    trace.back()->perform(trace);

    return trace;
}

Trace Cache::write(Addr addr, size_t size)
{
    // TODO: write policies (WriteBack/WriteThrough x Alloc/NoAlloc).
    (void)addr;
    (void)size;
    return {};
}


// --- Cache::TagLookup ---------------------------------------------------

Cache::TagLookup::TagLookup(Cache& cache, Addr byte_addr)
    : cache_(cache), byte_addr_(byte_addr), cost_(cache.accessCycles())
{
}

void Cache::TagLookup::perform(Trace& /*trace*/)
{
    ++count_;

    const Addr line = cache_.lineAddr(byte_addr_);
    if (cache_.setFor(byte_addr_).lookup(line)) {
        hit_ = true;
        ++cache_.hits_;
    } else {
        hit_ = false;
        ++cache_.misses_;
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
    ++count_;

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
    ++count_;

    cache_.sets_[victim_line_addr_ % cache_.sets_.size()].remove(
        victim_line_addr_);
}

void Cache::Evict::print(std::ostream& os) const
{
    os << cache_.name_ << " Evict line=0x" << std::hex
       << victim_line_addr_ << std::dec
       << (dirty_ ? " (dirty)" : " (clean)");
}
