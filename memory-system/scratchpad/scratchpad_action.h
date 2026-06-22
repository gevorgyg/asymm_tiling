#pragma once

#include "../action.h"
#include <ostream>

enum class ScratchpadOp
{
    READ,
    WRITE
};

class ScratchpadAction : public Action
{
  public:
    ScratchpadAction(ScratchpadOp op, Addr addr, uint w, uint h, uint cycles)
        : op_(op), addr_(addr), w_(w), h_(h), cycles_(cycles) {}

    uint        cyclesToPerform() const override { return cycles_; }
    const char* name() const override            { return "Scratchpad"; }
    void        print(std::ostream& os) const override {
        os << "Scratchpad " << (op_ == ScratchpadOp::WRITE ? "write" : "read")
           << " @0x" << std::hex << addr_ << std::dec
           << " (" << w_ << "x" << h_ << ") (" << cycles_ << " cy)";
    }

  private:
    ScratchpadOp op_;
    Addr         addr_;
    uint         w_;
    uint         h_;
    uint         cycles_;
};
