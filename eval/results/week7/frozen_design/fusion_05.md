## Flight 05: fused vs odometry-only vs fixes-only (mean over seeds [p5, p95]); design: fix_inflation 1.2, gate mixture_pvalue

| Drift | Fused ATE RMSE | Fused median | Odometry-only RMSE (from prior) | Odometry-only RMSE from TRUE start (oracle) | Fixes-only RMSE / median | Fused NEES (2 = consistent) | Fused cov 95 % | Odo cov 95 % | Published share | Published median | Published cov 95 % | Fixes fused / gated / thinned (of candidates) | Outlier share | Per-frame latency ms (median / p95: odometry + fix + belief) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1 % | 10.2 [8.7, 12.5] | 7.2 [4.9, 10.0] | 60.7 [51.5, 71.5] | 11.7 [6.0, 24.6] | 59.5 / 27.4 | 2.09 [1.05, 3.86] | 0.95 [0.83, 0.99] | 1.00 [1.00, 1.00] | 1.00 | 7.2 [4.9, 10.0] | 0.95 [0.83, 0.99] | 134 / 1 / 337 (472) | 0.09 | 0.35 / 8.18 |
| 0.5 % | 17.2 [15.5, 19.3] | 14.0 [12.6, 15.5] | 82.5 [46.5, 116.5] | 53.7 [35.2, 73.1] | 59.5 / 27.4 | 1.98 [1.57, 2.49] | 0.96 [0.92, 0.99] | 1.00 [1.00, 1.00] | 1.00 | 14.0 [12.6, 15.5] | 0.96 [0.92, 0.99] | 134 / 1 / 337 (472) | 0.09 | 0.36 / 2.77 |
| 1.0 % | 23.8 [20.6, 27.8] | 19.2 [16.8, 21.2] | 122.8 [57.2, 222.5] | 107.1 [49.8, 178.2] | 59.5 / 27.4 | 1.95 [1.46, 2.42] | 0.95 [0.93, 0.98] | 0.96 [0.76, 1.00] | 1.00 | 19.2 [16.8, 21.2] | 0.95 [0.93, 0.98] | 134 / 1 / 337 (472) | 0.09 | 0.33 / 1.60 |
| 2.0 % | 33.4 [29.3, 38.3] | 26.0 [23.3, 29.3] | 233.4 [118.3, 384.8] | 224.6 [119.1, 336.0] | 59.5 / 27.4 | 1.79 [1.47, 2.18] | 0.96 [0.94, 0.99] | 0.95 [0.83, 1.00] | 1.00 | 26.0 [23.3, 29.3] | 0.96 [0.94, 0.99] | 134 / 1 / 337 (472) | 0.09 | 0.30 / 1.00 |

State shares (mean over seeds):

| Drift | STRONG | AGING | UNCERTAIN | DO_NOT_PUBLISH |
|---|---|---|---|---|
| 0.1 % | 0.71 | 0.01 | 0.28 | 0.00 |
| 0.5 % | 0.71 | 0.01 | 0.28 | 0.00 |
| 1.0 % | 0.71 | 0.01 | 0.28 | 0.00 |
| 2.0 % | 0.70 | 0.08 | 0.22 | 0.00 |

473 frames; ATE over all frames. Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).

### Fix outage: fixes stop at frame 141 (t = 481 s), seed 0

- 1.0 % drift: first AGING at t = 567.0 s, first DO_NOT_PUBLISH at t = 1547.0 s; at the end error 147 m, 1-sigma 103 m; error inside the 2-sigma band on 100% of the outage frames.
- 2.0 % drift: first AGING at t = 490.0 s, first DO_NOT_PUBLISH at t = 729.0 s; at the end error 379 m, 1-sigma 207 m; error inside the 2-sigma band on 94% of the outage frames.

Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).
