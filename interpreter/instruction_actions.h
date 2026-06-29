#pragma once

#include "../memory-system/action.h"
#include "../utils.h"

#include <iosfwd>
#include <string>
#include <utility>


// One CPU memory access (read or write to a single element). Wraps the
// device Trace produced by MemoryHierarchy::access -- those leaf cache /
// MainMemory Actions become this Access's children, and its cycle cost is
// just their sum.
class Access : public Action
{
  public:
    Access(const char* op, Addr addr, Trace body)
        : op_(op), addr_(addr), body_(std::move(body)) {}

    uint        cyclesToPerform() const override { return totalCycles(body_); }
    const char* name() const override            { return op_; }
    void        print(std::ostream& os) const override;
    const Trace* children() const override       { return &body_; }

  private:
    const char* op_;
    Addr        addr_;
    Trace       body_;
};


// One ISA instruction. Children are whatever the handler emitted
// (per-element Access wrappers, MulAcc, ...); the printed cycle total is
// the sum over them.
class Instruction : public Action
{
  public:
    Instruction(std::string header, Trace body)
        : header_(std::move(header)), body_(std::move(body)) {}

    uint        cyclesToPerform() const override { return totalCycles(body_); }
    const char* name() const override            { return "Instruction"; }
    void        print(std::ostream& os) const override;
    const Trace* children() const override       { return &body_; }

  private:
    std::string header_;
    Trace       body_;
};
