#pragma once

#include "../../memory-system/action.h"
#include "../../utils.h"

#include <iosfwd>


// Single multiply-accumulate over the register-file tiles already loaded
// into %ra, %rb, %rc by preceding ltea instructions. Carries only the
// compute cost; any memory traffic for scalar-mode operands is emitted
// separately by the interpreter through doRead/doWrite.
class MulAcc : public Action
{
  public:
    explicit MulAcc(uint cost) : cost_(cost) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "MulAcc"; }
    void        print(std::ostream& os) const override;

  private:
    uint cost_;
};
