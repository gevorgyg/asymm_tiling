#pragma once

using uint = unsigned int;
using Addr = unsigned int;

#ifndef NDEBUG
    #define LOG_DEBUG(msg) std::cerr << "[DEBUG] (" << __FILE__ << ":" << __LINE__ << ") " << msg << std::endl
#else
    #define LOG_DEBUG(msg) do {} while (0) // Stripped out entirely during optimization
#endif
