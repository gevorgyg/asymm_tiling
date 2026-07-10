#include "prng_fifo.h"
#include "prng_fifo_actions.h"

#include <cassert>
#include <iostream>


PrngFifoDev::PrngFifoDev(InitParameters p, const size_t& cpu_cycles)
    : MemoryObject(p.access_cycles),
      ctrl_start_addr_(p.ctrl_start_addr),
      ctrl_stop_addr_(p.ctrl_stop_addr),
      seed_addr_(p.seed_addr),
      data_start_addr_(p.data_start_addr),
      data_end_addr_(p.data_end_addr),
      fifo_capacity_(p.fifo_capacity),
      gen_cost_(p.gen_cost),
      cpu_cycles_(cpu_cycles),
      seed_(0),
      active_(false),
      paused_(false),
      last_update_cycle_(0)
{
    // gen_cost_ == 0 is valid: elements are generated instantly (no stalls ever).
}

bool PrngFifoDev::contains(Addr addr) const
{
    if (fifo_capacity_ == 0) return false;
    return addr == ctrl_start_addr_ ||
           addr == ctrl_stop_addr_ ||
           addr == seed_addr_ ||
           (addr >= data_start_addr_ && addr < data_end_addr_);
}

void PrngFifoDev::catchUp(size_t current_cycle)
{
    if (!active_ || paused_) return;

    if (gen_cost_ == 0) {
        while (ready_cycles_.size() < fifo_capacity_) {
            ready_cycles_.push(current_cycle);
            ++stats_.generates;
        }
        paused_ = true;
        return;
    }

    while (last_update_cycle_ + gen_cost_ <= current_cycle) {
        last_update_cycle_ += gen_cost_;
        ready_cycles_.push(last_update_cycle_);
        ++stats_.generates;

        if (ready_cycles_.size() == fifo_capacity_) {
            paused_ = true;
            break;
        }
    }
}

void PrngFifoDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    // Control / seed register reads are stateless witnesses.
    if (addr < data_start_addr_ || addr >= data_end_addr_) {
        trace.push_back(std::make_unique<FifoRegisterRead>(addr, accessCycles()));
        return;
    }

    // Data port read: try to satisfy from the FIFO, stall if it is empty.
    catchUp(cpu_cycles_);

    uint stall = 0;
    if (ready_cycles_.empty()) {
        const size_t next_ready = last_update_cycle_ + gen_cost_;
        assert(next_ready > cpu_cycles_);
        stall = static_cast<uint>(next_ready - cpu_cycles_);
        ++stats_.stalls;
        stats_.stall_cycles += stall;
        trace.push_back(std::make_unique<FifoGenerateElement>(next_ready, gen_cost_));
        catchUp(next_ready);
    }
    assert(!ready_cycles_.empty());
    ready_cycles_.pop();
    ++stats_.reads;

    // Resuming from a full-FIFO pause: the slot we just freed lets the
    // generator run again starting from the cycle this read completes.
    if (paused_) {
        paused_ = false;
        last_update_cycle_ = cpu_cycles_ + stall;
        catchUp(cpu_cycles_ + stall);
    }

    trace.push_back(std::make_unique<FifoReadFifo>(addr, accessCycles(), stall));
}

void PrngFifoDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    if (addr == ctrl_start_addr_) {
        ++stats_.starts;
        if (!active_) {
            active_ = true;
            paused_ = false;
            last_update_cycle_ = cpu_cycles_;
        }
        trace.push_back(std::make_unique<FifoControlWrite>(addr, ctrl_start_addr_, accessCycles()));
        return;
    }
    if (addr == ctrl_stop_addr_) {
        ++stats_.stops;
        active_ = false;
        paused_ = false;
        while (!ready_cycles_.empty()) {
            ready_cycles_.pop();
        }
        trace.push_back(std::make_unique<FifoControlWrite>(addr, ctrl_start_addr_, accessCycles()));
        return;
    }
    if (addr == seed_addr_) {
        trace.push_back(std::make_unique<FifoSeedWrite>(addr, accessCycles()));
        return;
    }

    std::cerr << "PRNG FIFO data port is read-only: write @0x" << std::hex << addr
              << std::dec << std::endl;
    exit(1);
}
