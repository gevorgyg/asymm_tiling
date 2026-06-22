#pragma once

#include "../utils.h"


// Scratchpad address windows: A, B, C tiles are DMA'd to fixed offsets.
constexpr Addr SP_A_ADDR = 0x20000000;
constexpr Addr SP_B_ADDR = 0x30000000;
constexpr Addr SP_C_ADDR = 0x40000000;
constexpr Addr SP_END    = 0x50000000;

// PRNG FIFO MMIO register layout.
constexpr Addr FIFO_CTRL_START_ADDR = 0xFF000000;
constexpr Addr FIFO_SEED_ADDR       = 0xFF000004;
constexpr Addr FIFO_DATA_START_ADDR = 0xFF000008;
constexpr Addr FIFO_CTRL_STOP_ADDR  = 0xFF00000C;
constexpr Addr FIFO_DATA_END_ADDR   = 0xFF100008;
