# Weeks 2-8 briefs for the executor

Put this file at `docs/WEEK2_8_BRIEFS.md`. Give the executor ONE week at a time:
"Read CLAUDE.md and the Week N section of docs/WEEK2_8_BRIEFS.md and follow them."

## Rules for every week
- Same rules as CLAUDE.md: metrics only from scripts in `eval/`, log everything in
  `docs/log.md`, ask before sudo, deletes, or downloads over 1 GB, stop on failure with the
  last 30 lines.
- Parts marked **User writes** are core algorithms the user writes. The executor scaffolds
  around them (tests, wrappers, plots, launch files) and explains the code on request, but
  does not write the core itself unless the user says so.
- Time limit: if any single step takes more than about two hours, stop, log, and ask.
- Report back in the planning chat: the acceptance checklist with proof for each item,
  `docs/log.md`, and anything surprising, skipped, or worked around.

---

## Week 2: VIO baseline and drift model
**Goal.** Real VIO numbers on public data, and a drift model fitted from them. Week 6 uses
that model to generate synthetic odometry.

**Tasks**
1. Download two EuRoC sequences (MH_01_easy and V1_01_easy) from the ETH Research Collection
   (https://doi.org/10.3929/ethz-b-000690084). Check the licence and file sizes first.
2. Run OpenVINS on both. If it will not build on 24.04, show the failure and wait for the
   user to choose a fallback.
3. `eval/score_vio.py`: run evo APE and RPE against ground truth, save CSV and plots.
4. **User writes** `eval/fit_drift_model.py`: fit how position error grows with distance
   travelled (for example, random-walk drift per metre) and save `eval/results/drift_params.json`.

**Acceptance checks**
- [ ] CSV with ATE RMSE and RPE for both sequences, produced by one documented command.
- [ ] Plot of position error against distance travelled for both sequences.
- [ ] `drift_params.json` exists and its units are documented in `docs/log.md`.
- [ ] The whole thing reruns from a fresh shell.

**Out of scope.** Tuning VIO parameters, other datasets, any map work.

---

## Week 3: Map side and data loader
**Goal.** A loader that returns an aerial image, its true position, a map patch, and a noisy
prior position, on a split that cannot leak between train, validation and test.

**Tasks**
1. Read the UAV-VisLoc README (https://zenodo.org/records/19603534) to learn which zips cover
   which regions and whether map imagery is included. Pick 2 or 3 regions with different
   terrain. Download only those zips. The dataset is academic-use-only: no redistribution.
2. If the dataset does not include map imagery, use Copernicus DEM tiles
   (`aws s3 ls --no-sign-request s3://copernicus-dem-30m/`) and find an orthoimage source.
   Ask the user before choosing a source, and check its licence.
3. **User writes** the tile store and loader logic: georeferenced tiles, a `map_patch(position, size_m)`
   function, and a loader returning `(image, true_position, map_patch, prior_position)` with a
   configurable prior error.
4. `splits.json`: split by flight or region. A script asserts no flight appears in two splits.
5. Save 10 overlay images showing each aerial footprint on the map.

**Acceptance checks**
- [ ] pytest passes for the loader and the leakage assertion.
- [ ] 10 overlays saved; the user checks that footprints land where they should.
- [ ] Coordinate frames and units are written down in `docs/log.md`.
- [ ] `data/README.md` explains the downloads; no data is committed.

**Out of scope.** Matching, learned models.

---

## Week 4: Terrain matcher
**Goal.** An absolute position fix from an aerial image and map, with diagnostics.

**Tasks**
1. **User writes** the matcher core: classical features (for example SIFT or ORB through
   OpenCV), matched against the map patch in a search window around the prior, with RANSAC
   to estimate the transform and the position. Output the fix plus diagnostics: inlier
   count, inlier ratio, residual, search window, score. Return "no fix" when evidence is weak.
2. Baseline: prior-only (no matching) error, for comparison.
3. `eval/eval_matcher.py`: run on the validation split while developing, on the test split
   once for the final numbers. Save per-sample diagnostics to CSV for week 5.
4. ROS 2 node in `trn_matcher` that publishes the fix and diagnostics.
5. Optional, behind a flag: a pretrained learned matcher for comparison. Ask before
   downloading weights.

**Acceptance checks**
- [ ] Test-split median and 95th-percentile position error in metres, and failure rate.
- [ ] Error CDF plot, with the prior-only baseline on the same plot.
- [ ] Per-sample diagnostics CSV for validation and test.
- [ ] Node publishes fixes when replaying a recorded sequence.

**Out of scope.** Calibration, fusion.

---

## Week 5: Calibration and validity states
**Goal.** The stated uncertainty is honest, and the system says "do not publish" when it
cannot back a fix.

**Tasks**
1. **User writes** the covariance model: map the diagnostics to a predicted error scale
   (for example, regress log error on diagnostics, or scale with a conformal method). Fit on
   the validation split only.
2. **User writes** the validity state machine: STRONG, AGING, UNCERTAIN, DO_NOT_PUBLISH,
   including how `fix_age` moves a state toward AGING. Thresholds come from validation.
3. `eval/eval_calibration.py`: NLL, coverage of the 68% and 95% intervals, a calibration
   curve, the fraction of bad fixes flagged, and the fraction of good fixes wrongly rejected.
4. `docs/validity_rule.md`: the rule for DO_NOT_PUBLISH in plain words, with the numbers.

**Acceptance checks**
- [ ] Coverage table on the test split. Target, not a guarantee: the 68% interval covers
      about 60-76% of cases and the 95% interval covers about 90-99%. If it misses, report the
      miss honestly and do not tune on the test split.
- [ ] Calibration plot and the flagged/rejected rates.
- [ ] `validity_rule.md` exists and matches the code.

**Out of scope.** Fusion. This is the week not to cut.

---

## Week 6: Fusion and the belief message
**Goal.** One node publishes NavBelief by fusing odometry and gated absolute fixes.

**Tasks**
1. Synthetic odometry: ground-truth motion increments plus drift sampled from
   `drift_params.json`. Label it as synthetic in the code, plots and README.
2. **User writes** the factor definitions and gating: odometry factors, absolute-fix factors
   using the calibrated covariance, a robust loss, and chi-square gating of fixes. The
   executor scaffolds the GTSAM/iSAM2 wrapper.
3. `trn_fusion` publishes NavBelief (pose, covariance, fix_age, validity, reason).
4. `launch/replay.launch.py` replays a recorded test flight through the full pipeline.
5. Timeline plot: position error with a plus/minus 2-sigma band, and validity state over time.

**Acceptance checks**
- [ ] Belief node runs on a replayed test flight and publishes at a stated rate.
- [ ] Fixes disabled: error grows as the drift model predicts and validity reaches
      DO_NOT_PUBLISH. Fixes enabled: error stays bounded.
- [ ] Timeline plot saved; per-update latency measured and logged.

**Out of scope.** Degradation tests, PX4 integration.

---

## Week 7: Stress tests, consumer, optional SITL
**Goal.** Show where the system breaks and that a downstream consumer respects confidence.

**Tasks**
1. `eval/degrade.py`: blur, haze or contrast loss, brightness shift, a colour or season
   shift between image and map, wrong prior positions, and fix outages of several lengths.
   Run the pipeline per condition and save one results table.
2. `trn_consumer`: continue when validity is STRONG or AGING, wait or hold when UNCERTAIN or
   DO_NOT_PUBLISH, and log each decision.
3. Failure gallery: at least 3 failures with images and a cause analysis. **User writes** the analysis.
4. Stretch, cut first if short on time: PX4 SITL hold/continue through `px4_msgs` and the
   Micro XRCE-DDS Agent. Ask before installing anything.

**Acceptance checks**
- [ ] Results table (CSV and markdown) with the week 4-6 metrics per condition.
- [ ] 3 or more failure cases with images and causes.
- [ ] Consumer decisions logged; the user records a short screen capture of it waiting
      when confidence drops.
- [ ] If the SITL stretch was skipped, the log says so.

**Out of scope.** New features, retuning on the test split.

---

## Week 8: Ship
**Goal.** A public repo someone else can run, and a write-up that matches the numbers.

**Tasks**
1. README: the problem, the headline result with numbers, how to run, limits, data
   licences and citations.
2. **User writes** `docs/writeup.md`: 2-3 pages in field-note style (question, conditions,
   result, failures).
3. Cleanup: no data or secrets in git, `.gitignore`, pinned requirements, clear folder names.
4. Fresh-clone test: clone into a new folder, follow only the README, and confirm the key
   tables reproduce. Log any deviations.
5. Cross-check: every number in the README and write-up traces to a file in `eval/results/`.
6. Draft the application note for the user to edit and send. The executor never sends email.
7. The user records the demo video (2-3 minutes).

**Acceptance checks**
- [ ] Fresh-clone reproduction passes, or its deviations are listed.
- [ ] A table mapping each claim in the write-up to its source file.
- [ ] At least 3 failure cases in the write-up.
- [ ] Repo has no data, secrets or unlabelled synthetic results.

**Out of scope.** New features.
