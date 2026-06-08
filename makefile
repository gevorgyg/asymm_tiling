SRC_DIR := instruction-translator
SRCS := $(SRC_DIR)/cachesim.cpp $(SRC_DIR)/instgen.cpp $(SRC_DIR)/interpeter.cpp
DEPS := $(SRC_DIR)/cachesim.h $(SRC_DIR)/instgen.h $(SRC_DIR)/interpeter.h

all: main

debug: main_d

main: $(DEPS)
	g++ $(SRCS) -o asymm -O3

main_d: $(DEPS)
	g++ $(SRCS) -o asymm -g

clean:
	rm -f asymm matmul.matv
