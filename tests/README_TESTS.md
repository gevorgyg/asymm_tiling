# Running the Tests

*Note:* Run everything from the project root.

## Prerequisites
```bash
# install test deps
.venv/bin/python -m pip install pytest hypothesis
# optional: lets you type `pytest` instead of `.venv/bin/python -m pytest`
source .venv/bin/activate
```

## Run
```bash
# all tests, fast profile
.venv/bin/python -m pytest tests/

# all tests, many more random traces
HYPOTHESIS_PROFILE=thorough .venv/bin/python -m pytest tests/

# C++ cache vs python cache
.venv/bin/python -m pytest tests/test_cache_diff.py   

# python cache invariants
.venv/bin/python -m pytest tests/test_ref_invariants.py      

# python cache hand-written checks
.venv/bin/python -m pytest tests/test_ref_cache.py    

# whole simulator on a tiny matrix
.venv/bin/python -m pytest tests/test_multi_unit.py   

# only tests with "lost" in the name
.venv/bin/python -m pytest tests/ -k lost      
```

## Useful flags
```bash
-x                   # stop at first failure
-v                   # print every test name
--durations=5        # show the 5 slowest tests
```

## Debugging
#### For running quick manual trace inputs
```bash
# forget saved failing traces
rm -rf .hypothesis                                                  

# C++ cache on a hand-written trace
printf 'r 0\nw 0\nr 40\n' | ./build/cache_driver 6 100 14 4 3 16 20 3 0   

# run the simulator with config.toml
./build/sim                                                         
```

Args for the cache_driver *(sizes/assoc in log2)*:  
`./cache_driver block mem l1_size l1_cycles l1_assoc l2_size l2_cycles l2_assoc write_alloc policy`  
Written as in `config.toml`: sizes > 30 are bytes, `l2_size` 0 means no L2, assoc -1 is fully associative.  
Output per access (H = hit, M = miss, - = not reached):  
`cycles L1 L2 mem`
