#pragma once

#include "../action.h"
#include "../../utils.h"

#include <iosfwd>


// Records one access to main memory. Pure data: the cost is captured at
// construction by MainMemory::read/write.
class MemoryAccess : public Action
{
  public:
    MemoryAccess(uint cost, Addr addr) : addr_(addr), cost_(cost) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "MemoryAccess"; }
    void        print(std::ostream& os) const override;

  private:
    Addr addr_;
    uint cost_;
};
