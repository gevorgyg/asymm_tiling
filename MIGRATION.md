# v0.4 → v0.4-simplification migration

A flat lookup table for old symbols, files, and patterns after the
v0.4-simplification refactor. `git log --reverse v0.4..v0.4-simplification`
walks through the change as a story; this file is the cheat sheet.

## Files moved or split

| Old path                              | New path                                                     |
| ------------------------------------- | ------------------------------------------------------------ |
| `interpreter/interpeter.{h,cpp}`      | `interpreter/interpreter.{h,cpp}` (spelling fix)             |
| `memory-system/mainmem.{h,cpp}`       | `memory-system/mainmem/mainmem.{h,cpp}`                      |
| `memory-system/prng.{h,cpp}`          | `memory-system/prng/prng.{h,cpp}`                            |
| `memory-system/prng_fifo.{h,cpp}`     | `memory-system/prng_fifo/prng_fifo.{h,cpp}`                  |
| *(action classes were inside cache.h)*| `memory-system/cache/cache_actions.{h,cpp}`                  |
| *(action classes were inside mainmem.h)* | `memory-system/mainmem/mainmem_actions.{h,cpp}`           |
| *(action classes were inside prng.h)* | `memory-system/prng/prng_actions.{h,cpp}`                    |
| *(action classes were inside prng_fifo.h)* | `memory-system/prng_fifo/prng_fifo_actions.{h,cpp}`     |
| *(config was globals in main.cpp)*    | `config.{h,cpp}` (typed `Config` struct + `loadConfig`)      |
| *(no MulAcc Action existed)*          | `interpreter/matmul/matmul_actions.{h,cpp}`                  |

## Symbols renamed

| Old                                | New                                  |
| ---------------------------------- | ------------------------------------ |
| `class Interpeter`                 | `class Interpreter`                  |
| `INTERPRETER_SYNTEX_CHECK` (macro) | `Interpreter::expect()` (function)   |
| `g_config`, `g_config_str`         | `Config` struct (passed by const-ref)|
| `getConfig(key)`, `hasConfig(key)` | direct field access on `Config`      |
| `getConfigStr(key)`                | direct field access on `Config`      |
| `loadConfigFile(path)`             | `loadConfig(path) -> Config`         |
| `createEvictionPolicy(string)`     | `parsePolicy(string) -> Policy`      |
| `class EvictionPolicy` (abstract)  | `enum class Policy { LRU, FIFO }`    |
| `class LruPolicy`, `class FifoPolicy` | gone — branch in `pickVictim`/`recordAccess` |
| `PrngDev::IsGenerated`, `PrngDev::Generate` | top-level `IsGenerated`, `Generate` |
| `PrngFifoDev::ControlWrite`        | `FifoControlWrite` (top-level)       |
| `PrngFifoDev::SeedWrite`           | `FifoSeedWrite`                      |
| `PrngFifoDev::ReadFifo`            | `FifoReadFifo`                       |
| `PrngFifoDev::GenerateElement`     | `FifoGenerateElement`                |
| `PrngFifoDev::RegisterRead`        | `FifoRegisterRead`                   |

Note: each Action's `name()` string is unchanged (e.g. `FifoControlWrite::name()`
still returns `"PrngFifoDev::ControlWrite"`), so the trace file is identical
and tests that grep for these strings keep working.

## Behaviour moved out of Actions

`Action::perform(Trace&)` is gone. State mutation now happens in the
device methods that produce the Action; the Action is a pure-data record.

| Old call                       | New location                                      |
| ------------------------------ | ------------------------------------------------- |
| `Cache::TagLookup::perform`    | `Cache::probe(Addr)` — stats + LRU touch + hit/miss |
| `Cache::LineFill::perform`     | `Cache::fillLine(Addr, Trace&)` — eviction + install + stats |
| `Cache::Evict::perform`        | folded into `Cache::fillLine`                     |
| `PrngDev::IsGenerated::perform`| inlined in `PrngDev::read`                        |
| `PrngDev::Generate::perform`   | inlined in `PrngDev::read`                        |
| `PrngFifoDev::ControlWrite::perform` | inlined in `PrngFifoDev::write`             |
| `PrngFifoDev::SeedWrite::perform`    | inlined in `PrngFifoDev::write`             |
| `PrngFifoDev::ReadFifo::perform`     | inlined in `PrngFifoDev::read`              |
| `MainMemory` no-op perform     | dropped entirely                                  |

## Interpreter restructuring

| Old                                       | New                                         |
| ----------------------------------------- | ------------------------------------------- |
| `enum cmd { load_tile, ... }`             | gone — dispatch via static op-table in `handleCmd` |
| `cmd Interpreter::readCmd()`              | gone                                        |
| `Interpreter::trim_prefix_spaces()`       | `Interpreter::skipSpaces()`                 |
| 25-line reg-shape check duplicated in `handleTload` / `handleTmove` | one `Interpreter::validateRegShape(reg, w, h)` |
| 6-arg parse block duplicated in `handleTload` / `handleTmove` / `handlePrefetch` | one `Interpreter::parseTileParams() -> TileParams` |
| inline `(0x..., w, h, stride, ew), %r..` printf | one `Interpreter::setInstHeader(op, params, reg)` |
| nested `for (row) for (col) ...` loops in 3 handlers | one `Interpreter::forEachElement(params, fn)` template |
| `cpu_cycles_ += getConfig("MULAC_CYCLES")`| `Trace t; t.push_back(make_unique<MulAcc>(mulac_cycles_)); cpu_cycles_ += totalCycles(t);` |

## Hierarchy restructuring

| Old                                                | New                                                  |
| -------------------------------------------------- | ---------------------------------------------------- |
| `class MemoryHierarchy : public MemoryObject`      | `class MemoryHierarchy` (no virtual dispatch)        |
| `MemoryHierarchy::read(addr, sz, trace)`           | `MemoryHierarchy::access(addr, sz, is_write, trace)` |
| `MemoryHierarchy::write(addr, sz, trace)`          | same `access(... is_write=true ...)`                 |
| `AddrRouter` checks both `prng_fifo_.contains` and `prng_.contains` | only checks `prng_.contains` (FIFO check was dead code) |
| `AddrRouter` ctor takes `(prng, prng_fifo, fallthrough)` | `AddrRouter` ctor takes `(prng, fallthrough)`  |

## Behaviour deltas (very small)

* Cache trace order on a dirty eviction now goes `[..., next->write(writeback), Evict, LineFill]` instead of `[..., LineFill, Evict, next->write(writeback)]`. Unit tests check counts/presence; cycle counts unchanged because Evict and LineFill both have cost 0.
* Write-back hit path no longer calls `recordAccess` twice (the old code did, redundantly). LRU was idempotent under repeat touch so this was a no-op; nothing observable changes.
