#pragma once

#include "../../policies.h"
#include "set.h"


// Two-policy enum is enough today; a strategy hierarchy would dwarf the
// actual logic (both policies evict the front; only recordAccess differs).

const char* policyName(Policy p);

CacheLine* pickVictim(Policy p, Set& set);
void       recordAccess(Policy p, Set& set, Addr line_addr);
