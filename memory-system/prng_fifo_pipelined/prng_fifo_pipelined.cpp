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
      cpu_cycles_(cpu_cycles),
      current_active_(false),
      current_paused_(false),
      current_last_update_(0),
      prefill_active_(false),
      prefill_paused_(false),
      prefill_last_update_(0)
{
    if (fifo_capacity_ > 0)
        assert(gen_cost_ > 0);
}

bool PrngFifoPipelinedDev::contains(Addr addr) const
{
    if (fifo_capacity_ == 0) return false;
    return addr == pref_seed_addr_  ||
           addr == pref_start_addr_ ||
           addr == swap_addr_        ||
           addr == stop_addr_        ||
           (addr >= data_start_addr_ && addr < data_end_addr_);
}

void PrngFifoPipelinedDev::catchUpCurrent(size_t cycle)
{
    if (!current_active_ || current_paused_) return;
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

void PrngFifoPipelinedDev::catchUpPrefill(size_t cycle)
{
    if (!prefill_active_ || prefill_paused_) return;
    while (prefill_last_update_ + gen_cost_ <= cycle) {
        prefill_last_update_ += gen_cost_;
        prefill_ready_.push(prefill_last_update_);
        ++stats_.prefill_generates;
        if (prefill_ready_.size() == fifo_capacity_) {
            prefill_paused_ = true;
            break;
        }
    }
}

void PrngFifoPipelinedDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));
    assert(addr >= data_start_addr_ && addr < data_end_addr_);
    assert(current_active_ && "DATA_REG read before any SWAP");

    // Advance both generators to the current CPU cycle.
    catchUpPrefill(cpu_cycles_);
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
        if (!prefill_active_) {
            prefill_active_      = true;
            prefill_paused_      = false;
            prefill_last_update_ = cpu_cycles_;
        }
        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    if (addr == swap_addr_) {
        ++stats_.swaps;
        // Bring prefill buffer up to date, then hand it to the current channel.
        catchUpPrefill(cpu_cycles_);

        current_ready_       = std::move(prefill_ready_);
        current_last_update_ = prefill_last_update_;
        current_active_      = true;
        current_paused_      = false;

        // Reset prefill for the next PREF_START.
        prefill_ready_ = std::queue<size_t>{};
        prefill_active_      = false;
        prefill_paused_      = false;
        prefill_last_update_ = 0;

        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    if (addr == stop_addr_) {
        ++stats_.stops;
        current_active_ = false;
        current_paused_ = false;
        prefill_active_ = false;
        prefill_paused_ = false;
        current_ready_  = std::queue<size_t>{};
        prefill_ready_  = std::queue<size_t>{};
        trace.push_back(std::make_unique<FifoControlWrite>(addr, pref_start_addr_, accessCycles()));
        return;
    }

    std::cerr << "PrngFifoPipelinedDev: unexpected write @0x"
              << std::hex << addr << std::dec << '\n';
    exit(1);
}
