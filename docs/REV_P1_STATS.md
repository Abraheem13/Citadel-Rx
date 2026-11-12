# Revision statistics (scripts/revision_stats.py)

Primary metric: excess SER = attacked minus clean SER on the same blocks of the same seed and configuration (audit E3). Intervals: moving-block bootstrap over seeds and contiguous runs of blocks, with the block length set to twice the measured decorrelation length (audit E1). Tests: exact seed-level Wilcoxon signed-rank on per-seed mean excess SER, Holm-corrected within each family (families listed at the end, audit E8). Rates: counts and Wilson 95% intervals (audit E6).

Matched attacked/clean pairs: 110.

**A1 whitebox, SIR -10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0166 [+0.0111, +0.0228] | +0.0001 [-0.0002, +0.0005] | 0.0288 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| CRC-Rollback | 3 | +0.4322 [+0.3490, +0.5272] | +0.5805 [+0.4525, +0.6603] | 0.4604 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.8971 [+0.8712, +0.9208] | +0.0940 [+0.0520, +0.1432] | 0.9341 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.8688 [+0.7821, +0.9373] | +0.1027 [+0.0245, +0.1918] | 0.8971 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| online_select | 3 | +0.8803 [+0.7933, +0.9491] | +0.0636 [+0.0160, +0.1242] | 0.8972 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 whitebox, SIR 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 10 | +0.0188 [+0.0142, +0.0246] | +0.0004 [+0.0001, +0.0008] | 0.0340 | 6 / 12 | 0.0020 (0.0098) | 0.0020 | 0.0020 |
| CRC-Rollback | 10 | +0.2712 [+0.2340, +0.3067] | +0.3462 [+0.3199, +0.3761] | 0.3026 | 5 / 10 | 0.0020 (0.0098) | 0.0020 | 0.0020 |
| Meta-DeepSIC | 10 | +0.6507 [+0.6303, +0.6698] | +0.0882 [+0.0714, +0.1064] | 0.6896 | 2 / 5 | 0.0020 (0.0098) | 0.0020 | 0.0020 |
| Online DeepSIC | 10 | +0.7675 [+0.7153, +0.8150] | +0.0189 [+0.0108, +0.0274] | 0.7990 | 6 / 12 | 0.0020 (0.0098) | 0.0020 | 0.0020 |
| online_select | 10 | +0.7645 [+0.7109, +0.8135] | +0.0118 [+0.0074, +0.0166] | 0.7845 | 6 / 12 | 0.0020 (0.0098) | 0.0020 | 0.0020 |

**A1 whitebox, SIR 10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0088 [+0.0051, +0.0129] | +0.0007 [-0.0000, +0.0014] | 0.0210 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| CRC-Rollback | 3 | +0.0642 [+0.0462, +0.0853] | +0.0011 [-0.0004, +0.0027] | 0.0925 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1954 [+0.1785, +0.2110] | +0.0419 [+0.0286, +0.0564] | 0.2323 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.2957 [+0.2562, +0.3327] | +0.0084 [+0.0042, +0.0124] | 0.3239 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| online_select | 3 | +0.1809 [+0.1416, +0.2209] | +0.0043 [+0.0018, +0.0070] | 0.1979 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 transfer, SIR 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0147 [+0.0096, +0.0205] | +0.0000 [-0.0003, +0.0003] | 0.0269 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| CRC-Rollback | 3 | +0.2640 [+0.2303, +0.2961] | +0.2966 [+0.2486, +0.3605] | 0.2923 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1943 [+0.1604, +0.2282] | +0.0165 [+0.0078, +0.0268] | 0.2312 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.3821 [+0.3305, +0.4315] | +0.0102 [+0.0021, +0.0194] | 0.4104 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| online_select | 3 | +0.3762 [+0.3240, +0.4259] | +0.0077 [+0.0031, +0.0138] | 0.3932 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**Data-jamming control, 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.8373 [+0.8334, +0.8408] | -0.0000 [-0.0003, +0.0002] | 0.8496 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| CRC-Rollback | 3 | +0.8239 [+0.8186, +0.8283] | -0.0010 [-0.0022, +0.0001] | 0.8522 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.8159 [+0.8082, +0.8228] | +0.0000 [+0.0000, +0.0000] | 0.8528 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.8218 [+0.8161, +0.8273] | +0.0000 [+0.0000, +0.0000] | 0.8501 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| online_select | 3 | +0.8333 [+0.8288, +0.8373] | +0.0000 [+0.0000, +0.0000] | 0.8503 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

## Gate rates with counts

**A1 whitebox, SIR -10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 120 / 120 | 1.000 [0.969, 1.000] | 4 / 165 | 0.024 [0.009, 0.061] |
| CRC-Rollback | 104 / 120 | 0.867 [0.794, 0.916] | 77 / 165 | 0.467 [0.392, 0.543] |

**A1 whitebox, SIR 0 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 397 / 400 | 0.993 [0.978, 0.997] | 10 / 550 | 0.018 [0.010, 0.033] |
| CRC-Rollback | 359 / 400 | 0.897 [0.864, 0.924] | 349 / 550 | 0.635 [0.593, 0.674] |

**A1 whitebox, SIR 10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 114 / 120 | 0.950 [0.895, 0.977] | 0 / 165 | 0.000 [0.000, 0.023] |
| CRC-Rollback | 109 / 120 | 0.908 [0.843, 0.948] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 transfer, SIR -10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|

**A1 transfer, SIR 0 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 120 / 120 | 1.000 [0.969, 1.000] | 4 / 165 | 0.024 [0.009, 0.061] |
| CRC-Rollback | 89 / 120 | 0.742 [0.657, 0.812] | 77 / 165 | 0.467 [0.392, 0.543] |

**A1 transfer, SIR 10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|

## Multiple-comparison families (audit E8)

- Holm family 'A1 whitebox, SIR -10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 5.
- Holm family 'A1 whitebox, SIR 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 5.
- Holm family 'A1 whitebox, SIR 10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 5.
- Holm family 'A1 transfer, SIR 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 5.
- Holm family 'Data-jamming control, 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 5.
