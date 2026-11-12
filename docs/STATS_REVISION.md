# Revision statistics (scripts/revision_stats.py)

Primary metric: excess SER = attacked minus clean SER on the same blocks of the same seed and configuration (audit E3). Intervals: moving-block bootstrap over seeds and contiguous runs of blocks, with the block length set to twice the measured decorrelation length (audit E1). Tests: exact seed-level Wilcoxon signed-rank on per-seed mean excess SER, Holm-corrected within each family (families listed at the end, audit E8). Rates: counts and Wilson 95% intervals (audit E6).

Matched attacked/clean pairs: 231.

**A1 whitebox, SIR -10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0010 [-0.0022, +0.0048] | +0.0001 [-0.0007, +0.0008] | 0.0254 | 4 / 8 | 0.5000 (1.0000) | 0.2500 | 1.0000 |
| Drift-detection | 3 | +0.9168 [+0.8976, +0.9342] | +0.0311 [+0.0146, +0.0517] | 0.9752 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.8754 [+0.8526, +0.8965] | +0.1422 [+0.1267, +0.1605] | 0.9329 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.8184 [+0.7797, +0.8552] | +0.1432 [+0.1078, +0.1843] | 0.8631 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.9233 [+0.8991, +0.9434] | +0.0250 [+0.0100, +0.0430] | 0.9726 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.9309 [+0.9087, +0.9500] | +0.0317 [+0.0064, +0.0630] | 0.9746 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 whitebox, SIR 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0018 [-0.0018, +0.0061] | +0.0000 [-0.0006, +0.0006] | 0.0263 | 4 / 8 | 0.5000 (1.0000) | 0.2500 | 1.0000 |
| Drift-detection | 3 | +0.7174 [+0.6931, +0.7390] | +0.0347 [+0.0198, +0.0517] | 0.7758 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.6806 [+0.6518, +0.7103] | +0.1308 [+0.1171, +0.1470] | 0.7381 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.5494 [+0.5151, +0.5787] | +0.1323 [+0.1088, +0.1567] | 0.5941 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.7196 [+0.6876, +0.7498] | +0.0278 [+0.0156, +0.0423] | 0.7688 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.7438 [+0.7210, +0.7647] | +0.0251 [+0.0099, +0.0443] | 0.7875 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 whitebox, SIR 10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0080 [+0.0038, +0.0131] | +0.0003 [-0.0007, +0.0011] | 0.0324 | 3 / 6 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Drift-detection | 3 | +0.2068 [+0.1866, +0.2246] | +0.0173 [+0.0105, +0.0249] | 0.2651 | 3 / 6 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.3394 [+0.3229, +0.3539] | +0.0981 [+0.0895, +0.1055] | 0.3969 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1982 [+0.1769, +0.2201] | +0.0732 [+0.0605, +0.0876] | 0.2429 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.2302 [+0.2174, +0.2409] | +0.0150 [+0.0093, +0.0209] | 0.2794 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.2320 [+0.2200, +0.2438] | +0.0182 [+0.0090, +0.0297] | 0.2757 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 transfer, SIR -10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0015 [-0.0019, +0.0057] | -0.0002 [-0.0008, +0.0004] | 0.0260 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Drift-detection | 3 | +0.2865 [+0.2546, +0.3191] | +0.0124 [+0.0073, +0.0183] | 0.3448 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| LMMSE | 3 | +0.8272 [+0.8105, +0.8425] | +0.0000 [+0.0000, +0.0000] | 0.8733 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.6667 [+0.6125, +0.7141] | +0.1821 [+0.1649, +0.2012] | 0.7242 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1498 [+0.1208, +0.1821] | +0.0144 [+0.0104, +0.0192] | 0.1945 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.3037 [+0.2690, +0.3393] | +0.0085 [+0.0039, +0.0137] | 0.3529 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.3191 [+0.2823, +0.3564] | +0.0061 [-0.0004, +0.0130] | 0.3628 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 transfer, SIR 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0025 [-0.0015, +0.0070] | +0.0004 [-0.0002, +0.0009] | 0.0269 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Drift-detection | 3 | +0.2786 [+0.2489, +0.3107] | +0.0174 [+0.0107, +0.0258] | 0.3369 | 4 / 8 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| LMMSE | 3 | +0.4011 [+0.3865, +0.4171] | +0.0000 [+0.0000, +0.0000] | 0.4472 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.4867 [+0.4399, +0.5342] | +0.1409 [+0.1268, +0.1563] | 0.5443 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1688 [+0.1466, +0.1935] | +0.0277 [+0.0215, +0.0347] | 0.2135 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.2974 [+0.2680, +0.3269] | +0.0181 [+0.0115, +0.0261] | 0.3467 | 3 / 6 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.3107 [+0.2816, +0.3386] | +0.0159 [+0.0068, +0.0262] | 0.3544 | 3 / 6 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**A1 transfer, SIR 10 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.0127 [+0.0078, +0.0176] | +0.0011 [+0.0003, +0.0019] | 0.0371 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Drift-detection | 3 | +0.1410 [+0.1255, +0.1578] | +0.0222 [+0.0149, +0.0303] | 0.1993 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| LMMSE | 3 | +0.0183 [+0.0153, +0.0214] | +0.0000 [+0.0000, +0.0000] | 0.0644 | 3 / 6 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.2380 [+0.2186, +0.2600] | +0.0880 [+0.0759, +0.1015] | 0.2955 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.1260 [+0.1116, +0.1409] | +0.0470 [+0.0383, +0.0564] | 0.1707 | 1 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.1562 [+0.1399, +0.1737] | +0.0209 [+0.0125, +0.0296] | 0.2054 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.1566 [+0.1381, +0.1773] | +0.0193 [+0.0124, +0.0269] | 0.2003 | 2 / 5 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

**Data-jamming control, 0 dB**

| receiver | seeds | excess SER in window [95% moving-block CI] | excess SER, 30 blocks after [CI] | raw window SER | decorr. length / bootstrap block | seed-level Wilcoxon p (Holm) | min. attainable p | sign-test p |
|---|---|---|---|---|---|---|---|---|
| Citadel-Rx | 3 | +0.8238 [+0.8189, +0.8282] | +0.0004 [-0.0004, +0.0012] | 0.8482 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Drift-detection | 3 | +0.8000 [+0.7925, +0.8070] | +0.0000 [+0.0000, +0.0000] | 0.8583 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| LMMSE | 3 | +0.8462 [+0.8350, +0.8570] | +0.0000 [+0.0000, +0.0000] | 0.8923 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Median-of-means gradient | 3 | +0.8005 [+0.7913, +0.8097] | +0.0000 [+0.0000, +0.0000] | 0.8580 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Meta-DeepSIC | 3 | +0.8068 [+0.7981, +0.8145] | +0.0000 [+0.0000, +0.0000] | 0.8515 | 5 / 10 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Online DeepSIC | 3 | +0.8055 [+0.7968, +0.8137] | +0.0000 [+0.0000, +0.0000] | 0.8548 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |
| Single-memory Titans | 3 | +0.8171 [+0.8063, +0.8273] | +0.0000 [+0.0000, +0.0000] | 0.8608 | 6 / 12 | 0.2500 (1.0000) | 0.2500 | 0.2500 |

## Gate rates with counts

**A1 whitebox, SIR -10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 196 / 200 | 0.980 [0.950, 0.992] | 4 / 275 | 0.015 [0.006, 0.037] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 whitebox, SIR 0 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 193 / 200 | 0.965 [0.930, 0.983] | 1 / 275 | 0.004 [0.001, 0.020] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 whitebox, SIR 10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 171 / 200 | 0.855 [0.800, 0.897] | 0 / 275 | 0.000 [0.000, 0.014] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 transfer, SIR -10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 198 / 200 | 0.990 [0.964, 0.997] | 4 / 275 | 0.015 [0.006, 0.037] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 transfer, SIR 0 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 195 / 200 | 0.975 [0.943, 0.989] | 1 / 275 | 0.004 [0.001, 0.020] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

**A1 transfer, SIR 10 dB**

| receiver | rejected / poisoned blocks | rejection [Wilson 95%] | rejected / clean blocks | false rejection [Wilson 95%] |
|---|---|---|---|---|
| Citadel-Rx | 156 / 200 | 0.780 [0.718, 0.832] | 0 / 275 | 0.000 [0.000, 0.014] |
| Single-memory Titans | 0 / 120 | 0.000 [0.000, 0.031] | 0 / 165 | 0.000 [0.000, 0.023] |

## Multiple-comparison families (audit E8)

- Holm family 'A1 whitebox, SIR -10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 6.
- Holm family 'A1 whitebox, SIR 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 6.
- Holm family 'A1 whitebox, SIR 10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 6.
- Holm family 'A1 transfer, SIR -10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 7.
- Holm family 'A1 transfer, SIR 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 7.
- Holm family 'A1 transfer, SIR 10 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 7.
- Holm family 'Data-jamming control, 0 dB': H0(receiver) = 'mean excess SER is zero', one per receiver row, size 7.
