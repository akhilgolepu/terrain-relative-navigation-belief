# Everything that must be frozen before the one test run (flight 11, week 8)

The test split (flight 11, region gansu) has never been run. Nothing below may change after the test
run starts; anything not yet frozen (marked **OPEN**) must be decided and committed first, without
looking at flight 11.

| # | What | File(s) | Status |
|---|---|---|---|
| 1 | Splits: tune = 10, calibrate = 05, test = 11; Jiangsu 18-20 excluded (thermal) | `eval/splits.json`, `eval/check_splits.py` | frozen (week 3) |
| 2 | Loader: prior = label + N(0, 50 m) per axis, seed 0; image resized to 1024 px; map patch 0.5 m/px | `src/trn_matcher/trn_matcher/loader.py` (`LoaderConfig`), `frames.py`, `eval/eval_matcher.py` defaults | frozen (week 4) |
| 3 | Matcher settings: intensity features, coarse 96 px, peak_min 0.2, ratio_min 1.2 | `src/trn_matcher/trn_matcher/matcher_frozen.json` | frozen (`eab9cc3`) |
| 4 | Matcher fixed constants (steps, fine level, normalisation window, exclusion, overlap, top-k) | `src/trn_matcher/trn_matcher/matcher.py` (CAPITALS) | frozen |
| 5 | Search space: window +-150 m, scale 0.8-1.3, rotation +-20 deg | `src/trn_matcher/trn_matcher/interface.py` (`DEFAULT_SEARCH`), `matcher_frozen.json` | frozen (`3c70607`) |
| 6 | Matcher mode for fusion: accept-all (best candidate every frame, old gate as a flag) | `FeatureMatcher(accept_all=True)` in `matcher.py`; used by `eval/fusion_inputs.py` / `closed_loop.py` | frozen (`bac8029`) |
| 7 | Fix error model: ratio-only mixture (sigma, w, sigma_out) | `src/trn_calibration/trn_calibration/calibration_frozen.json`, `covariance.py` | frozen (`3e3a2cb`) |
| 8 | Validity cuts on P(wrong): STRONG <= 0.15, UNCERTAIN <= 0.389 | `src/trn_calibration/trn_calibration/validity_cuts.json` | frozen (2026-11-21; STRONG chosen after flight 10 was seen) |
| 9 | Fusion: SYNTHETIC odometry model (floor + random walk, D_ref 10 km), drift levels 0.1/0.5/1/2 %, 20 seeds, prior 50 m, thinning 9 s, fix inflation 1.2, gate mixture_pvalue at 0.99, AGING 30 m, DO_NOT_PUBLISH 100 m | `src/trn_fusion/trn_fusion/fusion_frozen.json` | frozen (week 6 `6aa1eda`, design freeze `88b463b`) |
| 10 | Fusion code: factors, gate, thinning, validity state machine | `src/trn_fusion/trn_fusion/core.py`, `fix_factor.py`, `odometry_sim.py`, `validity.py` | frozen |
| 11 | Consumer policy | `src/trn_consumer/trn_consumer/policy.py` | frozen (week 7) |
| 12 | Environments: matcher and calibration under system Python (OpenCV 4.6.0, numpy 1.26.4, scipy 1.11.4); fusion under the venv (numpy 2.5.4, scipy 1.18.1, gtsam 4.3.0) | `eval/reference_env.json`, `eval/reference_env_fusion.json`, `eval/envcheck.py` | frozen |
| 13 | Matcher evaluation on 11: report table (both floor baselines, 15 m note, blank-patch split), label-offset diagnostic | `eval/eval_matcher.py` (needs `--allow-test`), `eval/matcher_report.py`, `eval/label_offset.py` | code frozen; the run itself needs Akhil's go |
| 14 | Calibration evaluation on 11 | a separate runner, `eval/run_test.py`; the existing scripts keep refusing flight 11 | RESOLVED (week 8): runner loads only the frozen files, fits nothing |
| 15 | Fusion evaluation on 11 (matcher pass, open loop, closed loop) | `eval/run_test.py` | RESOLVED (week 8) |
| 16 | Open loop or closed loop for the headline test numbers | `docs/test_preregistration.md` | RESOLVED: headline = closed loop (5 seeds), secondary = open loop (20 seeds) (Akhil, week 8) |
| 17 | Headline tables and wording | `docs/test_preregistration.md` | RESOLVED: empty tables T1-T4 and predictions P1-P3, committed and tagged `pre-test` |
| 19 | Hashes of all frozen files | `docs/frozen_manifest.json` (from `eval/make_frozen_manifest.py`) | frozen at tag `pre-test`; checked by `eval/run_test.py` |
| 18 | The 50 m "wrong" threshold, the 15 m label-floor sentence | `trn_calibration/covariance.py` (`WRONG_M`), `eval/matcher_report.py` | frozen |

Notes
- Flight 11's map coverage, footprint (329 m) and terrain differ from 05 and 10. Its fixes will use the frozen
  calibration fitted on 05; any miss must be reported, not fixed.
- The test run is run once; if a bug is found afterwards, the fix and the re-run must be logged as such.
- Not a freeze item but must be settled before anything is published: several committed result files
  (`eval/results/week4/*/frames_*.csv`, `week5/features_*.csv`, `week6/inputs_*.csv`, closed-loop runs) contain
  label-derived positions of UAV-VisLoc flights. The dataset forbids redistribution; keep the repository private
  or strip these files before publishing.
