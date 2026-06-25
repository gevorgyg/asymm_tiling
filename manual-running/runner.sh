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

echo "working set"
./asymm --config workingset.conf --stat_file stats-no-scratch.md --trace_file sp.trace --trace_level 2 16 16 16
echo "bigger than working set"
./asymm --config bigger-than-workingset.conf --stat_file stats-no-scratch.md --trace_file sp.trace --trace_level 2 8 32 16
