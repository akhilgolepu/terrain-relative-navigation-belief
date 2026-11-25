### Flight 10 (tune split), n = 144 frames

| Method | Role | Fixes | No-fix rate | Median [m] | p95 [m] | Within 15 m | Wrong (> 50 m) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 144 | 0.000 | 62.0 | 116.6 | 0.028 | 0.625 | 62.0 | 134.4 |
| random | floor | 144 | 0.000 | 134.4 | 231.3 | 0.007 | 0.917 | 62.0 | 134.4 |
| ncc | matcher | 141 | 0.021 | 53.2 | 181.6 | 0.083 | 0.514 | 62.0 | 134.4 |

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

