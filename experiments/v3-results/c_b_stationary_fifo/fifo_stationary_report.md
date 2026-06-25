# Stationary Policy Comparison Report (PRNG FIFO Stream)

This report details the performance metrics comparing **C-Stationary** and **B-Stationary** loop tiling policies under MMIO PRNG FIFO streaming on a 256x256 matrix multiplication.

## Performance Comparison Dashboard

![Stationary Comparison](/home/aregmk/.gemini/antigravity/brain/2da43f73-946b-424d-9271-e7366e35cbd1/fifo_stationary_comparison.png)

---

## Detailed Comparison Data

| Tile Shape ($M \times N \times K$) | Policy | Total Cycles | L1 Hit Rate (Hits / Lookups) | L2 Hit Rate (Hits / Lookups) | Starts/Stops | Stall Cycles | FIFO Reads |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **16x32x8** | C-stationary | 18,230,240 | 0.902 (594,829 / 659,456) | 0.774 (56,223 / 72,640) | 4,096 | 8,388,608 | 1,048,576 |
| **16x32x8** | B-stationary | **133,272,000** | 0.931 (4,393,247 / 4,718,848) | 0.444 (261,768 / 589,568) | 256 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **16x64x16** | C-stationary | 16,791,616 | 0.900 (354,816 / 394,240) | 0.655 (31,105 / 47,488) | 1,024 | 8,388,608 | 1,048,576 |
| **16x64x16** | B-stationary | **66,584,376** | 0.931 (2,196,564 / 2,359,360) | 0.443 (130,432 / 294,428) | 64 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **32x64x16** | C-stationary | 11,683,392 | 0.875 (344,512 / 393,728) | 0.715 (41,092 / 57,472) | 512 | 4,194,304 | 524,288 |
| **32x64x16** | B-stationary | **68,419,384** | 0.875 (2,064,440 / 2,359,360) | 0.615 (261,682 / 425,500) | 64 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **32x128x32** | C-stationary | 10,918,800 | 0.875 (229,488 / 262,272) | 0.598 (24,360 / 40,736) | 128 | 4,194,304 | 524,288 |
| **32x128x32** | B-stationary | **34,190,520** | 0.875 (1,032,206 / 1,179,664) | 0.614 (130,470 / 212,492) | 16 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **64x128x32** | C-stationary | 8,448,776 | 0.875 (229,432 / 262,208) | 0.577 (23,495 / 40,720) | 64 | 2,097,152 | 262,144 |
| **64x128x32** | B-stationary | **34,190,520** | 0.875 (1,032,206 / 1,179,664) | 0.614 (130,470 / 212,492) | 16 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **64x256x64** | C-stationary | 8,194,252 | 0.875 (172,046 / 196,624) | 0.444 (14,323 / 32,260) | 16 | 2,097,152 | 262,144 |
| **64x256x64** | B-stationary | **17,102,128** | 0.875 (516,100 / 589,828) | 0.614 (65,077 / 105,988) | 4 | 524,288 | **65,536** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **128x256x64** | C-stationary | 7,710,164 | 0.875 (172,039 / 196,616) | 0.238 (7,677 / 32,258) | 8 | 1,048,576 | 131,072 |
| **128x256x64** | B-stationary | **17,512,528** | 0.875 (516,100 / 589,828) | 0.588 (62,321 / 105,988) | 4 | 524,288 | **65,536** |

---

## Architectural Analysis & Key Insights

### 1. The Paradox: Why B-Stationary is Much Slower

At first glance, **B-Stationary** seems highly optimal because it loads B tiles from the FIFO only once, saving DRAM seed reads and start/stop command overheads. For example, at shape **16x32x8**:
* B-stationary performs only **256 starts** and **65,536 FIFO reads**.
* C-stationary performs **4,096 starts** and **1,048,576 FIFO reads** (16x more!).

However, **B-stationary is up to 7 times slower** (133M vs 18M cycles). The explanation lies in how Matrix C is accumulated:
* **C-Stationary Loop Order (Outer: `ti`, Middle: `tj`, Inner: `tk`):**
  A tile of C is loaded into register `%rc` once, accumulated over $K_{\text{tiles}}$ steps entirely inside registers, and written back to memory once.
* **B-Stationary Loop Order (Outer: `tk`, Middle: `tj`, Inner: `ti`):**
  Because the accumulation dimension (`tk`) is the **outermost loop**, the inner loop (`ti`) sweeps through *different* tiles of C. Therefore, the CPU **cannot** keep C in registers. In every single step of the inner loop, it must load $C_{ti, tj}$ from memory, execute `tmulac`, and store it back to memory.

This multiplies the memory traffic of C by a factor of $K_{\text{tiles}}$.
At shape **16x32x8** ($K_{\text{tiles}} = 32$):
* **C-stationary L1 Lookups:** 659,456
* **B-stationary L1 Lookups:** **4,718,848** (7.15x increase due to repeated A and C memory traffic!)

This massive L1/L2 bandwidth demand on C completely overwhelms the PRNG FIFO savings, making B-stationary far slower.

### 2. Startup Latency vs. Execution Latency
In C-stationary, the generator is restarted 4,096 times, causing **8,388,608 stall cycles** as the CPU waits for the FIFO pipeline to fill up on each restart.
In B-stationary, because the generator is restarted only 256 times, it achieves a 16x reduction in stall cycles (**524,288**). 
* Thus, B-stationary succeeds in making the PRNG FIFO device extremely efficient, but fails at the system level due to the loss of temporal locality on Matrix C.
* **Architectural Lesson:** Keeping C stationary in registers is a dominant optimization because C is read-write, whereas B is read-only.
