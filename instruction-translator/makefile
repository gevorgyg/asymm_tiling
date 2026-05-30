all: main trace

debug: main_d trace_d

main: cachesim.h
	g++ interpeter.cpp -o test -O3

trace:
	g++ instgen.cpp -o gentrace

main_d: cachesim.h
	g++ interpeter.cpp -o test -g

trace_d:
	g++ instgen.cpp -o gentrace -g

clean:
	rm gentrace test matmul.matv
