### Flight 05 (calibrate split), all frames, n = 473 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 473 | 1.000 | 55.8 | 125.2 | 0.032 | 0.032 | 0.581 | 55.8 | 125.4 |
| random | floor | 473 | 1.000 | 125.4 | 231.2 | 0.008 | 0.008 | 0.909 | 55.8 | 125.4 |
| ncc | matcher | 354 | 0.748 | 25.4 | 58.3 | 0.186 | 0.140 | 0.085 | 55.8 | 125.4 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 05 (calibrate split), map imagery < 90% of patch, n = 180 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 180 | 1.000 | 55.4 | 121.0 | 0.050 | 0.050 | 0.583 | 55.4 | 124.8 |
| random | floor | 180 | 1.000 | 124.8 | 237.9 | 0.011 | 0.011 | 0.906 | 55.4 | 124.8 |
| ncc | matcher | 135 | 0.750 | 22.0 | 50.4 | 0.237 | 0.178 | 0.067 | 55.4 | 124.8 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

### Flight 05 (calibrate split), map imagery >= 90% of patch, n = 293 frames

| Method | Role | Fixes | Acceptance | Median [m] | p95 [m] | Within 15 m (of fixes) | Within 15 m (of all) | Wrong > 50 m (of fixes) | Floor: prior median [m] | Floor: random median [m] |
|---|---|---|---|---|---|---|---|---|---|---|
| prior | floor | 293 | 1.000 | 57.3 | 126.4 | 0.020 | 0.020 | 0.580 | 57.3 | 126.1 |
| random | floor | 293 | 1.000 | 126.1 | 222.4 | 0.007 | 0.007 | 0.911 | 57.3 | 126.1 |
| ncc | matcher | 219 | 0.747 | 27.9 | 59.1 | 0.155 | 0.116 | 0.096 | 57.3 | 126.1 |

Median and p95 are over accepted frames (fixes) only.

Errors below about 15 m are not distinguishable from label registration error: week 3 found 10-40 m offsets between the dataset positions and the map (eval/results/week3/overlay_offsets.csv). Errors are against the dataset labels.

