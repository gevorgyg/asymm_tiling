#pragma once

#include "../utils.h"

#include <memory>
#include <numeric>
#include <ostream>
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
//
// Actions may be composite: an Action that wraps a body of child Actions
// (e.g. an instruction containing per-element accesses, an access containing
// the cache events it triggered) returns a non-null pointer from children().
// Leaf Actions return nullptr.

class Action;
using Trace = std::vector<std::unique_ptr<Action>>;

class Action
{
  public:
    virtual ~Action() = default;

    virtual uint cyclesToPerform() const       = 0;
    virtual const char* name() const           = 0;
    virtual void print(std::ostream& os) const = 0;

    virtual const Trace* children() const { return nullptr; }
};

inline static uint totalCycles(const Trace& trace)
{
    return std::accumulate(trace.begin(), trace.end(), 0u,
                           [](uint acc, const std::unique_ptr<Action>& a) {
                               return acc + a->cyclesToPerform();
                           });
}

// Walk an Action tree, printing one line per node with depth-based indentation.
// Recursion stops once depth exceeds max_depth; this maps trace verbosity onto
// tree depth (instructions at 0, per-access summaries at 1, leaf events at 2).
inline void printAction(std::ostream& os, const Action& a,
                        uint depth, uint max_depth)
{
    if (depth > max_depth) return;
    for (uint i = 0; i < depth; ++i) os << "  ";
    a.print(os);
    os << '\n';
    if (depth == max_depth) return;
    if (const Trace* kids = a.children()) {
        for (const auto& c : *kids) printAction(os, *c, depth + 1, max_depth);
    }
}

inline void printTrace(std::ostream& os, const Trace& trace,
                       uint depth, uint max_depth)
{
    for (const auto& a : trace) printAction(os, *a, depth, max_depth);
}
