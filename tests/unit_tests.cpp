#include "memory-system/cache/set.h"
#include "memory-system/cache/eviction_policy.h"
#include "memory-system/cache/cache.h"
#include "memory-system/mainmem.h"
#include <cassert>
#include <iostream>
#include <memory>
#include <vector>

void testEvictionPolicies() {
    std::cout << "Running unit test for LRU Set..." << std::endl;
    Set set_lru(2); // Assoc = 2
    auto lru = std::make_unique<LruPolicy>();

    set_lru.insert(10);
    set_lru.insert(20);
    assert(set_lru.isFull());
    assert(set_lru.lines().front().lineAddr() == 10);
    assert(set_lru.lines().back().lineAddr() == 20);

    // Touch 10 (promoting it to MRU)
    lru->recordAccess(set_lru, 10);
    assert(set_lru.lines().front().lineAddr() == 20); // LRU
    assert(set_lru.lines().back().lineAddr() == 10);  // MRU

    CacheLine* victim = lru->pickVictim(set_lru);
    assert(victim->lineAddr() == 20);

    set_lru.remove(20);
    set_lru.insert(30);
    assert(set_lru.lines().front().lineAddr() == 10);
    assert(set_lru.lines().back().lineAddr() == 30);

    std::cout << "LRU unit test PASSED!" << std::endl;

    std::cout << "Running unit test for FIFO Set..." << std::endl;
    Set set_fifo(2);
    auto fifo = std::make_unique<FifoPolicy>();

    set_fifo.insert(10);
    set_fifo.insert(20);

    // Touch 10 (FIFO should ignore this)
    fifo->recordAccess(set_fifo, 10);
    assert(set_fifo.lines().front().lineAddr() == 10);

    CacheLine* victim_fifo = fifo->pickVictim(set_fifo);
    assert(victim_fifo->lineAddr() == 10);

    std::cout << "FIFO unit test PASSED!" << std::endl;
}

// Helper to check action types in trace
bool hasAction(const Trace& trace, const std::string& actionName) {
    for (const auto& action : trace) {
        if (std::string(action->name()) == actionName) {
            return true;
        }
    }
    return false;
}

void testWriteThrough() {
    std::cout << "Running Cache Write-Through unit tests..." << std::endl;
    
    MainMemory memory(180);
    Cache::InitParameters params;
    params.name = "L1_WT";
    params.size = 16;        // 2 lines of 8B each
    params.line_size = 8;
    params.assoc = 2;
    params.write_policy = WritePolicy::WRITE_THROUGH;

    auto policy = std::make_unique<LruPolicy>();
    Cache cache(4, params, std::move(policy), &memory);

    // 1. Read Miss (should fetch from memory and fill)
    Trace trace1;
    cache.read(0x10, 8, trace1);
    assert(cache.stats().tag_lookups == 1);
    assert(cache.stats().misses == 1);
    assert(cache.stats().hits == 0);
    assert(cache.stats().line_fills == 1);
    assert(hasAction(trace1, "MemoryAccess")); // Fetched from memory
    assert(hasAction(trace1, "LineFill"));

    // 2. Read Hit (should hit in L1, no memory access)
    Trace trace2;
    cache.read(0x10, 8, trace2);
    assert(cache.stats().tag_lookups == 2);
    assert(cache.stats().misses == 1);
    assert(cache.stats().hits == 1);
    assert(!hasAction(trace2, "MemoryAccess")); // No memory access on hit

    // 3. Write Miss under Write-Through (No-allocate policy)
    // Write-through + no-allocate should lookup tag, and immediately write to memory without line fill.
    Trace trace3;
    cache.write(0x20, 8, trace3);
    assert(cache.stats().tag_lookups == 3);
    assert(cache.stats().misses == 2);
    assert(cache.stats().line_fills == 1); // No new fill!
    assert(hasAction(trace3, "MemoryAccess")); // Written directly to memory

    // Confirm it was not allocated by reading it (should miss again)
    Trace trace4;
    cache.read(0x20, 8, trace4);
    assert(cache.stats().misses == 3); // Missed again!
    assert(cache.stats().line_fills == 2); // Filled now on read miss

    std::cout << "Cache Write-Through unit tests PASSED!" << std::endl;
}

void testWriteBack() {
    std::cout << "Running Cache Write-Back unit tests..." << std::endl;

    MainMemory memory(180);
    Cache::InitParameters params;
    params.name = "L1_WB";
    params.size = 16;        // 2 lines of 8B each
    params.line_size = 8;
    params.assoc = 2;
    params.write_policy = WritePolicy::WRITE_BACK;

    auto policy = std::make_unique<LruPolicy>();
    Cache cache(4, params, std::move(policy), &memory);

    // 1. Write Miss (Write-Back + Write-Allocate)
    // Should read line from memory (write-allocate), perform line fill, and mark dirty locally.
    Trace trace1;
    cache.write(0x10, 8, trace1);
    assert(cache.stats().tag_lookups == 1);
    assert(cache.stats().misses == 1);
    assert(cache.stats().line_fills == 1);
    assert(hasAction(trace1, "MemoryAccess")); // Reads from memory to allocate
    assert(hasAction(trace1, "LineFill"));

    // 2. Write Hit
    // Should hit in L1, update LRU, and return immediately (no memory traffic).
    Trace trace2;
    cache.write(0x10, 8, trace2);
    assert(cache.stats().tag_lookups == 2);
    assert(cache.stats().hits == 1);
    assert(cache.stats().misses == 1);
    assert(!hasAction(trace2, "MemoryAccess")); // Absorbed in cache

    // 3. Read Miss
    // Fill the cache (it has 2 lines: 0x10 [dirty] and 0x20 [clean])
    Trace trace3;
    cache.read(0x20, 8, trace3); // Allocate 0x20 (clean)
    assert(cache.stats().line_fills == 2);
    
    // Now L1 has 0x10 (dirty) and 0x20 (clean).
    // Let's touch 0x10 to make it MRU, making 0x20 the LRU block.
    Trace traceTouch;
    cache.read(0x10, 8, traceTouch); // Hit 0x10 (MRU)
    assert(cache.stats().hits == 2);

    // 4. Now insert a third line (0x30) to trigger eviction.
    // L1 is full and using LRU. 0x20 (clean) is the LRU block.
    // 0x20 should be evicted. Since 0x20 is clean, eviction should NOT write back.
    Trace trace4;
    cache.read(0x30, 8, trace4);
    assert(cache.stats().line_fills == 3);
    assert(cache.stats().evicts == 1);
    
    bool foundEvict = false;
    for (const auto& action : trace4) {
        if (std::string(action->name()) == "Evict") {
            foundEvict = true;
        }
    }
    assert(foundEvict);

    // Since 0x20 was clean, trace4 should only have 1 MemoryAccess (the read for 0x30).
    int memAccesses4 = 0;
    for (const auto& action : trace4) {
        if (std::string(action->name()) == "MemoryAccess") {
            memAccesses4++;
        }
    }
    assert(memAccesses4 == 1);

    // 5. Now active lines in cache are 0x10 (dirty, LRU) and 0x30 (clean, MRU).
    // Allocate 0x40 to trigger eviction of 0x10 (dirty).
    // Since 0x10 is dirty, eviction MUST write back to memory first.
    Trace trace5;
    cache.read(0x40, 8, trace5);
    assert(cache.stats().line_fills == 4);
    assert(cache.stats().evicts == 2);

    // The trace for 0x40 read should contain:
    // - MemoryAccess (read for 0x40)
    // - Evict (for 0x10) which triggers:
    // - MemoryAccess (writeback write for 0x10)
    int memAccesses5 = 0;
    for (const auto& action : trace5) {
        if (std::string(action->name()) == "MemoryAccess") {
            memAccesses5++;
        }
    }
    assert(memAccesses5 == 2); // 1 read miss allocation, 1 writeback eviction!

    std::cout << "Cache Write-Back unit tests PASSED!" << std::endl;
}

int main() {
    std::cout << "========================================" << std::endl;
    std::cout << "Running Cache Simulator C++ Unit Tests..." << std::endl;
    std::cout << "========================================" << std::endl;

    testEvictionPolicies();
    testWriteThrough();
    testWriteBack();

    std::cout << "========================================" << std::endl;
    std::cout << "All C++ Unit Tests PASSED Successfully!" << std::endl;
    std::cout << "========================================" << std::endl;

    return 0;
}
