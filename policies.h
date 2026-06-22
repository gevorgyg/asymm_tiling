#pragma once

#include <string>


enum class Policy     { LRU, FIFO };
enum class WritePolicy { WRITE_THROUGH, WRITE_BACK };

Policy      parsePolicy(const std::string& name);
WritePolicy parseWritePolicy(const std::string& name);
