#include "mainmem_actions.h"

#include <ostream>


void MemoryAccess::print(std::ostream& os) const
{
    os << "MemoryAccess @0x" << std::hex << addr_ << std::dec << " ("
       << cost_ << " cy)";
}
