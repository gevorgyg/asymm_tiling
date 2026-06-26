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

echo "b - stat"
./asymm --Bstationary --config bvscstat.conf --stat_file bstat.md --trace_file btrace.trace --trace_level 2 16 16 16
echo "c - stat"
./asymm --config bvscstat.conf --stat_file cstat.md --trace_file ctrace.trace --trace_level 2 16 16 16
