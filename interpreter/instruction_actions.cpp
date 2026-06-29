#include "instruction_actions.h"

#include <ostream>


void Access::print(std::ostream& os) const
{
    os << op_ << " @0x" << std::hex << addr_ << std::dec
       << " (" << cyclesToPerform() << " cy)";
}

void Instruction::print(std::ostream& os) const
{
    os << header_ << " (" << cyclesToPerform() << " cy)";
}
