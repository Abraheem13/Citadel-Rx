# P3 grey-box, query attacker, signal-referenced budget (B6, B8) (scripts/revision_stats.py --by-name)

**P3 grey-box, query attacker, signal-referenced budget (B6, B8)**

| configuration | seeds | excess SER in window [95% MB CI] | excess SER after [CI] | raw window SER | seed Wilcoxon p | rejection [Wilson] (k/n) | false rejection [Wilson] (k/n) |
|---|---|---|---|---|---|---|---|
| p3_citadel_greybox__sir0 | 2 | +0.0148 [+0.0084, +0.0223] | +0.0001 [-0.0003, +0.0004] | 0.0261 | 0.5000 | 1.000 [0.954, 1.000] (80/80) | 0.018 [0.005, 0.064] (2/110) |
| p3_citadel_query__sir0 | 2 | +0.0136 [+0.0077, +0.0211] | -0.0004 [-0.0007, -0.0000] | 0.0249 | 0.5000 | 1.000 [0.954, 1.000] (80/80) | 0.018 [0.005, 0.064] (2/110) |
| p3_citadel_sigbudget__sir0 | 2 | +0.0140 [+0.0081, +0.0211] | -0.0001 [-0.0004, +0.0002] | 0.0253 | 0.5000 | 0.988 [0.933, 0.998] (79/80) | 0.018 [0.005, 0.064] (2/110) |
| p3_online_deepsic_query__sir0 | 2 | +0.5268 [+0.3998, +0.6390] | +0.0116 [-0.0010, +0.0250] | 0.5533 | 0.5000 | - | - |
| p3_online_deepsic_sigbudget__sir0 | 2 | +0.7255 [+0.5906, +0.8450] | +0.0132 [-0.0003, +0.0269] | 0.7520 | 0.5000 | - | - |
