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

echo "---NO PRNG---"
./asymm 4 4 4 --config default.config --trace_file trace.log 
echo " "
echo "---PRNG---"
./asymm 4 4 4 --config default.config --Bgenerated

