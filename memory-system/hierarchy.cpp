#include "hierarchy.h"
#include "cache/eviction_policy.h"


void AddrRouter::read(Addr addr, size_t size, Trace& trace)
{
    if (prng_fifo_.contains(addr)) {
        prng_fifo_.read(addr, size, trace);
    } else if (prng_.contains(addr)) {
        prng_.read(addr, size, trace);
    } else {
        fallthrough_.read(addr, size, trace);
    }
}

void AddrRouter::write(Addr addr, size_t size, Trace& trace)
{
    if (prng_fifo_.contains(addr)) {
        prng_fifo_.write(addr, size, trace);
    } else if (prng_.contains(addr)) {
        prng_.write(addr, size, trace);
    } else {
        fallthrough_.write(addr, size, trace);
    }
}

MemoryHierarchy::MemoryHierarchy(Parameters p, const size_t& cpu_cycles)
    : MemoryObject(0),
      mem_(p.mem_access_cycles),
      l2_(p.l2_access_cycles, p.l2, createEvictionPolicy(p.l2_policy), &mem_),
      prng_(p.prng),
      prng_fifo_(p.prng_fifo, cpu_cycles),
      router_(prng_, prng_fifo_, l2_),
      l1_(p.l1_access_cycles, p.l1, createEvictionPolicy(p.l1_policy), &router_)
{
}

void MemoryHierarchy::read(Addr addr, size_t size, Trace& trace)
{
    if (prng_fifo_.contains(addr)) {
        prng_fifo_.read(addr, size, trace);
    } else {
        l1_.read(addr, size, trace);
    }
}

void MemoryHierarchy::write(Addr addr, size_t size, Trace& trace)
{
    if (prng_fifo_.contains(addr)) {
        prng_fifo_.write(addr, size, trace);
    } else {
        l1_.write(addr, size, trace);
    }
}
