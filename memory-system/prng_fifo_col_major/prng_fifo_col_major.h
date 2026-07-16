#pragma once

#include "../action.h"
#include "../memory_object.h"

#include <cstdint>
#include <vector>


// Column-major double-buffered PRNG FIFO for C-stationary (output-stationary) dataflow.
//
// Generates B sub-tiles one column at a time: for fixed rj, all rk values in
// generation order. A prefill buffer generates the next column in the background
// while the current column is consumed. The current column can be read multiple
// times (once per ri) before swapping — the device keeps all col_capacity
// elements and serves reads circularly.
//
// MMIO map:
//   START_REG  write: begin generating next column into prefill buffer
//   SWAP_REG   write: promote prefill → current, reset read position to 0
//   STOP_REG   write: stop everything, clear all state
//   DATA_REG   read:  next sub-tile from current column (circular: wraps at col_capacity)
class PrngFifoColMajorDev : public MemoryObject
{
  public:
    struct InitParameters {
        Addr   start_addr;
        Addr   swap_addr;
        Addr   stop_addr;
        Addr   data_start_addr;
        Addr   data_end_addr;
        uint   access_cycles;
        size_t col_capacity;   // sub-tiles per column (= K_tiles × tile_k / reg_k)
        uint   gen_cost;       // cycles per sub-tile generated
    };

    struct Stats {
        uint64_t starts            = 0;
        uint64_t swaps             = 0;
        uint64_t stops             = 0;
        uint64_t reads             = 0;   // total reads (includes re-reads)
        uint64_t stalls            = 0;
        uint64_t stall_cycles      = 0;
        uint64_t prefill_generates = 0;   // elements generated in background prefill
        uint64_t generates         = 0;   // elements generated on-demand after promotion
    };

    PrngFifoColMajorDev(InitParameters p, const size_t& cpu_cycles);

    void read(Addr addr, size_t size, Trace& trace) override;
    void write(Addr addr, size_t size, Trace& trace) override;

    bool contains(Addr addr) const;

    const Stats& stats() const { return stats_; }

  private:
    void catchUpPrefill(size_t cycle);
    void catchUpCurrent(size_t cycle);

    Addr   start_addr_;
    Addr   swap_addr_;
    Addr   stop_addr_;
    Addr   data_start_addr_;
    Addr   data_end_addr_;
    size_t col_capacity_;
    uint   gen_cost_;

    const size_t& cpu_cycles_;

    // Current buffer: ready-cycle timestamps for each sub-tile [0..col_capacity_).
    // Grows as generation proceeds; reads wrap circularly.
    std::vector<size_t> current_ready_;
    bool   current_active_      = false;
    bool   current_paused_      = false;
    size_t current_last_update_ = 0;
    size_t read_pos_            = 0;

    // Prefill buffer: next column generating in background.
    std::vector<size_t> prefill_ready_;
    bool   prefill_active_      = false;
    bool   prefill_paused_      = false;
    size_t prefill_last_update_ = 0;

    Stats stats_;
};
