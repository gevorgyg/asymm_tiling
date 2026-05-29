all: main trace

debug: main_d trace_d

main: cache.h
	g++ cache.cpp interpeter.cpp -o test -O3

trace:
	g++ instgen.cpp -o gentrace

main_d: cache.h
	g++ cache.cpp interpeter.cpp -o test -g

trace_d:
	g++ instgen.cpp -o gentrace -g

clean:
	rm gentrace test matmul.matv
