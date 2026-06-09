GEN_DIR := instruction-stream-generator
INT_DIR := interpreter
MEM_DIR := memory-system
CACHE_DIR := $(MEM_DIR)/cache
SRCS := main.cpp \
        $(GEN_DIR)/instgen.cpp \
        $(INT_DIR)/interpeter.cpp $(INT_DIR)/prng_record.cpp \
        $(CACHE_DIR)/set.cpp $(CACHE_DIR)/eviction_policy.cpp $(CACHE_DIR)/cache.cpp \
        $(MEM_DIR)/mainmem.cpp $(MEM_DIR)/hierarchy.cpp
DEPS := $(GEN_DIR)/instgen.h \
        $(INT_DIR)/interpeter.h $(INT_DIR)/prng_record.h \
        $(MEM_DIR)/action.h $(MEM_DIR)/memory_object.h \
        $(MEM_DIR)/mainmem.h $(MEM_DIR)/hierarchy.h \
        $(CACHE_DIR)/set.h $(CACHE_DIR)/eviction_policy.h $(CACHE_DIR)/cache.h \
        utils.h

all: main

debug: main_d

main: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -O3

main_d: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -g

clean:
	rm -f asymm matmul.matv
