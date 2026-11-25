# Flight 11 test results (single pre-registered run)

Run started 2026-11-21T14:41:49 at commit 8c0740f; resumes: 1 (2026-11-21T20:17:58). Environment {'python': '3.12.3', 'numpy': '2.5.4', 'scipy': '1.18.1', 'opencv': '5.0.0', 'gtsam': '4.3.0'}.

## T1 Fused position error, flight 11 (HEADLINE = closed loop)

| Drift | Closed loop RMSE (median) [m], seeds 0-4 | Open loop RMSE (median) [m], seeds 0-19 | Odometry-only from prior RMSE [m] | Odometry-only from TRUE start RMSE [m] | Raw fixes RMSE (median) [m] | Closed loop NEES / cov 95 % | Open loop NEES / cov 95 % | Closed-loop runs that lose track |
|---|---|---|---|---|---|---|---|---|
| 0.1 % | 8.9 (7.0) | 8.9 (7.2) | 22.8 | 20.5 | 36.0 (26.7) | 2.13 / 0.94 | 2.13 / 0.94 | 0/5 |
| 0.5 % | 17.3 (14.3) | 17.5 (14.5) | 91.1 | 91.5 | 36.0 (26.7) | 1.92 / 0.96 | 1.98 / 0.95 | 0/5 |
| 1 % | 23.8 (19.0) | 24.6 (19.9) | 199.2 | 199.2 | 36.0 (26.7) | 1.90 / 0.95 | 2.01 / 0.94 | 0/5 |
| 2 % | 34.3 (26.4) | 34.3 (26.9) | 396.9 | 396.2 | 36.0 (26.7) | 1.93 / 0.95 | 1.95 / 0.95 | 0/5 |

Errors are against dataset labels and include label registration error; the reported uncertainty is not uncertainty about the true position. Odometry is SYNTHETIC.

## T2 Belief validity states, closed loop (seeds 0-4)

| Drift | STRONG share / wrong | AGING share / wrong | UNCERTAIN share / wrong | DO_NOT_PUBLISH share / wrong |
|---|---|---|---|---|
| 0.1 % | 0.87 / 0.00 | 0.00 / 0.00 | 0.12 / 0.00 | 0.00 / - |
| 0.5 % | 0.88 / 0.00 | 0.00 / 0.10 | 0.12 / 0.00 | 0.00 / - |
| 1 % | 0.88 / 0.02 | 0.00 / 0.00 | 0.12 / 0.04 | 0.00 / - |
| 2 % | 0.87 / 0.08 | 0.04 / 0.58 | 0.09 / 0.19 | 0.00 / - |

wrong = share of the state's frames with fused error > 50 m. Errors are against dataset labels and include label registration error; the reported uncertainty is not uncertainty about the true position. Odometry is SYNTHETIC.

## T3 Matcher and fix calibration (matcher pass, 590 frames)

| Set | Frames | Observed wrong rate | Calibration's promise (mean P(wrong)) | Above the promise? |
|---|---|---|---|---|
| all candidates | 577 | 0.114 | 0.129 | no |
| accepted by the frozen gate (acceptance = 0.868) | 501 | 0.086 | 0.099 | no |
| fix state STRONG | 507 | 0.081 | 0.098 | no |
| fix state UNCERTAIN | 43 | 0.233 | 0.270 | no |
| fix state DO_NOT_PUBLISH | 27 | 0.556 | 0.499 | yes |

## T4 Fix-error calibration on flight 11 (frozen ratio model, 577 candidates)

| NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness (median 90 % radius) [m] | ECE of P(wrong) | AUC wrong |
|---|---|---|---|---|---|---|
| 9.208 | 0.53 | 0.92 | 0.95 | 50.0 | 0.035 | 0.597 |

Errors are against dataset labels and include label registration error.

## Predictions

| # | Prediction | Held? | Numbers |
|---|---|---|---|
| P1 | closed-loop NEES > 2 (mean over levels) | FAILED | mean NEES 1.97 |
| P2 | accepted-fix wrong rate above the promise | FAILED | observed 0.086 vs promise 0.099 (n = 501) |
| P3a | fusion does NOT beat perfect-start odometry at 0.1 % | FAILED | closed 8.9 m vs odometry 20.5 m |
| P3b | fusion beats perfect-start odometry at 0.5, 1 and 2 % | HELD | 0.5 %: 17.3 vs 91.5 m; 1 %: 23.8 vs 199.2 m; 2 %: 34.3 vs 396.2 m |

Errors are against dataset labels and include label registration error; the reported uncertainty is not uncertainty about the true position. Odometry is SYNTHETIC.
