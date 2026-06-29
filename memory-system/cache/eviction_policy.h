#pragma once

#include <string>

enum class Policy { LRU, FIFO, MRU, Random };

const char* policyName(Policy p);
Policy      parsePolicy(const std::string& name);
