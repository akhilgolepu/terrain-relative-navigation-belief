## Flight 10: fused vs odometry-only vs fixes-only (mean over seeds [p5, p95])

| Drift | Fused ATE RMSE | Fused median | Odometry-only RMSE (from prior) | Odometry-only RMSE from TRUE start (oracle) | Fixes-only RMSE / median | Fused NEES (2 = consistent) | Fused cov 95 % | Odo cov 95 % | Published share | Published median | Published cov 95 % | Fixes fused / gated / thinned (of candidates) | Outlier share | Per-frame latency ms (median / p95: odometry + fix + belief) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1 % | 19.8 [18.9, 20.8] | 10.2 [8.4, 11.9] | 71.1 [65.9, 76.4] | 6.2 [3.0, 11.0] | 86.7 / 30.1 | 5.09 [4.04, 6.22] | 0.79 [0.64, 0.87] | 1.00 [1.00, 1.00] | 1.00 | 10.2 [8.4, 11.9] | 0.79 [0.64, 0.87] | 40 / 20 / 79 (139) | 0.07 | 0.24 / 1.49 |
| 0.5 % | 24.0 [20.8, 30.5] | 15.9 [12.3, 22.5] | 78.3 [52.2, 108.1] | 32.3 [17.8, 52.4] | 86.7 / 30.1 | 3.78 [2.67, 5.90] | 0.81 [0.64, 0.90] | 0.99 [0.99, 1.00] | 1.00 | 15.9 [12.3, 22.5] | 0.81 [0.64, 0.90] | 40 / 19 / 79 (139) | 0.05 | 0.23 / 1.45 |
| 1.0 % | 32.1 [25.3, 43.6] | 22.4 [18.3, 27.6] | 99.1 [59.6, 157.7] | 61.7 [26.5, 109.2] | 86.7 / 30.1 | 3.71 [2.48, 5.31] | 0.84 [0.72, 0.91] | 0.94 [0.61, 1.00] | 1.00 | 22.4 [18.3, 27.6] | 0.84 [0.72, 0.91] | 40 / 20 / 78 (139) | 0.06 | 0.23 / 0.92 |
| 2.0 % | 46.6 [33.2, 71.9] | 33.3 [26.3, 44.3] | 142.4 [76.8, 278.2] | 133.2 [56.5, 218.7] | 86.7 / 30.1 | 3.10 [2.02, 5.59] | 0.88 [0.69, 0.97] | 0.93 [0.57, 1.00] | 1.00 | 33.3 [26.3, 44.3] | 0.88 [0.69, 0.97] | 42 / 15 / 82 (139) | 0.15 | 0.23 / 0.62 |

State shares (mean over seeds):

| Drift | STRONG | AGING | UNCERTAIN | DO_NOT_PUBLISH |
|---|---|---|---|---|
| 0.1 % | 0.27 | 0.02 | 0.71 | 0.00 |
| 0.5 % | 0.27 | 0.02 | 0.71 | 0.00 |
| 1.0 % | 0.27 | 0.03 | 0.70 | 0.00 |
| 2.0 % | 0.23 | 0.23 | 0.54 | 0.00 |

144 frames; ATE over all frames. Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).

### Fix outage: fixes stop at frame 43 (t = 200 s), seed 0

- 1.0 % drift: first AGING at t = 286.0 s, first DO_NOT_PUBLISH at t = None s; at the end error 46 m, 1-sigma 60 m; error inside the 2-sigma band on 100% of the outage frames.
- 2.0 % drift: first AGING at t = 200.0 s, first DO_NOT_PUBLISH at t = 550.0 s; at the end error 199 m, 1-sigma 118 m; error inside the 2-sigma band on 78% of the outage frames.

Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).
