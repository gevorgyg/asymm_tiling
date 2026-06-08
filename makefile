SRC_DIR := instruction-translator
MEM_DIR := memory-system
CACHE_DIR := $(MEM_DIR)/cache
SRCS := $(SRC_DIR)/prng_record.cpp $(SRC_DIR)/instgen.cpp $(SRC_DIR)/interpeter.cpp \
        $(CACHE_DIR)/set.cpp $(CACHE_DIR)/eviction_policy.cpp $(CACHE_DIR)/cache.cpp \
        $(MEM_DIR)/mainmem.cpp $(MEM_DIR)/hierarchy.cpp
DEPS := $(SRC_DIR)/instgen.h $(SRC_DIR)/interpeter.h \
        $(SRC_DIR)/prng_record.h \
        $(MEM_DIR)/action.h $(MEM_DIR)/memory_object.h \
        $(MEM_DIR)/mainmem.h $(MEM_DIR)/hierarchy.h \
        $(CACHE_DIR)/set.h $(CACHE_DIR)/eviction_policy.h $(CACHE_DIR)/cache.h

all: main

debug: main_d

main: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -O3

main_d: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -g

clean:
	rm -f asymm matmul.matv
