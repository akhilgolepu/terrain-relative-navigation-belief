## Flight 05: fused vs odometry-only vs fixes-only (mean over seeds [p5, p95])

| Drift | Fused ATE RMSE | Fused median | Odometry-only RMSE (from prior) | Odometry-only RMSE from TRUE start (oracle) | Fixes-only RMSE / median | Fused NEES (2 = consistent) | Fused cov 95 % | Odo cov 95 % | Published share | Published median | Published cov 95 % | Fixes fused / gated / thinned (of candidates) | Outlier share | Per-frame latency ms (median / p95: odometry + fix + belief) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1 % | 11.1 [9.9, 13.1] | 8.1 [6.2, 10.0] | 60.7 [51.5, 71.5] | 11.7 [6.0, 24.6] | 59.5 / 27.4 | 3.07 [2.07, 5.05] | 0.87 [0.72, 0.97] | 1.00 [1.00, 1.00] | 1.00 | 8.1 [6.2, 10.0] | 0.87 [0.72, 0.97] | 125 / 32 / 315 (472) | 0.03 | 0.39 / 8.96 |
| 0.5 % | 18.1 [16.9, 19.6] | 15.2 [13.6, 16.8] | 82.5 [46.5, 116.5] | 53.7 [35.2, 73.1] | 59.5 / 27.4 | 2.66 [2.30, 3.13] | 0.91 [0.86, 0.96] | 1.00 [1.00, 1.00] | 1.00 | 15.2 [13.6, 16.8] | 0.91 [0.86, 0.96] | 125 / 31 / 316 (472) | 0.02 | 0.39 / 2.89 |
| 1.0 % | 24.9 [22.4, 30.3] | 20.2 [18.6, 21.6] | 122.8 [57.2, 222.5] | 107.1 [49.8, 178.2] | 59.5 / 27.4 | 2.52 [2.14, 2.98] | 0.91 [0.87, 0.95] | 0.96 [0.76, 1.00] | 1.00 | 20.2 [18.6, 21.6] | 0.91 [0.87, 0.95] | 125 / 30 / 317 (472) | 0.02 | 0.41 / 1.96 |
| 2.0 % | 37.1 [31.4, 45.7] | 27.0 [23.7, 30.0] | 233.4 [118.3, 384.8] | 224.6 [119.1, 336.0] | 59.5 / 27.4 | 2.26 [1.87, 2.77] | 0.93 [0.89, 0.97] | 0.95 [0.83, 1.00] | 1.00 | 27.0 [23.7, 30.0] | 0.93 [0.89, 0.97] | 127 / 22 / 323 (472) | 0.06 | 0.39 / 1.30 |

State shares (mean over seeds):

| Drift | STRONG | AGING | UNCERTAIN | DO_NOT_PUBLISH |
|---|---|---|---|---|
| 0.1 % | 0.75 | 0.01 | 0.24 | 0.00 |
| 0.5 % | 0.75 | 0.01 | 0.24 | 0.00 |
| 1.0 % | 0.74 | 0.01 | 0.25 | 0.00 |
| 2.0 % | 0.69 | 0.09 | 0.21 | 0.00 |

473 frames; ATE over all frames. Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).

### Fix outage: fixes stop at frame 141 (t = 481 s), seed 0

- 1.0 % drift: first AGING at t = 574.0 s, first DO_NOT_PUBLISH at t = 1553.0 s; at the end error 134 m, 1-sigma 103 m; error inside the 2-sigma band on 97% of the outage frames.
- 2.0 % drift: first AGING at t = 494.0 s, first DO_NOT_PUBLISH at t = 732.0 s; at the end error 359 m, 1-sigma 206 m; error inside the 2-sigma band on 98% of the outage frames.

Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).
