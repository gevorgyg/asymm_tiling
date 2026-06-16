#include "prng_fifo.h"

#include <algorithm>
#include <cassert>
#include <iostream>
#include <ostream>


PrngFifoDev::PrngFifoDev(InitParameters p, const size_t& cpu_cycles)
    : MemoryObject(p.access_cycles),
      ctrl_start_addr_(p.ctrl_start_addr),
      ctrl_stop_addr_(p.ctrl_stop_addr),
      seed_addr_(p.seed_addr),
      data_start_addr_(p.data_start_addr),
      data_end_addr_(p.data_end_addr),
      fifo_capacity_(p.fifo_capacity),
      gen_cost_(p.gen_cost),
      cpu_cycles_(cpu_cycles),
      seed_(0),
      active_(false),
      paused_(false),
      last_update_cycle_(0)
{
    if (fifo_capacity_ > 0) {
        assert(gen_cost_ > 0);
    }
}

bool PrngFifoDev::contains(Addr addr) const
{
    if (fifo_capacity_ == 0) return false;
    return (addr == ctrl_start_addr_ ||
            addr == ctrl_stop_addr_ ||
            addr == seed_addr_ ||
            (addr >= data_start_addr_ && addr < data_end_addr_));
}

void PrngFifoDev::catchUp(size_t current_cycle)
{
    if (!active_ || paused_) return;

    while (last_update_cycle_ + gen_cost_ <= current_cycle) {
        last_update_cycle_ += gen_cost_;
        ready_cycles_.push(last_update_cycle_);
        ++stats_.generates;

        if (ready_cycles_.size() == fifo_capacity_) {
            paused_ = true;
            break;
        }
    }
}

void PrngFifoDev::read(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    if (addr >= data_start_addr_ && addr < data_end_addr_) {
        trace.push_back(std::make_unique<ReadFifo>(*this, addr));
        trace.back()->perform(trace);
    } else {
        // Standard register read (ctrl or seed status)
        class RegisterRead : public Action {
          public:
            RegisterRead(uint cost, Addr a) : cost_(cost), addr_(a) {}
            uint cyclesToPerform() const override { return cost_; }
            const char* name() const override { return "PrngFifoDev::RegisterRead"; }
            void print(std::ostream& os) const override {
                os << "PRNG_FIFO RegisterRead @0x" << std::hex << addr_ << std::dec << " (" << cost_ << " cy)";
            }
            void perform(Trace&) override {}
          private:
            uint cost_;
            Addr addr_;
        };
        trace.push_back(std::make_unique<RegisterRead>(access_cycles_, addr));
    }
}

void PrngFifoDev::write(Addr addr, size_t /*size*/, Trace& trace)
{
    assert(contains(addr));

    if (addr == ctrl_start_addr_ || addr == ctrl_stop_addr_) {
        trace.push_back(std::make_unique<ControlWrite>(*this, addr));
        trace.back()->perform(trace);
    } else if (addr == seed_addr_) {
        trace.push_back(std::make_unique<SeedWrite>(*this, addr));
        trace.back()->perform(trace);
    } else {
        std::cerr << "PRNG FIFO data port is read-only: write @0x" << std::hex << addr
                  << std::dec << std::endl;
        exit(1);
    }
}


// --- ControlWrite Implementation ---------------------------------------------

PrngFifoDev::ControlWrite::ControlWrite(PrngFifoDev& dev, Addr addr)
    : dev_(dev), addr_(addr), cost_(dev.accessCycles())
{
}

uint PrngFifoDev::ControlWrite::cyclesToPerform() const
{
    return cost_;
}

const char* PrngFifoDev::ControlWrite::name() const
{
    return "PrngFifoDev::ControlWrite";
}

void PrngFifoDev::ControlWrite::print(std::ostream& os) const
{
    os << "PRNG_FIFO ControlWrite " << (addr_ == dev_.ctrl_start_addr_ ? "START" : "STOP")
       << " @0x" << std::hex << addr_ << std::dec << " (" << cost_ << " cy)";
}

void PrngFifoDev::ControlWrite::perform(Trace& /*trace*/)
{
    if (addr_ == dev_.ctrl_start_addr_) {
        ++dev_.stats_.starts;
        if (!dev_.active_) {
            dev_.active_ = true;
            dev_.paused_ = false;
            dev_.last_update_cycle_ = dev_.cpu_cycles_;
        }
    } else if (addr_ == dev_.ctrl_stop_addr_) {
        ++dev_.stats_.stops;
        dev_.active_ = false;
        dev_.paused_ = false;
        while (!dev_.ready_cycles_.empty()) {
            dev_.ready_cycles_.pop();
        }
    }
}


// --- SeedWrite Implementation ------------------------------------------------

PrngFifoDev::SeedWrite::SeedWrite(PrngFifoDev& dev, Addr addr)
    : dev_(dev), addr_(addr), cost_(dev.accessCycles())
{
}

uint PrngFifoDev::SeedWrite::cyclesToPerform() const
{
    return cost_;
}

const char* PrngFifoDev::SeedWrite::name() const
{
    return "PrngFifoDev::SeedWrite";
}

void PrngFifoDev::SeedWrite::print(std::ostream& os) const
{
    os << "PRNG_FIFO SeedWrite @0x" << std::hex << addr_ << std::dec << " (" << cost_ << " cy)";
}

void PrngFifoDev::SeedWrite::perform(Trace& /*trace*/)
{
}


// --- ReadFifo Implementation -------------------------------------------------

PrngFifoDev::ReadFifo::ReadFifo(PrngFifoDev& dev, Addr addr)
    : dev_(dev), addr_(addr), cost_(dev.accessCycles()), stall_cycles_(0)
{
}

uint PrngFifoDev::ReadFifo::cyclesToPerform() const
{
    return cost_ + stall_cycles_;
}

const char* PrngFifoDev::ReadFifo::name() const
{
    return "PrngFifoDev::ReadFifo";
}

void PrngFifoDev::ReadFifo::print(std::ostream& os) const
{
    os << "PRNG_FIFO ReadFifo @0x" << std::hex << addr_ << std::dec << " (" << cost_ << " cy)";
    if (stall_cycles_ > 0) {
        os << " [STALL " << stall_cycles_ << " cy]";
    }
}

void PrngFifoDev::ReadFifo::perform(Trace& trace)
{
    dev_.catchUp(dev_.cpu_cycles_);

    if (dev_.ready_cycles_.empty()) {
        // FIFO is empty, we must stall!
        size_t next_ready = dev_.last_update_cycle_ + dev_.gen_cost_;
        assert(next_ready > dev_.cpu_cycles_);
        stall_cycles_ = next_ready - dev_.cpu_cycles_;
        ++dev_.stats_.stalls;
        dev_.stats_.stall_cycles += stall_cycles_;

        // Push a Generate action to show the stall-causing generation
        trace.push_back(std::make_unique<GenerateElement>(dev_, next_ready));

        // Catch up to the new cycle count (which includes the stall)
        dev_.catchUp(next_ready);
    }

    assert(!dev_.ready_cycles_.empty());
    dev_.ready_cycles_.pop();
    ++dev_.stats_.reads;

    // If we were paused, resume now that a slot has opened up
    if (dev_.paused_) {
        dev_.paused_ = false;
        dev_.last_update_cycle_ = dev_.cpu_cycles_ + stall_cycles_; // Resume from the end of the read/stall
        dev_.catchUp(dev_.cpu_cycles_ + stall_cycles_);
    }
}


// --- GenerateElement Implementation ------------------------------------------

PrngFifoDev::GenerateElement::GenerateElement(PrngFifoDev& dev, size_t ready_cycle)
    : dev_(dev), ready_cycle_(ready_cycle), cost_(dev.gen_cost_)
{
}

uint PrngFifoDev::GenerateElement::cyclesToPerform() const
{
    return 0; // Captured in ReadFifo stall
}

const char* PrngFifoDev::GenerateElement::name() const
{
    return "PrngFifoDev::GenerateElement";
}

void PrngFifoDev::GenerateElement::print(std::ostream& os) const
{
    os << "PRNG_FIFO GenerateElement, ready at " << ready_cycle_ << " (" << cost_ << " cy)";
}

void PrngFifoDev::GenerateElement::perform(Trace& /*trace*/)
{
}
