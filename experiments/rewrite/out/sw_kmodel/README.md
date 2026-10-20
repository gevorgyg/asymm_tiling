# sw_kmodel: K in the model

## alpha of the other K values, from the calibrations

| calibrations | K | within 3 % | within 5 % | worst |
|---|---|---|---|---|
| two calibrations [128, 1024] | 192 | 63% | 99% | 19.6% |
| two calibrations [128, 1024] | 256 | 56% | 99% | 5.1% |
| two calibrations [128, 1024] | 384 | 84% | 84% | 6.5% |
| two calibrations [128, 1024] | 512 | 91% | 91% | 7.2% |
| two calibrations [128, 1024] | 768 | 92% | 92% | 8.0% |
| three calibrations [128, 384, 1024] | 192 | 65% | 99% | 20.8% |
| three calibrations [128, 384, 1024] | 256 | 92% | 99% | 5.1% |
| three calibrations [128, 384, 1024] | 512 | 100% | 100% | 1.3% |
| three calibrations [128, 384, 1024] | 768 | 100% | 100% | 1.9% |

## tile choice on the 20 padded matrices (6 gc each)

| alpha from | median | within 1 % | within 5 % | worst |
|---|---|---|---|---|
| own table | 0.00% | 99% | 100% | 1.9% |
| K model, two calibrations | 0.00% | 86% | 97% | 8.3% |
| K model, three calibrations | 0.00% | 88% | 99% | 6.3% |
| one table ($K = 256$) | 0.01% | 71% | 85% | 37.5% |
