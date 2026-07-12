#include "prng_fifo_pipelined.h"
#include "../prng_fifo/prng_fifo_actions.h"

#include <cassert>
#include <iostream>


PrngFifoPipelinedDev::PrngFifoPipelinedDev(InitParameters p, const size_t& cpu_cycles)
    : MemoryObject(p.access_cycles),
      pref_seed_addr_(p.pref_seed_addr),
      pref_start_addr_(p.pref_start_addr),
      swap_addr_(p.swap_addr),
      stop_addr_(p.stop_addr),
      data_start_addr_(p.data_start_addr),
      data_end_addr_(p.data_end_addr),
      fifo_capacity_(p.fifo_capacity),
      gen_cost_(p.gen_cost),
      num_prefill_(p.num_prefill ? p.num_prefill : 1),
      cpu_cycles_(cpu_cycles),
      current_active_(false),
      current_paused_(false),
      current_last_update_(0)
{
    // gen_cost_ == 0 is valid: elements are generated instantly (no stalls ever).
}

bool PrngFifoPipelinedDev::contains(Addr addr) const
{
    if (fifo_capacity_ == 0) return false;
    return addr == pref_seed_addr_  ||
           addr == pref_start_addr_ ||
           addr == swap_addr_       ||
           addr == stop_addr_       ||
           (addr >= data_start_addr_ && addr < data_end_addr_);
}

void PrngFifoPipelinedDev::catchUpCurrent(size_t cycle)
{
    if (!current_active_ || current_paused_) return;
    if (gen_cost_ == 0) {
        while (current_ready_.size() < fifo_capacity_) {
            current_ready_.push(cycle);
            ++stats_.generates;
        }
        current_paused_ = true;
        return;
    }
    while (current_last_update_ + gen_cost_ <= cycle) {
        current_last_update_ += gen_cost_;
        current_ready_.push(current_last_update_);
        ++stats_.generates;
        if (current_ready_.size() == fifo_capacity_) {
            current_paused_ = true;
            break;
        }
    }
}

void PrngFifoPipelinedDev::catchUpSlot(PrefillSlot& slot, size_t cycle)
{
    if (!slot.active || slot.paused) return;
    if (gen_cost_ == 0) {
        while (slot.ready.size() < fifo_capacity_) {
            slot.ready.push(cycle);
            ++stats_.prefill_generates;
        }
        slot.paused = true;
        return;
    }
    while (slot.last_update + gen_cost_ <= cycle) {
        slot.last_update += gen_cost_;
        slot.ready.push(slot.last_update);
        ++stats_.prefill_generates;
        if (slot.ready.size() == fifo_capacity_) {
            slot.paused = true;
            break;
        }
    }
}

void PrngFifoPipelinedDev::catchUpAllPrefill(size_t cycle)
{
    for (auto& slot : prefill_queue_)
        catchUpSlot(slot, cycle);
}

void PrngFifoPipelinedDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));
    assert(addr >= data_start_addr_ && addr < data_end_addr_);
    assert(current_active_ && "DATA_REG read before any SWAP");

    // Advance all generators to the current CPU cycle.
    catchUpAllPrefill(cpu_cycles_);
    catchUpCurrent(cpu_cycles_);

    uint stall = 0;
    if (current_ready_.empty()) {
        // Current generator hasn't produced the next element yet → stall.
        const size_t next_ready = current_last_update_ + gen_cost_;
        assert(next_ready > cpu_cycles_);
        stall = static_cast<uint>(next_ready - cpu_cycles_);
        ++stats_.stalls;
        stats_.stall_cycles += stall;
        trace.push_back(std::make_unique<FifoGenerateElement>(next_ready, gen_cost_));
        catchUpCurrent(next_ready);
    }

    assert(!current_ready_.empty());
    current_ready_.pop();
    ++stats_.reads;

    // Unpause current generator if the consumed slot freed capacity.
    if (current_paused_) {
        current_paused_ = false;
        current_last_update_ = cpu_cycles_ + stall;
        catchUpCurrent(cpu_cycles_ + stall);
    }

    trace.push_back(std::make_unique<FifoReadFifo>(addr, accessCycles(), stall));
}

void PrngFifoPipelinedDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    if (addr == pref_seed_addr_) {
        trace.push_back(std::make_unique<FifoSeedWrite>(addr, accessCycles()));
        return;
    }

    if (addr == pref_start_addr_) {
        ++stats_.starts;
        PrefillSlot slot;
        slot.active      = true;
        slot.last_update = cpu_cycles_;
        prefill_queue_.push_back(std::move(slot));
        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    if (addr == swap_addr_) {
        ++stats_.swaps;
        // Bring all prefill buffers up to date, then hand the oldest to current.
        catchUpAllPrefill(cpu_cycles_);
        assert(!prefill_queue_.empty() && "SWAP with empty prefill queue");

        PrefillSlot& front = prefill_queue_.front();
        current_ready_       = std::move(front.ready);
        current_last_update_ = front.last_update;
        current_active_      = true;
        current_paused_      = false;
        prefill_queue_.pop_front();

        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    if (addr == stop_addr_) {
        ++stats_.stops;
        current_active_      = false;
        current_paused_      = false;
        current_ready_       = std::queue<size_t>{};
        prefill_queue_.clear();
        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    std::cerr << "PrngFifoPipelinedDev: unexpected write @0x"
              << std::hex << addr << std::dec << '\n';
    exit(1);
}
