GEN_DIR := instruction-stream-generator
INT_DIR := interpreter
MATMUL_DIR := $(INT_DIR)/matmul
MEM_DIR := memory-system
CACHE_DIR := $(MEM_DIR)/cache
MAIN_DIR := $(MEM_DIR)/mainmem
PRNG_DIR := $(MEM_DIR)/prng
FIFO_DIR := $(MEM_DIR)/prng_fifo

MEM_SRCS := $(CACHE_DIR)/set.cpp $(CACHE_DIR)/eviction_policy.cpp \
            $(CACHE_DIR)/cache.cpp $(CACHE_DIR)/cache_actions.cpp \
            $(MAIN_DIR)/mainmem.cpp $(MAIN_DIR)/mainmem_actions.cpp \
            $(PRNG_DIR)/prng.cpp $(PRNG_DIR)/prng_actions.cpp \
            $(FIFO_DIR)/prng_fifo.cpp $(FIFO_DIR)/prng_fifo_actions.cpp \
            $(MEM_DIR)/hierarchy.cpp

INT_SRCS := $(INT_DIR)/interpreter.cpp $(MATMUL_DIR)/matmul_actions.cpp

SRCS := main.cpp $(GEN_DIR)/instgen.cpp $(INT_SRCS) $(MEM_SRCS)

DEPS := $(GEN_DIR)/instgen.h \
        $(INT_DIR)/interpreter.h $(MATMUL_DIR)/matmul_actions.h \
        $(MEM_DIR)/action.h $(MEM_DIR)/memory_object.h $(MEM_DIR)/hierarchy.h \
        $(CACHE_DIR)/set.h $(CACHE_DIR)/eviction_policy.h \
        $(CACHE_DIR)/cache.h $(CACHE_DIR)/cache_actions.h \
        $(MAIN_DIR)/mainmem.h $(MAIN_DIR)/mainmem_actions.h \
        $(PRNG_DIR)/prng.h $(PRNG_DIR)/prng_actions.h \
        $(FIFO_DIR)/prng_fifo.h $(FIFO_DIR)/prng_fifo_actions.h \
        utils.h

TEST_SRCS := tests/unit_tests.cpp $(MEM_SRCS)

all: main

debug: main_d

main: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -O3

main_d: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -g

unit_tests: $(DEPS) tests/unit_tests.cpp
	g++ -std=c++17 $(TEST_SRCS) -o tests/unit_tests -I. -g

test: main unit_tests
	./tests/unit_tests
	.venv/bin/python3 tests/run_tests.py

clean:
	rm -f asymm matmul.matv tests/unit_tests
