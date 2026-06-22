#pragma once

#include "set.h"

#include <string>


// Two-policy enum is enough today; a strategy hierarchy would dwarf the
// actual logic (both policies evict the front; only recordAccess differs).
enum class Policy { LRU, FIFO };

const char* policyName(Policy p);
Policy      parsePolicy(const std::string& name);

CacheLine* pickVictim(Policy p, Set& set);
void       recordAccess(Policy p, Set& set, Addr line_addr);
