## Closed loop (matcher around the fused prediction) vs open loop (matcher around the dataset prior)

Same SYNTHETIC odometry seeds (0-4), frozen fusion design. Track lost = fused error > 150 m for >= 3 consecutive frames. Errors are against dataset labels and include label registration error. The week 5 calibration was fitted with +-150 m windows.

| Flight | Drift | Closed-loop RMSE | Open-loop RMSE (same seeds) | Runs that lose track | Attempts | Wrong candidates (> 50 m) | No candidate / window off map | Median window [m] | Gated |
|---|---|---|---|---|---|---|---|---|---|
| 10 | 0.1 % | 21.5 | 21.3 | 0/5 | 252 | 40.0% | 4.8% / 0.0% | 150 | 0 |
| 10 | 0.5 % | 23.4 | 22.5 | 0/5 | 251 | 39.7% | 4.8% / 0.0% | 150 | 0 |
| 10 | 1.0 % | 27.7 | 26.9 | 0/5 | 246 | 41.4% | 2.8% / 0.0% | 150 | 0 |
| 10 | 2.0 % | 49.6 | 51.9 | 0/5 | 249 | 39.2% | 3.6% / 0.0% | 150 | 0 |
| 05 | 0.1 % | 10.7 | 10.3 | 0/5 | 670 | 14.0% | 0.0% / 0.0% | 150 | 0 |
| 05 | 0.5 % | 17.4 | 17.2 | 0/5 | 670 | 13.6% | 0.0% / 0.0% | 150 | 0 |
| 05 | 1.0 % | 24.8 | 24.4 | 0/5 | 677 | 13.3% | 0.1% / 0.0% | 150 | 8 |
| 05 | 2.0 % | 33.3 | 33.6 | 0/5 | 671 | 13.1% | 0.1% / 0.0% | 150 | 0 |
