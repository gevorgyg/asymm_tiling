#include "hierarchy.h"
#include <ostream>

// Inline helper action to output PRNG logging parameters cleanly
class PrngAction : public Action
{
  public:
    PrngAction(Addr addr) : addr_(addr)
    {
    }
    void perform(Trace& /*trace*/) override
    {
    }
    uint cyclesToPerform() const override
    {
        return 0;
    } // Managed internally by prng_dev_ clock updates
    const char* name() const override
    {
        return "PrngAccess";
    }
    void print(std::ostream& os) const override
    {
        os << "PRNG MMIO Device Read @0x" << std::hex << addr_ << std::dec;
    }

  private:
    Addr addr_;
};

MemoryHierarchy::MemoryHierarchy(Parameters p, size_t& cpu_cycles)
    : MemoryObject(0), mem_(p.mem_access_cycles),
      l2_(p.l2_access_cycles, p.l2, std::make_unique<FifoPolicy>(), &mem_),
      l1_(p.l1_access_cycles, p.l1, std::make_unique<FifoPolicy>(), &l2_),
      prng_dev_(cpu_cycles)
{
}

void MemoryHierarchy::read(Addr addr, size_t size, Trace& trace)
{
    if (magic_addr_ != 0 && addr >= magic_addr_) {
        prng_dev_.pop();
        trace.push_back(std::make_unique<PrngAction>(addr));
        return;
    }
    l1_.read(addr, size, trace);
}

void MemoryHierarchy::write(Addr addr, size_t size, Trace& trace)
{
    if (magic_addr_ != 0 && addr >= magic_addr_) {
        trace.push_back(std::make_unique<PrngAction>(addr));
        return;
    }
    l1_.write(addr, size, trace);
}

void MemoryHierarchy::reseedPrng(Addr base_addr, Trace& trace)
{
    Addr tile_offset = base_addr - magic_addr_;
    Addr seed_addr   = seed_mem_base + tile_offset;

    read(seed_addr, 4, trace);
    prng_dev_.reseed();
}
