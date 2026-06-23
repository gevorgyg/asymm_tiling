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

./asymm --scratchpad --stat_file stats-scratch.md --trace_file sp.trace --trace_level 2 4 4 4
./asymm --stat_file stats-no-scratch.md --trace_file sp.trace --trace_level 2 4 4 4
