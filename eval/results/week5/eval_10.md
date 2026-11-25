## Flight 10: frozen models fitted on 05 (out-of-sample check)

144 frames with a candidate, 54 wrong (|e| > 50 m, 37.5%); effective sample size 51 (wrong indicator) / 68 (log error). 95 % intervals: block bootstrap, blocks of 15 frames.

| Model | NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness: median 90 % radius [m] | ECE P(wrong) | AUC wrong | AURC |
|---|---|---|---|---|---|---|---|---|
| selected (M1 ratio) | 10.447 [9.899, 10.853] | 0.51 [0.42, 0.62] | 0.91 [0.87, 0.95] | 0.97 [0.95, 0.99] | 173.7 | 0.056 [0.058, 0.182] | 0.739 | 0.181 |
| baseline_const (M0 const) | 10.740 [10.037, 11.265] | 0.42 [0.33, 0.53] | 0.67 [0.56, 0.79] | 0.81 [0.75, 0.87] | 85.3 | 0.199 [0.093, 0.294] | 0.500 | 0.385 |
| baseline_ratio (M1 ratio) | 10.447 [9.899, 10.853] | 0.51 [0.42, 0.62] | 0.91 [0.87, 0.95] | 0.97 [0.95, 0.99] | 173.7 | 0.056 [0.058, 0.182] | 0.739 | 0.181 |
| alt_robust (M2 robust) | 10.893 [10.139, 11.514] | 0.40 [0.33, 0.51] | 0.72 [0.60, 0.81] | 0.78 [0.69, 0.84] | 52.1 | 0.236 [0.132, 0.332] | 0.719 | 0.236 |

Old ratio gate (accept highest ratio first): AURC 0.181, AUC 0.739. Frozen matcher gate (peak >= 0.2, ratio >= 1.2): accepts 30.6%, wrong among accepted 0.0%.

Reliability of the selected model's P(wrong) (equal-count bins):

| Bin | n | Mean predicted | Observed wrong rate | Range |
|---|---|---|---|---|
| 1 | 29 | 0.100 | 0.000 | 0.073-0.172 |
| 2 | 29 | 0.271 | 0.276 | 0.173-0.352 |
| 3 | 29 | 0.419 | 0.483 | 0.356-0.467 |
| 4 | 29 | 0.505 | 0.586 | 0.468-0.542 |
| 5 | 28 | 0.564 | 0.536 | 0.544-0.579 |

Frozen validity states (t_strong = None, t_publish = 0.389):

| State | Fraction of frames | Wrong rate | Coverage 95 % in state |
|---|---|---|---|
| STRONG | 0.000 | nan | nan |
| UNCERTAIN | 0.444 | 0.172 | 0.953 |
| DO_NOT_PUBLISH | 0.556 | 0.537 | 0.988 |

Validity cuts set 2026-11-21 (STRONG: P(wrong) <= 0.15, UNCERTAIN: <= 0.389, else DO_NOT_PUBLISH; STRONG cut chosen after the flight 10 curve had been seen):

| State | Fraction of frames | Observed wrong rate | Coverage 90 % | Sharpness: median 90 % radius [m] |
|---|---|---|---|---|
| STRONG | 0.181 | 0.000 | 1.000 | 47.8 |
| UNCERTAIN | 0.264 | 0.289 | 0.895 | 146.5 |
| DO_NOT_PUBLISH | 0.556 | 0.537 | 0.887 | 186.1 |

Risk-coverage at fixed acceptance (wrong rate among accepted):

| Accepted | Ratio gate | P(wrong) selected | P(wrong) alt_robust |
|---|---|---|---|
| 10% | 0.000 | 0.000 | 0.214 |
| 25% | 0.000 | 0.000 | 0.167 |
| 50% | 0.194 | 0.194 | 0.194 |
| 75% | 0.343 | 0.343 | 0.306 |
| 90% | 0.362 | 0.362 | 0.362 |

Candidate P(wrong) thresholds for the validity proposal (selected model; frames with P(wrong) <= t):

| t | Fraction accepted | Wrong rate among accepted | Coverage 95 % among accepted |
|---|---|---|---|
| 0.08 | 0.083 | 0.000 | 1.000 |
| 0.1 | 0.125 | 0.000 | 1.000 |
| 0.15 | 0.181 | 0.000 | 1.000 |
| 0.2 | 0.222 | 0.000 | 1.000 |
| 0.3 | 0.340 | 0.041 | 0.959 |
| 0.389 | 0.444 | 0.172 | 0.953 |

Errors are against dataset labels, so reported uncertainty includes label registration error and is not uncertainty about the true position.
