# E13-nol2: FIFO-B vs Memory-B — Fair Head-to-Head in L1-only Hierarchy

**Config**: M=192, N=K=TK=256, A_P=B_P=4, L1=16KB, no-L2.  
**Memory-B**: 40 fresh runs (this experiment). **FIFO-B**: loaded from E8-nol2 cache.

---

## Memory-B α(TM, TN)

```
   TM       TN=4       TN=8      TN=16      TN=32      TN=64
    8     12.5409     7.8222     5.4628     4.9861     4.7476
   12     10.6658     6.8846     4.9940     4.5172     4.2786
   16      9.7283     6.4158     4.7595     4.2827     4.0440
   24      8.7907     5.9469     4.5250     4.0481     3.8092
   32      8.3218     5.7124     4.4077     3.9307     3.6915  ← TM*@TN=64
   48      7.8528     5.4778     4.2903     3.8131     9.4786*
   64      7.6182     5.3604     4.2315     3.7540*    9.6231*
   96      7.3834     5.2428     4.1725    10.3050*    9.5646*
```

`*` WS unsafe (ws_lines ≥ 300). TM* per TN: 96/96/96/64/32.

Memory-B α is **dramatically higher** than FIFO-B α, especially at small TN.
Even at TN=4 where the B tile is only 4 KB (fits within L1), α_mem≈7.4–12.5
because each 4×4 B register block spans **4 non-contiguous cache lines** (B row
stride = N×4 = 1024 bytes = 16 cache lines). B therefore exerts 4× the L1
pressure that naive tile-size arithmetic suggests, evicting A lines and adding
DRAM refill cost to every A access.

---

## FIFO-B α(TM, TN) at gc=0

```
   TM       TN=4       TN=8      TN=16      TN=32      TN=64
    8      3.3997     3.3973     3.3963     3.3958     3.3957
   12      3.3159     3.3146     3.3139     3.3133     3.4378
   16      6.0524     4.6403     3.9343     3.5811     3.4041
   24      6.0067     4.5966     3.8916     3.5387     3.3617
   32      5.9839     4.5747     3.8701     3.5174     3.3403  ← TM*@TN=64
   48      5.9609     4.5527     3.8486     3.4959     4.3896*
   64      5.9492     4.5415     3.8377     3.4849     8.8731*
   96      5.9374     4.5302     3.8266     9.0329*    8.8756*
```

FIFO keeps B entirely off the L1 bus. A and C compete only with each other.

---

## FIFO advantage and crossover gc* per TN

```
  TN   α_mem(TM*)   α_FIFO(gc=0)   FIFO adv (gc=0)   crossover gc*
   4       7.3834         3.3159              55.1%         > 400
   8       5.2428         3.3146              36.8%         > 400
  16       4.1725         3.3139              20.6%    (250, 400]
  32       3.7540         3.3133              11.7%    (150, 250]
  64       3.6915         3.3403               9.5%    (100, 150]
```

**FIFO wins at every tested gc value for TN ≤ 8** — even at gc=400, FIFO is
still 23–43% faster than the best Memory-B tile. The crossover only becomes
relevant at TN ≥ 16, and at TN=32 it falls somewhere in (150, 250].

The trend is clear: **larger TN → smaller crossover gc*.** At large TN the B
tile (TK×TN×4 bytes) is already fully DRAM-bound regardless of mode, so the
per-FMA cost of loading B from memory becomes comparable to a moderate FIFO
generation cost. At small TN the non-contiguous B layout amplifies the Memory-B
penalty so severely that FIFO wins by a large margin at all practical gc values.

---

## Comparison at TN=32 (standard operating point)

```
  gc   TM*_FIFO   T_FIFO   T_mem   speedup   winner
  15         12   3.3155  3.7540    1.132x    FIFO
  30         12   3.3179  3.7540    1.131x    FIFO
  38         12   3.3192  3.7540    1.131x    FIFO
  42         64   3.4861  3.7540    1.077x    FIFO
  47         64   3.4862  3.7540    1.077x    FIFO
 100         64   3.4879  3.7540    1.076x    FIFO
 150         64   3.4894  3.7540    1.076x    FIFO
 250         64   3.9931  3.7540    0.940x    mem   ← crossover
 400         64   6.3368  3.7540    0.592x    mem
```

At TN=32, FIFO wins by ~13% at low gc (TM*=12, α-bound), dropping to ~8% after
the TM* transition at gc≈42 (TM*=64). Memory-B wins above gc≈200.

---

## Why Memory-B is so expensive in L1-only

In the L2 case, B's DRAM misses are buffered by L2 (14-cycle latency). Here
there is no L2: every B cache miss goes directly to DRAM (180 cycles). The
effective B penalty per FMA is amplified by 180/14 ≈ 13×.

Additionally, B has 4 cache lines per 4×4 register block (due to row stride),
so the true B working set is 4× larger than the tile size suggests:

| TN | B tile (naive) | B actual lines | L1 capacity |
|----|---------------|---------------|-------------|
|  4 |  4 KB = 64 lines | **256 lines** | 256 lines |
|  8 |  8 KB = 128 lines | **512 lines** | 256 lines |
| 32 | 32 KB = 512 lines | **2048 lines** | 256 lines |

At TN=4, B already fills all of L1. At TN≥8, B is 2× or more the L1 capacity
— every B access is a DRAM miss regardless of TM. FIFO-B sidesteps this
entirely: B never enters L1, so A and C have 256 lines to themselves.

---

## Summary

| Finding | Result |
|---------|--------|
| FIFO advantage at gc=0, TN=32 | 11.7% (α_mem=3.754 vs α_FIFO=3.313) |
| FIFO advantage at gc=0, TN=4 | 55.1% (α_mem=7.383 vs α_FIFO=3.316) |
| Crossover gc* at TN=32 | ∈ (150, 250] |
| Crossover gc* at TN=4,8 | > 400 (FIFO wins at all tested gc) |
| Memory-B TM* | 96 for TN≤16, 64 for TN=32, 32 for TN=64 |
| B tile L1 pressure | 4× higher than naive estimate (stride effect) |
| vs L2 case crossover gc* | ~13× lower (no L2 buffer: 180 cy vs 14 cy) |
