SRC_DIR := instruction-translator
SRCS := $(SRC_DIR)/cachesim.cpp $(SRC_DIR)/instgen.cpp $(SRC_DIR)/interpeter.cpp
DEPS := $(SRC_DIR)/cachesim.h

all: main

debug: main_d

main: $(DEPS)
	g++ $(SRCS) -o test -O3

main_d: $(DEPS)
	g++ $(SRCS) -o test -g

clean:
	rm -f test matmul.matv
