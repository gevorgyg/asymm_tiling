* Using same size elements. But we bring it in way quicker. That's the idea with the fifo.
* The cost in cache goes to zero.
* The non fifo saves space in the L2 only.
* Percision is the same.

* Questions:
    1. can we increase the C tile with FIFO.
    2. depending on elements per cycle, does it effect the tile size of C. And how much does it effect the end to end time.

* Now the ratio will be the amount of bytes per cycle of A to The time of creating the B element with the prng. series of ratios depending on how many cycles to bring in an element of A.
* We want to check this because it can increase the tile size of C, and that is better for performance.


prompt:
  ok listen. We talked to the supervisor. Basically, this is all fine and good. We validated the theory. Now we want
  to get our take on this.

  our take is using the prng and prng fifo.
  the notes from the talk where:

  [Pasted text #1 +11 lines]

  this is very important, cause this tells us what we need to continue with from now on. Let's think about this
  together, what do you think about this? how do you think we should move forward with this in mind?
