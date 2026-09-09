## page 19 alpha graph:
* when Tm is small enough, the A tile fits in L1 with C completely. So there is no cost.
* when it starts spilling, you can calculate the panalty with (ram_lat - l1_lat / regm*regk) * 1/Tn.
* from there as long as C doesn't overflow the L1 cache, the size of Tm doesn't effect alpha.
* the second step is when C gets evicted, then you need to pay the read and write for it each time.

## page 20 alpha graph:
### the dip:
* what is it? at first there is not amoretization of the A because Tm = 4.
* as Tm grows a little we get amoretization so better performance. 
* then at Tm 16 there is the jump because of the spill over.

## page 22 alpha graph:
* how do we calculate the Tm and Tn? we calculate the alpha for Tm and Tn when gc is 0 and create a table for each pair.
* for some gc -> we check each pair and calculate -> max{alpha (from table), gc/Tm} -> we pick the best pair out of the options.
* the alpha for large enough Tn as we seen is quite low, and for a large Tm we can lower the gc/Tm and almost always allow for a small alpha.  
  that is possible because of the B residing in the FIFO.
* most of the time the winner is mem-bound, not gen-bound. It becomes gen-bound when the gc is too high.

## page 23 ratios graph:
* Tm only goes up because we always want to lower the gc/Tm as much as possible.
* Tn goes up at first because we want to amoretize the cost of bringing in the evicted A tile we stream.
* Tn goes down when gc is high enough because Tm is forced to grow to keep the cost down, and also we cannot 
  allow Tn to be high enough for the C eviction, it's very bad, so lowering Tn is better even though it amoretizes less. That makes sense because  
  the Tm is large so we acually need less bands of A. 

## page 25 comparing to square:
### why lower Tn makes for bigger difference?
* because the square just stays small, then there is almost no amoretization for the huge gc stall. 
### why red goes down?
* because at first it's already spilling out of C for low gc. When gc grows, because Tm is large for  
  the square also we get amoretization and the difference is not so big for high gc. 
### why the green stays flat at some point?
* there they are both generation bound, because of that, the ratio is just the ratio between the tile sizes: 1-8/12.
* that stays until we get to a gc where the optimal is not Tm=12 anymore.
### what happens with yellow?
* at first, the non square can have a small enough Tm such that A just fits in the L1 cache with C  
  so it's faster. 
* then the non squre is gen bound but the squre is mem bound. and the difference is no that big. 
* after that the square becomes gen bound eventually and the difference starts growing. 
### what happens with blue?
* same as yellow, just that the dip is longer, because Tn is larger, then Tm is larger (cause it's  
  a square), meaning that it lowers the gc/Tm for a longer time. Until the gc is large enough such that  
  the square looses to the new Tm of the optimal one.

