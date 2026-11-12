# P6 30-step and last-layer variants (D9) (scripts/revision_stats.py --by-name)

**P6 30-step and last-layer variants (D9)**

| configuration | seeds | excess SER in window [95% MB CI] | excess SER after [CI] | raw window SER | seed Wilcoxon p | rejection [Wilson] (k/n) | false rejection [Wilson] (k/n) |
|---|---|---|---|---|---|---|---|
| p6_citadel_last_layer__sir0 | 2 | +0.0145 [+0.0082, +0.0221] | +0.0004 [+0.0000, +0.0007] | 0.0276 | 0.5000 | 0.988 [0.933, 0.998] (79/80) | 0.009 [0.002, 0.050] (1/110) |
| p6_citadel_steps30__sir0 | 2 | +0.0171 [+0.0103, +0.0261] | +0.0015 [-0.0005, +0.0039] | 0.0312 | 0.5000 | 0.975 [0.913, 0.993] (78/80) | 0.127 [0.077, 0.202] (14/110) |
