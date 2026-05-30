all: main

debug: main_d

main: cachesim.h
	g++ cachesim.cpp instgen.cpp interpeter.cpp -o test -O3

main_d: cachesim.h
	g++ cachesim.cpp instgen.cpp interpeter.cpp -o test -g

clean:
	rm test matmul.matv
