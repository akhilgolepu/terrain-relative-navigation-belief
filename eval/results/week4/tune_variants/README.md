# Week 4 tuning runs on the tune split (flight 10, 144 frames)

All runs: `/usr/bin/python3 eval/eval_matcher.py --split tune --matcher trn_matcher.matcher:FeatureMatcher --matcher-args '<json>' --out <dir>`,
accept-all thresholds (peak_min = ratio_min = 0) unless stated. Exact commands and commits are in each `run_ncc.json`.

| Folder | Commit | Ranking | Feature | Coarse px | Rotation | Purpose |
|---|---|---|---|---|---|---|
| gradient_c64 | ea6aff8 | raw NCC (first version) | gradient | 64 | ±5° | first try; scale piled at 0.8 (bias fixed by Fisher z) |
| intensity_c64 | ea6aff8 | raw NCC (first version) | intensity | 64 | ±5° | as above |
| z_gradient_c64 | 5e965e6 | Fisher z | gradient | 64 | ±5° | setting 1 (feature), compared once |
| z_intensity_c64 | 5e965e6 | Fisher z | intensity | 64 | ±5° | setting 1 (feature): winner |
| z_intensity_c64_rot20 | 5e965e6 | Fisher z | intensity | 64 | ±20° | the one wider rotation sweep |
| z_intensity_c48_rot20 | 3c70607 | Fisher z | intensity | 48 | ±20° | setting 2 (coarse px) |
| z_intensity_c96_rot20 | 3c70607 | Fisher z | intensity | 96 | ±20° | setting 2: winner; thresholds chosen on it (threshold_grid.csv) |
| sift | de82043 | SIFT + RANSAC (fixed settings) | - | - | - | comparison matcher: 0 fixes, rejected; `matcher_sift.py` deleted 2026-11-20 (in git history up to e470a4a) |

The frozen run is in `../tune/` (settings in `src/trn_matcher/trn_matcher/matcher_frozen.json`).
