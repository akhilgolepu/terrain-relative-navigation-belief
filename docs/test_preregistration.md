# Test pre-registration: flight 11 (gansu, arid, test split)

Written 2026-11-21, before any computation on flight 11. Flight 11 has never been matched, fused or
evaluated. This file, the frozen files in `docs/frozen_for_test.md` and their hashes in
`docs/frozen_manifest.json` are committed and tagged `pre-test`. The test is run once by
`eval/run_test.py` (committed and tagged `test-runner` before the run); nothing is fitted or changed
after seeing results. **Every table carries the caveat: errors are against dataset labels, so they
include label registration error; the reported uncertainty is not uncertainty about the true
position. Odometry is SYNTHETIC.**

## What is run

| Pass | What | Seeds | Role |
|---|---|---|---|
| Matcher pass | frozen matcher (accept-all; old gate kept as a flag) on all 590 frames, window +-150 m around the loader prior (label + N(0, 50 m), seed 0) | - | inputs for the calibration tables and the open loop |
| Closed loop | matcher around the fused prediction (window max(150 m, 3 sigma), capped at map extent and 1000 m), thinned fix times, frozen fusion design | 0-4 x 4 drift levels | **HEADLINE** |
| Open loop | recorded matcher-pass candidates, frozen fusion design | 0-19 x 4 drift levels | secondary |

Drift levels 0.1 / 0.5 / 1 / 2 % (RMS drift after 10 km as % of 10 km; odometry seed = 1000 x level index
+ seed, as in weeks 6-7). Environment: the venv (`eval/reference_env_fusion.json`, OpenCV 5.0) for every
pass, because the closed loop needs the matcher and GTSAM in one process; the matcher differs from the
system-Python reference only numerically (week 4 regression test: positions within 0.5 m).

## Definitions (fixed)

- error e = estimate - label (2-D, m); RMSE and median over all 590 frames.
- odometry-only from the prior: dead reckoning from the first-frame prior; from the TRUE start: dead
  reckoning from the first label (oracle, pure drift).
- raw fixes: all matcher-pass candidates, no fusion.
- NEES = mean of e^T P^-1 e over frames (2 if consistent); coverage = share of frames inside the 95 %
  ellipse (e^T P^-1 e <= 5.991).
- wrong fix: |fix - label| > 50 m.
- matcher acceptance: share of frames whose candidate passes the frozen peak/ratio gate.
- **calibration's promise** for a set of fixes: the mean predicted P(wrong) (frozen ratio model) over that
  set. "Wrong rate above the promise" = observed wrong rate > that mean.
- fix validity states (per candidate): STRONG P(wrong) <= 0.15, UNCERTAIN <= 0.389, DO_NOT_PUBLISH above.
- belief validity states (per fused frame): STRONG / AGING / UNCERTAIN / DO_NOT_PUBLISH from the fusion;
  "wrong rate" of a belief state = share of its frames with fused error > 50 m.
- sharpness: median radius of the 90 % region of the calibrated fix model.
- track lost (closed loop): fused error > 150 m for >= 3 consecutive frames.

## Empty headline tables

### T1 Fused position error, flight 11 (HEADLINE = closed loop)

| Drift | Closed loop RMSE (median) [m], seeds 0-4 | Open loop RMSE (median) [m], seeds 0-19 | Odometry-only from prior RMSE [m] | Odometry-only from TRUE start RMSE [m] | Raw fixes RMSE (median) [m] | Closed loop NEES / cov 95 % | Open loop NEES / cov 95 % | Closed-loop runs that lose track |
|---|---|---|---|---|---|---|---|---|
| 0.1 % | | | | | | | | |
| 0.5 % | | | | | | | | |
| 1 % | | | | | | | | |
| 2 % | | | | | | | | |

Errors are against dataset labels and include label registration error; odometry SYNTHETIC.

### T2 Belief validity states, closed loop (all levels, seeds 0-4)

| Drift | STRONG share / wrong | AGING share / wrong | UNCERTAIN share / wrong | DO_NOT_PUBLISH share / wrong |
|---|---|---|---|---|
| 0.1 % | | | | |
| 0.5 % | | | | |
| 1 % | | | | |
| 2 % | | | | |

### T3 Matcher and fix calibration (matcher pass, 590 frames)

| Set | Frames | Observed wrong rate | Calibration's promise (mean P(wrong)) | Above the promise? |
|---|---|---|---|---|
| all candidates | | | | |
| accepted by the frozen gate (acceptance = ...) | | | | |
| fix state STRONG | | | | |
| fix state UNCERTAIN | | | | |
| fix state DO_NOT_PUBLISH | | | | |

### T4 Fix-error calibration on flight 11 (frozen ratio model)

| NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness (median 90 % radius) [m] | ECE of P(wrong) | AUC wrong |
|---|---|---|---|---|---|---|
| | | | | | | |

Errors are against dataset labels and include label registration error.

## Predictions (made before the run)

| # | Prediction | Checked by |
|---|---|---|
| P1 | Closed-loop NEES > 2 on flight 11 (mean over the four drift levels), i.e. the fused belief is overconfident against the labels | T1 |
| P2 | The wrong rate of accepted fixes is above the calibration's promise | T3 row "accepted" |
| P3a | Fusion (closed loop) does NOT beat perfect-start odometry at 0.1 % drift (fused RMSE >= odometry from true start) | T1 |
| P3b | Fusion (closed loop) beats perfect-start odometry at 0.5 %, 1 % and 2 % | T1 |

What we will say if a prediction fails:
- **P1 fails (NEES <= 2):** the fused covariance is consistent or conservative against flight 11's labels. We
  will say the 05-fitted inflation transferred to this flight, unlike flight 10. We will not take that as
  evidence that the belief is consistent about the TRUE position: the labels' registration error is part
  of the error budget.
- **P2 fails (wrong rate at or below the promise):** the calibration did not over-promise on flight 11. We will
  report it as one flight's result, with its sample size, not as proof that the 8.5 % calibrate-flight
  overshoot was noise.
- **P3a fails (fusion beats perfect-start odometry at 0.1 %):** fixes on flight 11 are accurate enough
  relative to the labels to help even against near-perfect odometry. That depends on this flight's label
  offset being small; we will not generalise.
- **P3b fails at some level:** fusion does not help at that drift level on flight 11. We will report it as a
  failure of the method on this flight, with the fix wrong rate and validity states that explain it, and
  not re-run with other settings.

## Rules for the run

- One run. A second run is refused by a lock file.
- **Resume policy.** A crash or infrastructure failure (for example WSL shutting down) is resumed from the
  cached matcher calls, never restarted with changes to frozen files. Any code fix needed to resume is logged.
  The results report says which runs (if any) were resumed or repeated.
- No retuning, no extra variants, no subsets chosen after seeing results. Every prediction is reported,
  including failures.
- Results go to a new folder, `eval/results/test_flight11/`.
