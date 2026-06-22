#include "policies.h"

#include <cstdlib>
#include <iostream>


Policy parsePolicy(const std::string& name)
{
    if (name == "LRU")  return Policy::LRU;
    if (name == "FIFO") return Policy::FIFO;
    std::cerr << "error: unknown eviction policy: " << name << std::endl;
    exit(1);
}

WritePolicy parseWritePolicy(const std::string& name)
{
    if (name == "WRITE_THROUGH") return WritePolicy::WRITE_THROUGH;
    if (name == "WRITE_BACK")    return WritePolicy::WRITE_BACK;
    std::cerr << "error: unknown write policy: " << name << std::endl;
    exit(1);
}
