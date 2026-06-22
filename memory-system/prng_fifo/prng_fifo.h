#pragma once

#include "../action.h"
#include "../memory_object.h"

#include <cstdint>
#include <queue>


// Cycle-accurate MMIO PRNG generator. Background-generates elements at a
// constant rate while `active_`, buffering them in a FIFO of bounded
// capacity. Reads at the data port pop from the FIFO; an empty FIFO stalls
// the CPU until the next element is ready. The FIFO state is advanced
// lazily by catchUp() right before each data-port read.
class PrngFifoDev : public MemoryObject
{
  public:
    struct InitParameters {
        Addr   ctrl_start_addr;   // MMIO start register
        Addr   ctrl_stop_addr;    // MMIO stop register
        Addr   seed_addr;         // MMIO seed register
        Addr   data_start_addr;   // MMIO data window start
        Addr   data_end_addr;     // MMIO data window end
        uint   access_cycles;     // MMIO register read/write overhead
        size_t fifo_capacity;     // max elements in FIFO
        uint   gen_cost;          // cycles per generated element
    };

    struct Stats {
        uint64_t starts       = 0;
        uint64_t stops        = 0;
        uint64_t reads        = 0;
        uint64_t stalls       = 0;
        uint64_t stall_cycles = 0;
        uint64_t generates    = 0;
    };

    PrngFifoDev(InitParameters p, const size_t& cpu_cycles);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    bool contains(Addr addr) const;

    void catchUp(size_t current_cycle);

    const Stats& stats() const { return stats_; }

  private:
    Addr   ctrl_start_addr_;
    Addr   ctrl_stop_addr_;
    Addr   seed_addr_;
    Addr   data_start_addr_;
    Addr   data_end_addr_;
    size_t fifo_capacity_;
    uint   gen_cost_;

    const size_t& cpu_cycles_;

    uint64_t seed_;
    bool     active_;
    bool     paused_;
    size_t   last_update_cycle_;

    std::queue<size_t> ready_cycles_;
    Stats stats_;
};
