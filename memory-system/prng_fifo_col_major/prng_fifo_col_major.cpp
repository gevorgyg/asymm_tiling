#include "prng_fifo_col_major.h"
#include "../prng_fifo/prng_fifo_actions.h"

#include <cassert>
#include <iostream>


PrngFifoColMajorDev::PrngFifoColMajorDev(InitParameters p, const size_t& cpu_cycles)
    : MemoryObject(p.access_cycles),
      start_addr_(p.start_addr),
      swap_addr_(p.swap_addr),
      stop_addr_(p.stop_addr),
      data_start_addr_(p.data_start_addr),
      data_end_addr_(p.data_end_addr),
      col_capacity_(p.col_capacity),
      gen_cost_(p.gen_cost),
      cpu_cycles_(cpu_cycles)
{}

bool PrngFifoColMajorDev::contains(Addr addr) const
{
    if (col_capacity_ == 0) return false;
    return addr == start_addr_ ||
           addr == swap_addr_  ||
           addr == stop_addr_  ||
           (addr >= data_start_addr_ && addr < data_end_addr_);
}

void PrngFifoColMajorDev::catchUpPrefill(size_t cycle)
{
    if (!prefill_active_ || prefill_paused_) return;
    if (gen_cost_ == 0) {
        while (prefill_ready_.size() < col_capacity_) {
            prefill_ready_.push_back(cycle);
            ++stats_.prefill_generates;
        }
        prefill_paused_ = true;
        return;
    }
    while (prefill_ready_.size() < col_capacity_ &&
           prefill_last_update_ + gen_cost_ <= cycle) {
        prefill_last_update_ += gen_cost_;
        prefill_ready_.push_back(prefill_last_update_);
        ++stats_.prefill_generates;
    }
    if (prefill_ready_.size() == col_capacity_) prefill_paused_ = true;
}

void PrngFifoColMajorDev::catchUpCurrent(size_t cycle)
{
    if (!current_active_ || current_paused_) return;
    if (gen_cost_ == 0) {
        while (current_ready_.size() < col_capacity_) {
            current_ready_.push_back(cycle);
            ++stats_.generates;
        }
        current_paused_ = true;
        return;
    }
    while (current_ready_.size() < col_capacity_ &&
           current_last_update_ + gen_cost_ <= cycle) {
        current_last_update_ += gen_cost_;
        current_ready_.push_back(current_last_update_);
        ++stats_.generates;
    }
    if (current_ready_.size() == col_capacity_) current_paused_ = true;
}

void PrngFifoColMajorDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));
    assert(addr >= data_start_addr_ && addr < data_end_addr_);
    assert(current_active_ && "DATA read before SWAP");

    catchUpPrefill(cpu_cycles_);
    catchUpCurrent(cpu_cycles_);

    const size_t elem = read_pos_ % col_capacity_;

    uint stall = 0;
    if (elem >= current_ready_.size()) {
        // Element not generated yet — compute when it will be ready and stall.
        const size_t steps = elem - current_ready_.size() + 1;
        const size_t next_ready = current_last_update_ + gen_cost_ * steps;
        assert(next_ready > cpu_cycles_);
        stall = static_cast<uint>(next_ready - cpu_cycles_);
        ++stats_.stalls;
        stats_.stall_cycles += stall;
        trace.push_back(std::make_unique<FifoGenerateElement>(next_ready, gen_cost_));
        catchUpCurrent(next_ready);
    } else if (current_ready_[elem] > cpu_cycles_) {
        // Element is in the vector but its ready-cycle is still in the future.
        stall = static_cast<uint>(current_ready_[elem] - cpu_cycles_);
        ++stats_.stalls;
        stats_.stall_cycles += stall;
        trace.push_back(std::make_unique<FifoGenerateElement>(current_ready_[elem], gen_cost_));
    }

    ++read_pos_;
    ++stats_.reads;
    trace.push_back(std::make_unique<FifoReadFifo>(addr, accessCycles(), stall));
}

void PrngFifoColMajorDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    if (addr == start_addr_) {
        ++stats_.starts;
        prefill_ready_.clear();
        prefill_active_      = true;
        prefill_paused_      = false;
        prefill_last_update_ = cpu_cycles_;
        catchUpPrefill(cpu_cycles_);
        trace.push_back(std::make_unique<FifoControlWrite>(addr, start_addr_, accessCycles()));
        return;
    }

    if (addr == swap_addr_) {
        ++stats_.swaps;
        catchUpPrefill(cpu_cycles_);
        current_ready_       = std::move(prefill_ready_);
        current_last_update_ = prefill_last_update_;
        current_active_      = true;
        current_paused_      = prefill_paused_;
        prefill_ready_       = {};
        prefill_active_      = false;
        prefill_paused_      = false;
        read_pos_            = 0;
        trace.push_back(std::make_unique<FifoControlWrite>(addr, start_addr_, accessCycles()));
        return;
    }

    if (addr == stop_addr_) {
        ++stats_.stops;
        current_ready_  = {};
        current_active_ = false;
        current_paused_ = false;
        prefill_ready_  = {};
        prefill_active_ = false;
        prefill_paused_ = false;
        read_pos_       = 0;
        trace.push_back(std::make_unique<FifoControlWrite>(addr, start_addr_, accessCycles()));
        return;
    }

    std::cerr << "PrngFifoColMajorDev: unexpected write @0x"
              << std::hex << addr << std::dec << '\n';
    exit(1);
}
