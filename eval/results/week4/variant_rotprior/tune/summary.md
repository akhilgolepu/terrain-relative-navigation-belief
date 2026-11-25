### Flight 10 (tune split), all frames, n = 144 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 144 | 1.000 | 62.0 | 116.6 | 0.028 | 0.028 | 0.625 | 62.0 | 134.4 |
| random | floor | 144 | 1.000 | 134.4 | 231.3 | 0.007 | 0.007 | 0.917 | 62.0 | 134.4 |
| ncc | matcher | 32 | 0.222 | 22.2 | 33.4 | 0.156 | 0.035 | 0.000 | 62.0 | 134.4 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 10 (tune split), map imagery < 90% of patch, n = 32 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 32 | 1.000 | 63.0 | 113.5 | 0.000 | 0.000 | 0.719 | 63.0 | 141.2 |
| random | floor | 32 | 1.000 | 141.2 | 243.4 | 0.000 | 0.000 | 0.938 | 63.0 | 141.2 |
| ncc | matcher | 7 | 0.219 | 21.1 | 33.8 | 0.000 | 0.000 | 0.000 | 63.0 | 141.2 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 10 (tune split), map imagery >= 90% of patch, n = 112 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 112 | 1.000 | 62.0 | 119.6 | 0.036 | 0.036 | 0.598 | 62.0 | 134.4 |
| random | floor | 112 | 1.000 | 134.4 | 229.0 | 0.009 | 0.009 | 0.911 | 62.0 | 134.4 |
| ncc | matcher | 25 | 0.223 | 22.3 | 32.4 | 0.200 | 0.045 | 0.000 | 62.0 | 134.4 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

