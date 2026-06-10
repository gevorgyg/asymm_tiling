#pragma once

using uint = unsigned int;
using Addr = unsigned int;

#ifndef NDEBUG
#define LOG_DEBUG(msg)                                                         \
    std::cerr << "[DEBUG] (" << __FILE__ << ":" << __LINE__ << ") " << msg     \
              << std::endl
#else
#define LOG_DEBUG(msg)                                                         \
    do {                                                                       \
    } while (0) // Stripped out entirely during optimization
#endif

constexpr int g_page_size = 1024 * 4;

#define CACHESIM_ALIGN(addr, page_size)                                        \
    do {                                                                       \
        if ((addr) % (page_size) != 0) {                                       \
            if ((addr) / (page_size) == 0) {                                   \
                (addr) = 0;                                                    \
            } else {                                                           \
                (addr) = (((addr) / (page_size)) + 1) * (page_size);           \
            }                                                                  \
        }                                                                      \
    } while (0)
