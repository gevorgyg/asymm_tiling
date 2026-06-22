#pragma once

#include "../action.h"
#include "../../utils.h"


// Action records emitted by Cache. Pure data: hit/miss/dirty state is
// computed by Cache::probe / Cache::fillLine before constructing the witness.
// The `cache` string is the cache's name ("L1" / "L2"), propagated so each
// event prints in the right level.

class TagLookup : public Action
{
  public:
    TagLookup(const char* cache, Addr byte_addr, uint cost, bool hit)
        : cache_(cache), byte_addr_(byte_addr), cost_(cost), hit_(hit) {}

    uint        cyclesToPerform() const override { return cost_; }
    const char* name() const override            { return "TagLookup"; }
    void        print(std::ostream& os) const override;

  private:
    const char* cache_;
    Addr        byte_addr_;
    uint        cost_;
    bool        hit_;
};


class LineFill : public Action
{
  public:
    LineFill(const char* cache, Addr byte_addr)
        : cache_(cache), byte_addr_(byte_addr) {}

    uint        cyclesToPerform() const override { return 0; }
    const char* name() const override            { return "LineFill"; }
    void        print(std::ostream& os) const override;

  private:
    const char* cache_;
    Addr        byte_addr_;
};


class Evict : public Action
{
  public:
    Evict(const char* cache, Addr victim_line_addr, bool dirty)
        : cache_(cache), victim_line_addr_(victim_line_addr), dirty_(dirty) {}

    uint        cyclesToPerform() const override { return 0; }
    const char* name() const override            { return "Evict"; }
    void        print(std::ostream& os) const override;

  private:
    const char* cache_;
    Addr        victim_line_addr_;
    bool        dirty_;
};
