#include "prng_fifo_actions.h"

#include <ostream>


void FifoControlWrite::print(std::ostream& os) const
{
    os << "PRNG_FIFO ControlWrite " << (addr_ == start_addr_ ? "START" : "STOP")
       << " @0x" << std::hex << addr_ << std::dec << " (" << cost_ << " cy)";
}

void FifoSeedWrite::print(std::ostream& os) const
{
    os << "PRNG_FIFO SeedWrite @0x" << std::hex << addr_ << std::dec
       << " (" << cost_ << " cy)";
}

void FifoReadFifo::print(std::ostream& os) const
{
    os << "PRNG_FIFO ReadFifo @0x" << std::hex << addr_ << std::dec
       << " (" << cost_ << " cy)";
    if (stall_cycles_ > 0) {
        os << " [STALL " << stall_cycles_ << " cy]";
    }
}

void FifoGenerateElement::print(std::ostream& os) const
{
    os << "PRNG_FIFO GenerateElement, ready at " << ready_cycle_
       << " (" << cost_ << " cy)";
}

void FifoRegisterRead::print(std::ostream& os) const
{
    os << "PRNG_FIFO RegisterRead @0x" << std::hex << addr_ << std::dec
       << " (" << cost_ << " cy)";
}
