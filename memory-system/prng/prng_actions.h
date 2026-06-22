#pragma once

#include "../action.h"
#include "../../utils.h"


// Action records emitted by PrngDev. Pure data: state mutation happens in
// PrngDev::read, which fills in `generated` / `regen` before constructing
// the witness.

class IsGenerated : public Action
{
  public:
    IsGenerated(Addr byte_addr, uint cost, bool generated)
        : byte_addr_(byte_addr), cost_(cost), generated_(generated) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "IsGenerated"; }
    void        print(std::ostream& os) const override;

  private:
    Addr byte_addr_;
    uint cost_;
    bool generated_;
};


class Generate : public Action
{
  public:
    Generate(Addr line_base, uint cost, bool regen)
        : line_base_(line_base), cost_(cost), regen_(regen) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "Generate"; }
    void        print(std::ostream& os) const override;

  private:
    Addr line_base_;
    uint cost_;
    bool regen_;
};
