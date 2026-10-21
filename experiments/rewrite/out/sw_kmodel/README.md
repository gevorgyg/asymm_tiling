# sw_kmodel: K in the model

## alpha of the other K values, from the calibrations

| calibrations | K | within 3 % | within 5 % | worst |
|---|---|---|---|---|
| two calibrations [128, 1024] | 192 | 62% | 97% | 17.2% |
| two calibrations [128, 1024] | 256 | 57% | 98% | 6.6% |
| two calibrations [128, 1024] | 384 | 84% | 84% | 6.5% |
| two calibrations [128, 1024] | 512 | 91% | 91% | 7.2% |
| two calibrations [128, 1024] | 768 | 92% | 92% | 8.0% |
| two calibrations + 1/K term [128, 1024] | 192 | 95% | 99% | 20.0% |
| two calibrations + 1/K term [128, 1024] | 256 | 96% | 100% | 4.5% |
| two calibrations + 1/K term [128, 1024] | 384 | 100% | 100% | 1.2% |
| two calibrations + 1/K term [128, 1024] | 512 | 100% | 100% | 0.6% |
| two calibrations + 1/K term [128, 1024] | 768 | 99% | 100% | 3.6% |
| three calibrations [128, 384, 1024] | 192 | 63% | 98% | 18.4% |
| three calibrations [128, 384, 1024] | 256 | 92% | 99% | 5.1% |
| three calibrations [128, 384, 1024] | 512 | 100% | 100% | 1.3% |
| three calibrations [128, 384, 1024] | 768 | 99% | 100% | 3.5% |
| three calibrations + 1/K term [128, 384, 1024] | 192 | 95% | 99% | 20.0% |
| three calibrations + 1/K term [128, 384, 1024] | 256 | 99% | 100% | 3.0% |
| three calibrations + 1/K term [128, 384, 1024] | 512 | 100% | 100% | 1.2% |
| three calibrations + 1/K term [128, 384, 1024] | 768 | 99% | 100% | 3.6% |

## tile choice on the 120 padded matrices (20 + 100 random, 6 gc each)

| alpha from | median | within 1 % | within 5 % | worst |
|---|---|---|---|---|
| own table | 0.00% | 99% | 100% | 1.9% |
| K model, two calibrations | 0.00% | 86% | 92% | 12.4% |
| K model, two calibrations + 1/K term | 0.00% | 95% | 100% | 5.8% |
| K model, three calibrations | 0.00% | 94% | 100% | 6.0% |
| K model, three calibrations + 1/K term | 0.00% | 96% | 100% | 5.8% |
| one table ($K = 256$) | 0.00% | 76% | 85% | 40.1% |

## predicted vs measured (20 matrices + K sweep, gc > 0)

predicted, one calibration for all: 37086 runs, within 1 % 77.7%, within 5 % 95.8%, predicted too slow (> 1 %) 4004, too fast (> 1 %) 4274
predicted, K model: 37086 runs, within 1 % 86.4%, within 5 % 98.4%, predicted too slow (> 1 %) 568, too fast (> 1 %) 4482
