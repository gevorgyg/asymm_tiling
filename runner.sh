#!/bin/bash

bflag=

while getopts rgBbc name
do
   case $name in
   b)    bflag=1;;
   ?)    printf "Usage: %s: [-b]\n" "$0"
         exit 2;;
   esac
done

if [ ! -z "$bflag" ]; then
	make clean
    make
fi

# ./asymm 125 500 125 --trace_file output.trace
# ./asymm 125 125 500 --trace_file output.trace
# ./asymm 500 125 125 --trace_file output.trace

