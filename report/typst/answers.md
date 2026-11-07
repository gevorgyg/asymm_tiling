# Why did we choose those default values?
- Matrices 192×256×256: small enough to run thousands of simulations fast, but way bigger than L1 (A alone is 192 KB vs a 16 KB cache), so tiling matters.
- 4-byte elements: FP32 / INT32 are the most common types.
- 4×4 register block: a modest, realistic register file.
- L1 16 KB, 64 B lines, LRU: a common setup. Fully associative mimics a software-managed scratchpad (we test set-associative separately).
- L1 4 cycles, memory 180 cycles: realistic latencies.
- No L2: fewer degrees of freedom, easier to understand the results (tested separately).
- g_c swept 0 to 600: from a fast dedicated generator to a slow or shared one.
- FIFO 2^14 elements: big enough to never limit the overlap, so we see the generator itself (FIFO size tested separately).
- FIFO pop 2 cycles: comparable to an L1 access.
- Free compute (c = 0): isolates the memor
  y and generation costs (compute speed tested separately).

# Why the platou shape in the dataflow graph?
- when they both become generation bound.

# Why isn't the best tile just the one such that the tile fits into the cache?
- because as soon as gc is not 0 -> we need something to amoretize the cost.

# Why the sawtooth shape?
- Because of the short last row -> we are still at the first step though so the affects are small.

# Why the osilatory shape?
- Also the short last row -> When we full divide there is no short last row and the threshing is full always.
- When there is a sort last row -> it threshes less -> and that is averaged with the max threshing -> making it less.

# Why is the startup only on the memory part?
- Every new tile loads a new seed, and we have to wait for it at the start no matter what, so it adds to the memory in all cases.
- This also shows why even with the refined model, some of the points still miss -> when the generation time and the memory latency are quite close to each other, it's not completely async and that introduces some of the left over error.

# The refined model threshold: why is it like that?
- We have one strip of A streaming. B strips are going from left to right. And C has tiles that are going from left to right. Inside of those big tile strips, we have the loading into registers. Inside the A stip, we load the RxR register from top to bottom in the strip (column like) -> The B strip goes from left to right, one load of RxR is used for the entire column of RxR loads of A -> Then it goes right and the same coloum of A is used again -> This already touched the entire C tile. Now when we come back to this same coloum for the next tile of C, in one go we already touched the entire C tile. Now that only happens if the cache lines align that way, but most of the time they do.
  Link to [visualization](https://claude.ai/artifact/BvbNRyGGq4M4PiHWxG34ot).

# The added constant because of C to the final model?
- It's because every element of C is loaded once, and also it's amoretized by the the number of elements in one cache line and by the number of macs each element is used in, which is K. 

# Why does N cause earlier threshing?
- Becuase it's not aligned with the cache lines -> causing it to touch more then one -> causing more cache usage and earlier threshing.

# Tall and short or Short and wide tiles:
- Tall and short are obviously because we amoratize the gc value.
- Short and wide are less obvious -> they are because if it's wider -> those are less rereads of the A strip -> so we reload it less -> and it's a case of which one causes better performance -> at high gc values -> the gc is so big that a tall one is the best bet -> at low gc values -> wider is better because it makes it so we need to reload A less.

# Does the choice matter slide explanations:
- Blue starts the same as square -> because the sqare is small enough to fit into the cache and the performance is good -> until gc is large enough where Tm needs to amoratize it but square is stuck.
- Why is bigger Tn better at smaller gc -> because there the non square can afford to keep Tm very small to fit but the square cannot.
- High Tn at high gc -> the square is already quite big amoretizing the gc also like the non square one.
- Why does it platau -> because at really high gc they are both generaion bound and their ratio is just the ratio of Tm between them.
- in the best of each, why two hills at two parts like that -> first hill has a short and wide tile that is better -> second hill has a tall and and narrow one.

# Why do  we see an effect of doubling the cache is exactly like halfing the generation cost?
- Both cliffs of alpha are capacity limits -> how much of A and two tiles of C can fit -> increasing the cache, off course, increases alpha.
- The doubling is because we double the cache -> recall the cliff threshold -> the height of the tile (Tm) is dependend linearly on the size of the cache -> doubling the size then -> doubles the height we can use -> doubling the height means Tm * alpha doubles and therefore the gc halfs.

# what are the other jumps in the figure?
- They are the same as the first -> just after the first jump alpha changes -> then the next jump depends on that alpha.

# Why does the FIFO size figure have higher gc values give better performance sometimes?  
- This is a very interesting thing -> let's recall that when gc is bigger -> the model makes Tm bigger -> That means each pop from the FIFO is used for longer -> allowing the the generator to catch up to the core -> making it so we need a *lower* FIFO capacity to have the same performance as an infinite FIFO.
- On the other hand, a lower gc means a shorter tile meaning less usage of the same pop meaning we need more space to be able to prefill it.

# Why is giving more to the FIFO so much worse?
- giving more to the FIFO means less to the L1 cache.
- less to the cache -> tile hight (T_m) must shrink -> generator amortization goes down.
- It looks really bad because of the high gc runs. For the gc = 5 runs, it's not that bad. That's because the high gc runs need the tall tiles the most -> and there they can't really get them.

# Why is random suddenly better at high gc for a little?
- it goes back to 0 at 4000 gc because there the cycles is just pure gc, the overhead of getting memory is so miniscule compared to it.
- at around gc = 1500. The generation is so slow, such that the best tile is the one that allows B to be only generated once, even if it means threshing. And in that case Random threshes less and that's why it beats LRU

# Why did we decide to use a fully assoc cache?
- For eaiser analysis -> no conflict misses -> only capacity misses.
- Then we test how much a non full assoc changes things -> because of the deterministic factor of matrix multiplication -> padding causes them to behave almost the same.


# Slide notes:

slide 12:
- notice the fact that at Tm = 4 they behave the same -> because of the same amoritization.

slide 37:
- notice that even if the best is a square, our model lets you know what square size is the best.

slide 39:
- We decided to test it against different cache sizes because it can also answer the question of should we use a bigger cache or a faster generator.
- Interestingly we see an effect of doubling the cache is exactly like halfing the generation cost (why?).
- Meaning that if we know that we want to lower generation we can actually choose between the two accordingly.
- In addition we can see that from analysing the results we see that generation cost performs as good as free generation as long as gc is approx Tm * alpha. That makes sense if we think about our equation.
- This gives us an idea of how slow we can afford our generator to be without losing on too much performance.

slide 41:
- With seeing how the gc value can effect the FIFO size unexpectingly we decided to see how other hardware factors might effect it.
- The register block sizes by far effected it the most -> with small ones even a very small FIFO size is enough -> and with bigger ones causing up to 20% slowdown even for a 4kB FIFO.
- The memory latency outcome seems backwards also -> we would expect higher latency allowing the generator to keep up and allowing for a smaller FIFO -> but the opposite happends -> why? -> well because even though on a miss we are slow, and the generator fills up then -> between misses we are still very fast and we just empty out the FIFO -> meaning we need more capacity to allow the FIFO to not empty and stall.
- On the other hand actaully making the compute unit slower -> does do what we expect.

slide 44:
- why the dip? the dips accure at places where the best tile is generation bound anyway -> therefore the cache conflicts which effect memory bound areas don't really matter.
- why the spike? Because of how the memory is stacked for that tile specifically -> causing a little more treshing then usual.

slide 56:
- We saw the deterministic factor and LRU really does sometimes when there is no space, it chooses to let go of the elements that we know we will need next -> So we decided to try out random replacemnet instead.
- The expected thing is that random replacement will cause the cliffs to smooth out.
- What's less expected is for how long the random replacement is better than LRU -> that's because in the second step where C is treshing, LRU *always* picks the line we need next, random off course doesn't (in average).
- Why do they go back to the same at high Tm? Because at high Tm -> tall tile -> the amount of cache lines that a tile needs is very high -> at Tm = 300 it's about 3 times the cache -> for random, for it to win against LRU it needs to not evict the line when we come back to it -> in those cases where in one loop we use 3 times the cache, there are so way more misses -> that increases the probability that random will pick the line we want it not to pick for eviction.

slide 57:
- at a very high gc -> no matter what tile we pick -> we are past the second cliff -> there random is just always better.
- between the extremes -> the tile that is picked is the one that is generation bound -> and for generation bound areas -> the policy does not matter -> making it so they have the same performance.

# Final questions

## What is the L_mem/(EK) term?
- Every element of C must come from memory once (compulsory miss) -> L_mem/E cycles per element -> shared by its K MACs -> L_mem/(EK) per MAC.
- Small, but different for every K -> that's the drift in alpha.

## Which matrices do we calibrate on?
- 192×128×256 and 192×1024×256, at gc = 0, every tile simulated -> two full tables of alpha.

## Isn't it circular? The fit test needs the tile height, and alpha depends on it.
- No -> the model goes over every tile -> fit test for that tile -> read alpha of that same tile from the matching table -> predict runtime -> pick the fastest at the end.
- The height is an input to the fit test, never an output.

## How do we get one table where it fits and one where it doesn't?
- Fitting only gets harder as K grows.
- Small K (the smallest we expect, 128) -> anything that fits at our K fits here too.
- Large K (1024) -> nothing fits at all.
- So every tile always has a matching table, also for K bigger than 1024.

## Why would anyone be past the cliff, where random wins?
- On purpose -> extremely slow generator -> the best tile is one row of tiles (T_M = M) so B is generated once, even though it thrashes (gc about 1400 to 4500).
- By accident -> shared cache (other cores take part of it) or tiles hard-coded for a bigger cache -> a tile that fits on paper thrashes.
- Robustness -> random has no sharp cliffs, so a tile that is a bit too tall costs a little instead of a lot.
- Hardware -> random is much cheaper to build than true LRU.
- Otherwise keep LRU and pick a tile that fits -> random is up to 28% slower there.
