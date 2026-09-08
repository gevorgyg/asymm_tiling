questions after one go:
1. 

notes:
* alpha graph: 
why alpha is flat. because the Tm cancels in the calculation of (Tm * k * 1/16) / (Tm * Tn * k)

remember that it's b stationary.
first cliff - you bring in A and it spills over, and you don't reuse it that much, so it causes a cliff. 

* what is alpha? the total cycles divided by the number of MACs which is NMK.

* the alpha bowl: because at first gc = 0, so it's just the cost of bringing a. 
then it's the cost of bringing b and also that cost is amoretized by Tm/reg_m.
then it goes up again because Tm is too big so A starts spilling out.

* what is the deal with the going up and down of TN? because at first the C tile still fits, and Tn growing is good 
because it means more A amoretization. But then it's too big for the C tile.

* why 300 and 256? 
256 is L1_cap / L1_line_size. 300 is 10% above that because the eviction is still not that 

* final graph:
how do we know when the optimal is gen bound? by a = gc/tm => gc = a * tm => so we know where it will go gen bound. 

* for orange:
first it's not genbound so we want A residancy, to stay always in l1. So we pick Tm small enough such that we get that.  
then it's genbound and that punishes small Tm (from formula), therefore we need to increase it and then it's the same as the square.  
then for large enough gc the square also goes genbound but stays with the same Tm, and the optimal wins. it's way better then the square. 

* the green:
at first the tile is small enough that the green square fits also in l1, so they are simillar. Then 
the square goes genbound pretty early and the optimal goes genbound around 40 like always, so there is no win for the square this time.
it's flat because they are both genbound at that point, and the ratio is 33%.

* the dip: 
notice the dip is at the same spot, because around gc=40 it looses the cache advantage. 

* why wider for higher Tn? 
because for higher Tn the square also has a higher Tm off course. And that allows him to resist the higher  
gc values, so to stay on par with the optimal shape. 

* why the asymptote shrinks?
at high gc (asymptote), it's fully gen bound, so the speedup it just the ratio 1-(gc/Tm)/(gc/Tm_opt).

todo:
* change name to george.
* slide 13 - put the FIFO into registers.
* remove row major.
* connect between gen cost and traffic cost.
