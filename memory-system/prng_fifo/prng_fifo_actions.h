#pragma once

#include "../action.h"
#include "../../utils.h"

#include <cstddef>


// Action records emitted by PrngFifoDev. Pure data: all FIFO state mutation
// (start/stop, generation catch-up, pop, stall accounting) happens inside
// PrngFifoDev::read/write, which then constructs the appropriate witness.

class FifoControlWrite : public Action
{
  public:
    FifoControlWrite(Addr addr, Addr start_addr, uint cost)
        : addr_(addr), start_addr_(start_addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::ControlWrite"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    Addr start_addr_;   // remembered just to render START vs STOP
    uint cost_;
};

class FifoSeedWrite : public Action
{
  public:
    FifoSeedWrite(Addr addr, uint cost) : addr_(addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::SeedWrite"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};

class FifoReadFifo : public Action
{
  public:
    FifoReadFifo(Addr addr, uint cost, uint stall_cycles)
        : addr_(addr), cost_(cost), stall_cycles_(stall_cycles) {}

    uint cyclesToPerform() const override { return cost_ + stall_cycles_; }
    const char* name() const override     { return "PrngFifoDev::ReadFifo"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
    uint stall_cycles_;
};

class FifoGenerateElement : public Action
{
  public:
    FifoGenerateElement(size_t ready_cycle, uint cost)
        : ready_cycle_(ready_cycle), cost_(cost) {}

    uint cyclesToPerform() const override { return 0; }   // accounted for in ReadFifo's stall
    const char* name() const override     { return "PrngFifoDev::GenerateElement"; }
    void print(std::ostream& os) const override;

  private:
    size_t ready_cycle_;
    uint   cost_;
};

class FifoRegisterRead : public Action
{
  public:
    FifoRegisterRead(Addr addr, uint cost) : addr_(addr), cost_(cost) {}

    uint cyclesToPerform() const override { return cost_; }
    const char* name() const override     { return "PrngFifoDev::RegisterRead"; }
    void print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};
