Feature shift between flight 05 (fit) and flight 10 (check). Medians [p25, p75]; KS = two-sample Kolmogorov-Smirnov statistic (0 = same distribution, 1 = disjoint); shift = (median 10 - median 05) / IQR 05. 'right' = frames with |e| <= 50 m.

| Feature | 05 all | 10 all | KS all | shift all | 05 right | 10 right | KS right | shift right |
|---|---|---|---|---|---|---|---|---|
| log_ratio | 0.578 [0.231, 0.819] | 0.0986 [0.0401, 0.233] | 0.54 | -0.81 | 0.647 [0.383, 0.858] | 0.179 [0.0556, 0.364] | 0.54 | -0.98 |
| peak | 0.303 [0.223, 0.376] | 0.26 [0.216, 0.321] | 0.21 | -0.28 | 0.322 [0.251, 0.387] | 0.279 [0.228, 0.345] | 0.20 | -0.31 |
| peak_z_norm | 0.309 [0.196, 0.399] | 0.269 [0.229, 0.352] | 0.18 | -0.19 | 0.331 [0.236, 0.412] | 0.31 [0.251, 0.389] | 0.12 | -0.12 |
| rel_gap | 0.425 [0.183, 0.538] | 0.0755 [0.0277, 0.208] | 0.51 | -0.98 | 0.454 [0.281, 0.558] | 0.135 [0.042, 0.279] | 0.52 | -1.15 |
| overlap | 1 [1, 1] | 1 [1, 1] | 0.12 | +nan | 1 [1, 1] | 1 [1, 1] | 0.11 | +nan |
| edge_fp | 1.79 [0.858, 2.94] | 2.87 [1.91, 3.83] | 0.28 | +0.52 | 1.72 [0.823, 2.95] | 2.98 [2.07, 3.89] | 0.34 | +0.59 |
| at_bound | 0 [0, 0] | 0 [0, 0] | 0.04 | +nan | 0 [0, 0] | 0 [0, 0] | 0.02 | +nan |
| alt_dist_fp | 0.446 [0.198, 0.79] | 0.508 [0.264, 0.974] | 0.21 | +0.10 | 0.431 [0.185, 0.772] | 0.443 [0.255, 0.84] | 0.23 | +0.02 |
| map_valid | 1 [0.747, 1] | 1 [0.967, 1] | 0.19 | +0.00 | 1 [0.741, 1] | 1 [1, 1] | 0.25 | +0.00 |

Frames with a candidate: 05 473 (86 wrong, 18.2%); 10 144 (54 wrong, 37.5%). Errors are against dataset labels, so reported uncertainty includes label registration error and is not uncertainty about the true position.
