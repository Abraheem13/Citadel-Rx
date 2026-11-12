# P6 16-QAM (D5) (scripts/revision_stats.py --by-name)

**P6 16-QAM (D5)**

| configuration | seeds | excess SER in window [95% MB CI] | excess SER after [CI] | raw window SER | seed Wilcoxon p | rejection [Wilson] (k/n) | false rejection [Wilson] (k/n) |
|---|---|---|---|---|---|---|---|
| p6_citadel_qam16__sir0 | 2 | +0.5124 [+0.3953, +0.6297] | +0.0235 [+0.0121, +0.0362] | 0.6083 | 0.5000 | 0.787 [0.686, 0.863] (63/80) | 1.000 [0.966, 1.000] (110/110) |
| p6_lmmse_qam16__sir0 | 2 | +0.9498 [+0.9453, +0.9546] | +0.0000 [+0.0000, +0.0000] | 0.9574 | 0.5000 | - | - |
| p6_online_deepsic_qam16__sir0 | 2 | +0.9411 [+0.9158, +0.9599] | +0.4806 [+0.3706, +0.6029] | 0.9786 | 0.5000 | - | - |
