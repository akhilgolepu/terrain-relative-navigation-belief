## Flight 05: out-of-fold (block CV within 05)

473 frames with a candidate, 86 wrong (|e| > 50 m, 18.2%); effective sample size 100 (wrong indicator) / 207 (log error). 95 % intervals: block bootstrap, blocks of 15 frames.

| Model | NLL | Coverage 50 % | Coverage 90 % | Coverage 95 % | Sharpness: median 90 % radius [m] | ECE P(wrong) | AUC wrong | AURC |
|---|---|---|---|---|---|---|---|---|
| selected (M1 ratio) | 9.538 [9.286, 9.784] | 0.50 [0.44, 0.56] | 0.90 [0.87, 0.93] | 0.96 [0.94, 0.98] | 48.7 | 0.062 [0.030, 0.105] | 0.757 | 0.113 |
| baseline_const (M0 const) | 9.693 [9.407, 10.010] | 0.50 [0.44, 0.56] | 0.89 [0.83, 0.95] | 0.94 [0.90, 0.97] | 88.1 | 0.079 [0.051, 0.145] | 0.334 | 0.267 |
| baseline_ratio (M1 ratio) | 9.538 [9.286, 9.784] | 0.50 [0.44, 0.56] | 0.90 [0.87, 0.93] | 0.96 [0.94, 0.98] | 48.7 | 0.062 [0.030, 0.105] | 0.757 | 0.113 |
| alt_robust (M2 robust) | 9.580 [9.322, 9.833] | 0.51 [0.45, 0.57] | 0.90 [0.86, 0.93] | 0.96 [0.94, 0.98] | 50.5 | 0.058 [0.031, 0.096] | 0.728 | 0.123 |

Old ratio gate (accept highest ratio first): AURC 0.071, AUC 0.814. Frozen matcher gate (peak >= 0.2, ratio >= 1.2): accepts 74.8%, wrong among accepted 8.5%.

Reliability of the selected model's P(wrong) (equal-count bins):

| Bin | n | Mean predicted | Observed wrong rate | Range |
|---|---|---|---|---|
| 1 | 95 | 0.072 | 0.126 | 0.060-0.077 |
| 2 | 95 | 0.081 | 0.053 | 0.078-0.084 |
| 3 | 95 | 0.091 | 0.084 | 0.084-0.102 |
| 4 | 94 | 0.180 | 0.074 | 0.103-0.307 |
| 5 | 94 | 0.460 | 0.574 | 0.309-0.596 |

Frozen validity states (t_strong = None, t_publish = 0.389):

| State | Fraction of frames | Wrong rate | Coverage 95 % in state |
|---|---|---|---|
| STRONG | 0.000 | nan | nan |
| UNCERTAIN | 0.852 | 0.099 | 0.963 |
| DO_NOT_PUBLISH | 0.148 | 0.657 | 0.957 |

Validity cuts set 2026-11-21 (STRONG: P(wrong) <= 0.15, UNCERTAIN: <= 0.389, else DO_NOT_PUBLISH; STRONG cut chosen after the flight 10 curve had been seen):

| State | Fraction of frames | Observed wrong rate | Coverage 90 % | Sharpness: median 90 % radius [m] |
|---|---|---|---|---|
| STRONG | 0.687 | 0.083 | 0.905 | 47.9 |
| UNCERTAIN | 0.163 | 0.169 | 0.909 | 135.3 |
| DO_NOT_PUBLISH | 0.150 | 0.648 | 0.887 | 185.3 |

Risk-coverage at fixed acceptance (wrong rate among accepted):

| Accepted | Ratio gate | P(wrong) selected | P(wrong) alt_robust |
|---|---|---|---|
| 10% | 0.043 | 0.170 | 0.128 |
| 25% | 0.042 | 0.136 | 0.127 |
| 50% | 0.064 | 0.085 | 0.085 |
| 75% | 0.082 | 0.082 | 0.096 |
| 90% | 0.117 | 0.120 | 0.141 |

Candidate P(wrong) thresholds for the validity proposal (selected model; frames with P(wrong) <= t):

| t | Fraction accepted | Wrong rate among accepted | Coverage 95 % among accepted |
|---|---|---|---|
| 0.08 | 0.290 | 0.117 | 0.920 |
| 0.1 | 0.586 | 0.090 | 0.946 |
| 0.15 | 0.687 | 0.083 | 0.954 |
| 0.2 | 0.732 | 0.081 | 0.957 |
| 0.3 | 0.793 | 0.085 | 0.960 |
| 0.389 | 0.850 | 0.100 | 0.963 |

Errors are against dataset labels, so reported uncertainty includes label registration error and is not uncertainty about the true position.
