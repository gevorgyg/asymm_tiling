#include "eviction_policy.h"

#include <cstdlib>
#include <iostream>


const char* policyName(Policy p)
{
    switch (p) {
        case Policy::LRU:    return "LRU";
        case Policy::FIFO:   return "FIFO";
        case Policy::MRU:    return "MRU";
        case Policy::Random: return "Random";
    }
    return "?";
}

Policy parsePolicy(const std::string& name)
{
    if (name == "LRU")    return Policy::LRU;
    if (name == "FIFO")   return Policy::FIFO;
    if (name == "MRU")    return Policy::MRU;
    if (name == "Random") return Policy::Random;
    std::cerr << "error: unknown eviction policy: " << name << std::endl;
    exit(1);
}
