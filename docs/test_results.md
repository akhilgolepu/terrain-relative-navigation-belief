# Flight 11 test results, in the pre-registered tables

The single test run on flight 11, as pre-registered in `docs/test_preregistration.md` (tag `pre-test`).
- Run by `eval/run_test.py` (tag `test-runner`, commit `8c0740f`). Started 2026-11-21 14:41, completed 21:07.
- Raw output: `eval/results/test_flight11/results.md`, `tables.json`, `open_loop.csv`, `closed_loop_summary.csv`,
  `closed_loop/*.csv`, `RUN.lock`, `run.log`.
- Nothing was fitted, tuned or changed after the start. No extra variants were run.

**Run history: one resume, no repeated run.**
- WSL shut down with the Claude Code session at about 17:40, during the last 6 of 20 closed-loop runs. It had already
  done so twice in week 7.
- The run was resumed with `run_test.py --resume` at 20:17 (recorded in `RUN.lock`). The 14 finished runs were
  skipped, and the 6 unfinished ones replayed their cached matcher calls (59 each) and continued.
- No frozen file changed: the guards re-checked every hash. The only commits between start and resume were the
  README draft and `docs/private_files.md` with its script, none of them in the manifest.
- No run was repeated or restarted from scratch.

Flight 11: 590 frames over 81 min. 577 frames got a matcher candidate (13 none).

**Errors are against dataset labels, so they include label registration error; the reported uncertainty is not
uncertainty about the true position. Odometry is SYNTHETIC.**

## T1 Fused position error, flight 11 (HEADLINE = closed loop)

| Drift | Closed loop RMSE (median) [m], seeds 0-4 | Open loop RMSE (median) [m], seeds 0-19 | Odometry-only from prior RMSE [m] | Odometry-only from TRUE start RMSE [m] | Raw fixes RMSE (median) [m] | Closed loop NEES / cov 95 % | Open loop NEES / cov 95 % | Closed-loop runs that lose track |
|---|---|---|---|---|---|---|---|---|
| 0.1 % | 8.9 (7.0) | 8.9 (7.2) | 22.8 | 20.5 | 36.0 (26.7) | 2.13 / 0.94 | 2.13 / 0.94 | 0/5 |
| 0.5 % | 17.3 (14.3) | 17.5 (14.5) | 91.1 | 91.5 | 36.0 (26.7) | 1.92 / 0.96 | 1.98 / 0.95 | 0/5 |
| 1 % | 23.8 (19.0) | 24.6 (19.9) | 199.2 | 199.2 | 36.0 (26.7) | 1.90 / 0.95 | 2.01 / 0.94 | 0/5 |
| 2 % | 34.3 (26.4) | 34.3 (26.9) | 396.9 | 396.2 | 36.0 (26.7) | 1.93 / 0.95 | 1.95 / 0.95 | 0/5 |

Errors are against dataset labels and include label registration error; odometry SYNTHETIC.

## T2 Belief validity states, closed loop (all levels, seeds 0-4)

| Drift | STRONG share / wrong | AGING share / wrong | UNCERTAIN share / wrong | DO_NOT_PUBLISH share / wrong |
|---|---|---|---|---|
| 0.1 % | 0.87 / 0.00 | 0.00 / 0.00 | 0.12 / 0.00 | 0.00 / - |
| 0.5 % | 0.88 / 0.00 | 0.00 / 0.10 | 0.12 / 0.00 | 0.00 / - |
| 1 % | 0.88 / 0.02 | 0.00 / 0.00 | 0.12 / 0.04 | 0.00 / - |
| 2 % | 0.87 / 0.08 | 0.04 / 0.58 | 0.09 / 0.19 | 0.00 / - |

"wrong" = share of the state's frames with fused error > 50 m; "-" = the state never occurred. AGING shares print as
0.00 at 0.1–1 % but are not exactly zero (a few frames, hence a wrong rate at 0.5 %). Errors are against dataset
labels and include label registration error.

## T3 Matcher and fix calibration (matcher pass, 590 frames)

| Set | Frames | Observed wrong rate | Calibration's promise (mean P(wrong)) | Above the promise? |
|---|---|---|---|---|
| all candidates | 577 | 0.114 | 0.129 | no |
| accepted by the frozen gate (acceptance = 0.868 of candidates) | 501 | 0.086 | 0.099 | no |
| fix state STRONG | 507 | 0.081 | 0.098 | no |
| fix state UNCERTAIN | 43 | 0.233 | 0.270 | no |
| fix state DO_NOT_PUBLISH | 27 | 0.556 | 0.499 | yes |

## T4 Fix-error calibration on flight 11 (frozen ratio model)

| NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness (median 90 % radius) [m] | ECE of P(wrong) | AUC wrong |
|---|---|---|---|---|---|---|
| 9.208 | 0.53 | 0.92 | 0.95 | 50.0 | 0.035 | 0.597 |

Errors are against dataset labels and include label registration error.

## Predictions

| # | Prediction | Result | Numbers |
|---|---|---|---|
| P1 | Closed-loop NEES > 2 on flight 11 (mean over the four levels) | **FAILED** | mean NEES 1.97 (2.13 / 1.92 / 1.90 / 1.93) |
| P2 | Accepted-fix wrong rate above the calibration's promise | **FAILED** | observed 0.086 vs promise 0.099 (n = 501) |
| P3a | Fusion does NOT beat perfect-start odometry at 0.1 % | **FAILED** | closed loop 8.9 m vs odometry 20.5 m |
| P3b | Fusion beats perfect-start odometry at 0.5, 1 and 2 % | held | 17.3 vs 91.5 m; 23.8 vs 199.2 m; 34.3 vs 396.2 m |

What we said, before the run, we would say if each prediction failed (quoted from the pre-registration):
- **P1 failed:** "the fused covariance is consistent or conservative against flight 11's labels. We will say the
  05-fitted inflation transferred to this flight, unlike flight 10. We will not take that as evidence that the
  belief is consistent about the TRUE position: the labels' registration error is part of the error budget."
- **P2 failed:** "the calibration did not over-promise on flight 11. We will report it as one flight's result, with its
  sample size, not as proof that the 8.5 % calibrate-flight overshoot was noise."
  - Here n = 501 accepted fixes.
  - Only the DO_NOT_PUBLISH group (27 fixes) was worse than promised.
- **P3a failed:** "fixes on flight 11 are accurate enough relative to the labels to help even against near-perfect
  odometry. That depends on this flight's label offset being small; we will not generalise."
  - Flight 11 is long (81 min), so even 0.1 % drift reaches about 20 m of RMS error.
  - Its fix errors average out well: fused median 7 m against a raw-fix median of 27 m. That is consistent with a
    small systematic label offset on this flight, unlike flight 10's about 20 m along-track offset.

## Plain reading
- On the held-out flight the system did better than predicted. The fused position stayed within about 9–34 m RMS of
  the labels across the drift sweep, and its uncertainty was consistent (95 % ellipse covered 94–96 % of frames).
  No closed-loop run lost track, and the belief never had to refuse publication.
- The fix calibration transferred: ECE 0.035, 95 % coverage 0.95.
- **The ranking power of the ratio is weak on flight 11** (AUC 0.60, against 0.74–0.76 on 05 and 10). The
  calibration is right on average, but it is not good at picking out which individual fix is wrong.
- Closed loop and open loop agree within 1 m. As in week 7, the search window stayed at its floor because fixes kept
  coming.
- These are results on one flight, against labels with registration error, with synthetic odometry. They are not
  flight-ready performance.
