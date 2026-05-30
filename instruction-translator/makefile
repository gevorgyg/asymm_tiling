all: main

debug: main_d

main: cachesim.h
	g++ instgen.cpp interpeter.cpp -o test -O3

main_d: cachesim.h
	g++ interpeter.cpp -o test -g

clean:
	rm test matmul.matv
