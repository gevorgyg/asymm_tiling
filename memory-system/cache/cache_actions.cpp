#include "cache_actions.h"

#include <ostream>


void TagLookup::print(std::ostream& os) const
{
    os << cache_ << " TagLookup @0x" << std::hex << byte_addr_ << std::dec
       << ' ' << (hit_ ? "HIT" : "MISS") << " (" << cost_ << " cy)";
}

void LineFill::print(std::ostream& os) const
{
    os << cache_ << " LineFill @0x" << std::hex << byte_addr_ << std::dec;
}

void Evict::print(std::ostream& os) const
{
    os << cache_ << " Evict line=0x" << std::hex << victim_line_addr_
       << std::dec << (dirty_ ? " (dirty)" : " (clean)");
}
