#pragma once

#include "../utils.h"

#include <iosfwd>
#include <memory>
#include <numeric>
#include <vector>

// An Action is a *record* of one textbook-level step a memory device took
// while handling a read or write -- the kind of thing you'd point at in a
// computer-architecture diagram (tag lookup, line fill, eviction, writeback).
//
// Actions are pure data: they carry the description and the cycle cost of an
// event that already happened. The device that produced them did all the
// state mutation already, then appended the Action as a witness.
//
// A request returns a Trace = sequence of Actions. Summing cyclesToPerform()
// over the Trace gives the access time. Iterating it tells you what the model
// captured and -- by their absence -- what it elides.

class Action;
using Trace = std::vector<std::unique_ptr<Action>>;

class Action
{
  public:
    virtual ~Action() = default;

    virtual uint cyclesToPerform() const       = 0;
    virtual const char* name() const           = 0;
    virtual void print(std::ostream& os) const = 0;
};

inline static uint totalCycles(const Trace& trace)
{
    return std::accumulate(trace.begin(), trace.end(), 0u,
                           [](uint acc, const std::unique_ptr<Action>& a) {
                               return acc + a->cyclesToPerform();
                           });
}
