#pragma once

#include "../action.h"
#include "../memory_object.h"

#include <cstdint>
#include <deque>
#include <queue>


// Multi-buffer pipelined extension of PrngFifoDev.
//
// N = num_prefill + 1 buffers in flight at once:
//   current               – serves DATA_REG reads
//   prefill[0..N-2]       – background generation for future sessions,
//                           growing as PREF_START is issued, shrinking on SWAP
//
// MMIO map (writes = control, reads = data):
//   0xFF200000  PREF_SEED_REG   set seed for the upcoming prefill session
//   0xFF200004  PREF_START_REG  enqueue a new prefill slot (starts immediately)
//   0xFF200008  SWAP_REG        pop oldest prefill slot → current; clear old current
//   0xFF20000C  STOP_REG        stop everything, clear all buffers
//   0xFF200010…0xFF300010  DATA_REG  read elements from current session
//
// With num_prefill=1 the behaviour is identical to the original dual-buffer device.
// With num_prefill=N, up to N sessions generate simultaneously; stall-free condition:
//   gc ≤ N × TM × α
class PrngFifoPipelinedDev : public MemoryObject
{
  public:
    struct InitParameters {
        Addr   pref_seed_addr;    // 0xFF200000
        Addr   pref_start_addr;   // 0xFF200004
        Addr   swap_addr;         // 0xFF200008
        Addr   stop_addr;         // 0xFF20000C
        Addr   data_start_addr;   // 0xFF200010
        Addr   data_end_addr;     // 0xFF300010
        uint   access_cycles;
        size_t fifo_capacity;     // per-buffer capacity in elements (0 = device disabled)
        uint   gen_cost;          // cycles to generate one element
        size_t num_prefill = 1;   // number of parallel prefill buffers
    };

    struct Stats {
        uint64_t starts           = 0;
        uint64_t stops            = 0;
        uint64_t swaps            = 0;
        uint64_t reads            = 0;
        uint64_t stalls           = 0;
        uint64_t stall_cycles     = 0;
        uint64_t generates        = 0;   // current channel (pre-promoted + on-demand)
        uint64_t prefill_generates = 0;  // all background prefill channels combined
    };

    PrngFifoPipelinedDev(InitParameters p, const size_t& cpu_cycles);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    bool contains(Addr addr) const;

    const Stats& stats() const { return stats_; }

  private:
    struct PrefillSlot {
        std::queue<size_t> ready;
        bool   active      = false;
        bool   paused      = false;
        size_t last_update = 0;
    };

    void catchUpCurrent(size_t cycle);
    void catchUpSlot(PrefillSlot& slot, size_t cycle);
    void catchUpAllPrefill(size_t cycle);

    Addr   pref_seed_addr_;
    Addr   pref_start_addr_;
    Addr   swap_addr_;
    Addr   stop_addr_;
    Addr   data_start_addr_;
    Addr   data_end_addr_;
    size_t fifo_capacity_;
    uint   gen_cost_;
    size_t num_prefill_;

    const size_t& cpu_cycles_;

    // Current channel – CPU reads from this
    std::queue<size_t> current_ready_;
    bool   current_active_;
    bool   current_paused_;
    size_t current_last_update_;

    // Prefill queue (front = oldest = next to be SWAPped in)
    std::deque<PrefillSlot> prefill_queue_;

    Stats stats_;
};
