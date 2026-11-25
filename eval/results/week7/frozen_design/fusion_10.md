## Flight 10: fused vs odometry-only vs fixes-only (mean over seeds [p5, p95]); design: fix_inflation 1.2, gate mixture_pvalue

| Drift | Fused ATE RMSE | Fused median | Odometry-only RMSE (from prior) | Odometry-only RMSE from TRUE start (oracle) | Fixes-only RMSE / median | Fused NEES (2 = consistent) | Fused cov 95 % | Odo cov 95 % | Published share | Published median | Published cov 95 % | Fixes fused / gated / thinned (of candidates) | Outlier share | Per-frame latency ms (median / p95: odometry + fix + belief) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.1 % | 21.4 [20.5, 22.5] | 11.2 [9.4, 13.3] | 71.1 [65.9, 76.4] | 6.2 [3.0, 11.0] | 86.7 / 30.1 | 4.67 [3.87, 5.65] | 0.71 [0.57, 0.85] | 1.00 [1.00, 1.00] | 1.00 | 11.2 [9.4, 13.3] | 0.71 [0.57, 0.85] | 48 / 0 / 91 (139) | 0.34 | 0.27 / 1.63 |
| 0.5 % | 24.3 [21.3, 30.6] | 16.9 [14.2, 21.2] | 78.3 [52.2, 108.1] | 32.3 [17.8, 52.4] | 86.7 / 30.1 | 3.12 [2.24, 4.83] | 0.85 [0.66, 0.92] | 0.99 [0.99, 1.00] | 1.00 | 16.9 [14.2, 21.2] | 0.85 [0.66, 0.92] | 48 / 0 / 91 (139) | 0.32 | 0.26 / 1.60 |
| 1.0 % | 29.7 [24.8, 39.1] | 22.4 [17.6, 29.2] | 99.1 [59.6, 157.7] | 61.7 [26.5, 109.2] | 86.7 / 30.1 | 2.63 [1.74, 4.05] | 0.89 [0.81, 0.97] | 0.94 [0.61, 1.00] | 1.00 | 22.4 [17.6, 29.2] | 0.89 [0.81, 0.97] | 48 / 0 / 91 (139) | 0.32 | 0.26 / 1.11 |
| 2.0 % | 44.2 [32.4, 69.5] | 31.8 [25.4, 40.4] | 142.4 [76.8, 278.2] | 133.2 [56.5, 218.7] | 86.7 / 30.1 | 2.61 [1.61, 5.40] | 0.92 [0.73, 0.99] | 0.93 [0.57, 1.00] | 1.00 | 31.8 [25.4, 40.4] | 0.92 [0.73, 0.99] | 48 / 0 / 91 (139) | 0.34 | 0.25 / 0.72 |

State shares (mean over seeds):

| Drift | STRONG | AGING | UNCERTAIN | DO_NOT_PUBLISH |
|---|---|---|---|---|
| 0.1 % | 0.22 | 0.02 | 0.76 | 0.00 |
| 0.5 % | 0.22 | 0.02 | 0.76 | 0.00 |
| 1.0 % | 0.22 | 0.02 | 0.76 | 0.00 |
| 2.0 % | 0.20 | 0.29 | 0.51 | 0.00 |

144 frames; ATE over all frames. Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).

### Fix outage: fixes stop at frame 43 (t = 200 s), seed 0

- 1.0 % drift: first AGING at t = 281.0 s, first DO_NOT_PUBLISH at t = None s; at the end error 52 m, 1-sigma 61 m; error inside the 2-sigma band on 100% of the outage frames.
- 2.0 % drift: first AGING at t = 200.0 s, first DO_NOT_PUBLISH at t = 550.0 s; at the end error 216 m, 1-sigma 118 m; error inside the 2-sigma band on 70% of the outage frames.

Errors are against dataset labels and include label registration error; odometry is SYNTHETIC (label path + sampled drift).
