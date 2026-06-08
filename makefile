SRC_DIR := instruction-translator
MEM_DIR := memory-system
SRCS := $(SRC_DIR)/prng_record.cpp $(SRC_DIR)/instgen.cpp $(SRC_DIR)/interpeter.cpp \
        $(MEM_DIR)/cache.cpp $(MEM_DIR)/hierarchy.cpp
DEPS := $(SRC_DIR)/instgen.h $(SRC_DIR)/interpeter.h \
        $(SRC_DIR)/prng_record.h \
        $(MEM_DIR)/cache.h $(MEM_DIR)/hierarchy.h $(MEM_DIR)/memory_object.h

all: main

debug: main_d

main: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -O3

main_d: $(DEPS)
	g++ -std=c++17 $(SRCS) -o asymm -g

clean:
	rm -f asymm matmul.matv
