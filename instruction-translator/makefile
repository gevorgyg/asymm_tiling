all: main trace

debug: main_d trace_d

main:
	g++ cache.cpp interpeter.cpp -o test -O3

trace:
	g++ instgen.cpp -o gentrace

main_d:
	g++ cache.cpp interpeter.cpp -o test -g

trace_d:
	g++ instgen.cpp -o gentrace -g
