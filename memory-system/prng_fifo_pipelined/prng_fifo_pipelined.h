#pragma once

#include "../action.h"
#include "../memory_object.h"

#include <cstdint>
#include <queue>


// Dual-buffer pipelined extension of PrngFifoDev.
//
// Two independent generation engines run in parallel:
//   current  – serves DATA_REG reads; receives a pre-filled snapshot via SWAP
//              and falls back to on-demand generation once the snapshot drains.
//   prefill  – runs silently in the background, accumulating elements for the
//              NEXT session so they are ready by the time SWAP is called.
//
// MMIO map (writes = control, reads = data):
//   0xFF200000  PREF_SEED_REG   set seed for the upcoming prefill session
//   0xFF200004  PREF_START_REG  start / restart background prefill
//   0xFF200008  SWAP_REG        swap prefill→current; clear old current
//   0xFF20000C  STOP_REG        stop everything, clear both buffers
//   0xFF200010…0xFF300010  DATA_REG  read elements from current session
//
// Steady-state speedup at gen_cost > crossover (~104 cycles/element for the
// 32×32 tile):  T_steady = gc*(T_comp + N*(gc-104)) / (2*gc - 104).
// For gc=512 this is ≈2.33M vs 4.19M cycles without pipelining (≈1.8× faster).
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
        size_t fifo_capacity;     // max elements per buffer (0 = device disabled)
        uint   gen_cost;          // cycles to generate one element
    };

    struct Stats {
        uint64_t starts           = 0;
        uint64_t stops            = 0;
        uint64_t swaps            = 0;
        uint64_t reads            = 0;
        uint64_t stalls           = 0;
        uint64_t stall_cycles     = 0;
        uint64_t generates        = 0;   // current channel (pre-promoted + on-demand)
        uint64_t prefill_generates = 0;  // background prefill channel
    };

    PrngFifoPipelinedDev(InitParameters p, const size_t& cpu_cycles);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    bool contains(Addr addr) const;

    const Stats& stats() const { return stats_; }

  private:
    void catchUpCurrent(size_t cycle);
    void catchUpPrefill(size_t cycle);

    Addr   pref_seed_addr_;
    Addr   pref_start_addr_;
    Addr   swap_addr_;
    Addr   stop_addr_;
    Addr   data_start_addr_;
    Addr   data_end_addr_;
    size_t fifo_capacity_;
    uint   gen_cost_;

    const size_t& cpu_cycles_;

    // Current channel – CPU reads from this
    std::queue<size_t> current_ready_;
    bool   current_active_;
    bool   current_paused_;
    size_t current_last_update_;

    // Prefill channel – background generation for the next session
    std::queue<size_t> prefill_ready_;
    bool   prefill_active_;
    bool   prefill_paused_;
    size_t prefill_last_update_;

    Stats stats_;
};
