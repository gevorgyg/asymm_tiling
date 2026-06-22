#include "prng_actions.h"

#include <ostream>


void IsGenerated::print(std::ostream& os) const
{
    os << "PRNG IsGenerated @0x" << std::hex << byte_addr_ << std::dec << " "
       << (generated_ ? "YES" : "NO") << " (" << cost_ << " cy)";
}

void Generate::print(std::ostream& os) const
{
    os << "PRNG Generate line @0x" << std::hex << line_base_ << std::dec
       << " (" << cost_ << " cy)" << (regen_ ? " REGEN" : "");
}
