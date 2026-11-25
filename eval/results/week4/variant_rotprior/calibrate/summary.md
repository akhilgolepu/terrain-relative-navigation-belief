### Flight 05 (calibrate split), all frames, n = 473 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 473 | 1.000 | 55.8 | 125.2 | 0.032 | 0.032 | 0.581 | 55.8 | 125.4 |
| random | floor | 473 | 1.000 | 125.4 | 231.2 | 0.008 | 0.008 | 0.909 | 55.8 | 125.4 |
| ncc | matcher | 109 | 0.230 | 26.6 | 80.5 | 0.138 | 0.032 | 0.147 | 55.8 | 125.4 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 05 (calibrate split), map imagery < 90% of patch, n = 180 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 180 | 1.000 | 55.4 | 121.0 | 0.050 | 0.050 | 0.583 | 55.4 | 124.8 |
| random | floor | 180 | 1.000 | 124.8 | 237.9 | 0.011 | 0.011 | 0.906 | 55.4 | 124.8 |
| ncc | matcher | 41 | 0.228 | 25.2 | 103.3 | 0.195 | 0.044 | 0.171 | 55.4 | 124.8 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 05 (calibrate split), map imagery >= 90% of patch, n = 293 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 293 | 1.000 | 57.3 | 126.4 | 0.020 | 0.020 | 0.580 | 57.3 | 126.1 |
| random | floor | 293 | 1.000 | 126.1 | 222.4 | 0.007 | 0.007 | 0.911 | 57.3 | 126.1 |
| ncc | matcher | 68 | 0.232 | 30.1 | 67.1 | 0.103 | 0.024 | 0.132 | 57.3 | 126.1 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

