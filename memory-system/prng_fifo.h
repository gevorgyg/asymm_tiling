#pragma once

#include "action.h"
#include "memory_object.h"

#include <cstdint>
#include <queue>
#include <iosfwd>

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
        size_t fifo_capacity;     // Max elements in FIFO
        uint   gen_cost;          // Cycles per generated element
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

    class ControlWrite;
    class SeedWrite;
    class ReadFifo;
    class GenerateElement;
    class RegisterRead;

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


// --- Action subclasses: pure-data records of FIFO events. -------------------

class PrngFifoDev::ControlWrite : public Action
{
  public:
    ControlWrite(Addr addr, Addr start_addr, uint cost)
        : addr_(addr), start_addr_(start_addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::ControlWrite"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    Addr start_addr_;  // remembered just to render START vs STOP
    uint cost_;
};

class PrngFifoDev::SeedWrite : public Action
{
  public:
    SeedWrite(Addr addr, uint cost) : addr_(addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::SeedWrite"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};

class PrngFifoDev::ReadFifo : public Action
{
  public:
    ReadFifo(Addr addr, uint cost, uint stall_cycles)
        : addr_(addr), cost_(cost), stall_cycles_(stall_cycles) {}

    uint cyclesToPerform() const override { return cost_ + stall_cycles_; }
    const char* name() const override     { return "PrngFifoDev::ReadFifo"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
    uint stall_cycles_;
};

class PrngFifoDev::GenerateElement : public Action
{
  public:
    GenerateElement(size_t ready_cycle, uint cost)
        : ready_cycle_(ready_cycle), cost_(cost) {}

    uint cyclesToPerform() const override { return 0; }  // accounted for in ReadFifo stall
    const char* name() const override     { return "PrngFifoDev::GenerateElement"; }
    void print(std::ostream& os) const override;

  private:
    size_t ready_cycle_;
    uint   cost_;
};

class PrngFifoDev::RegisterRead : public Action
{
  public:
    RegisterRead(Addr addr, uint cost) : addr_(addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::RegisterRead"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};
