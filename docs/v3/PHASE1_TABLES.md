# Phase 1: tables from the run records (scripts/v3/analyze.py)

Pairs: 250; problems: 0.

## Cells

| run | S | clean SER | window SER | excess [95% CI] | after | p (Wilcoxon) | rej. [k/n] | false rej. [k/n] |
|---|---|---|---|---|---|---|---|---|
| v3p1_model_kbest__wb_sir0 | 10 | 0.0053 | 0.0880 | +0.0827 [+0.0715, +0.0949] | +0.0000 | 0.00195 | – | – |
| v3p1_model_kbest_guard__wb_sir0 | 10 | 0.0053 | 0.0593 | +0.0540 [+0.0426, +0.0669] | +0.0000 | 0.00195 | 0.420 [168/400] | 0.000 [0/950] |
| v3p1_model_lmmse__wb_sir0 | 10 | 0.0477 | 0.3766 | +0.3289 [+0.3061, +0.3489] | +0.0000 | 0.00195 | – | – |
| v3p1_model_lmmse_guard__wb_sir0 | 10 | 0.0477 | 0.2732 | +0.2255 [+0.1843, +0.2663] | +0.0000 | 0.00195 | 0.420 [168/400] | 0.000 [0/950] |
| v3p1_model_ml__wb_sir0 | 10 | 0.0053 | 0.0880 | +0.0827 [+0.0715, +0.0949] | +0.0000 | 0.00195 | – | – |
| v3p1_model_ml_guard__wb_sir0 | 10 | 0.0053 | 0.0593 | +0.0540 [+0.0426, +0.0669] | +0.0000 | 0.00195 | 0.420 [168/400] | 0.000 [0/950] |
| v3p1_model_mmse__wb_sir0 | 10 | 0.0092 | 0.1729 | +0.1638 [+0.1479, +0.1802] | +0.0000 | 0.00195 | – | – |
| v3p1_model_mmse_guard__wb_sir0 | 10 | 0.0092 | 0.1176 | +0.1085 [+0.0878, +0.1319] | +0.0000 | 0.00195 | 0.420 [168/400] | 0.000 [0/950] |
| v3p1a_citadel__wb_sir0 | 10 | 0.0124 | 0.0269 | +0.0144 [+0.0113, +0.0180] | +0.0001 | 0.00195 | 0.998 [399/400] | 0.000 [0/950] |
| v3p1a_crc_rollback__wb_sir0 | 10 | 0.0284 | 0.2999 | +0.2715 [+0.2106, +0.3379] | +0.3718 | 0.00195 | 0.887 [355/400] | 0.001 [1/950] |
| v3p1a_frozen_deepsic__wb_sir0 | 10 | 0.0342 | 0.0342 | +0.0000 [+0.0000, +0.0000] | +0.0000 | 1 | – | – |
| v3p1a_frozen_select__wb_sir0 | 10 | 0.0217 | 0.0332 | +0.0114 [+0.0094, +0.0137] | +0.0000 | 0.00195 | – | – |
| v3p1a_online_deepsic__wb_sir0 | 10 | 0.0285 | 0.7836 | +0.7551 [+0.7008, +0.8042] | +0.0201 | 0.00195 | – | – |
| v3p1b_citadel_cold__a1_sir0 | 10 | 0.0194 | 0.0632 | +0.0438 [+0.0329, +0.0554] | +0.0010 | 0.00195 | 0.958 [383/400] | 0.000 [0/950] |
| v3p1b_citadel_cold__soft_sir0 | 10 | 0.0194 | 0.0647 | +0.0453 [+0.0337, +0.0577] | +0.0011 | 0.00195 | 0.978 [391/400] | 0.000 [0/950] |
| v3p1b_citadel_warm__a1_sir0 | 10 | 0.0133 | 0.0285 | +0.0152 [+0.0125, +0.0181] | +0.0003 | 0.00195 | 0.995 [398/400] | 0.000 [0/950] |
| v3p1c_citadel_burst__sir0 | 10 | 0.0143 | 0.0304 | +0.0161 [+0.0142, +0.0182] | -0.0006 | 0.00195 | 1.000 [400/400] | 0.000 [0/950] |
| v3p1c_citadel_ratchet__sir0 | 10 | 0.0143 | 0.0329 | +0.0186 [+0.0163, +0.0210] | -0.0003 | 0.00195 | 0.995 [398/400] | 0.000 [0/950] |
| v3p1d_citadel__spoof_sir0 | 10 | 0.0124 | 0.0353 | +0.0228 [+0.0163, +0.0314] | -0.0001 | 0.00195 | 0.995 [398/400] | 0.000 [0/950] |
| v3p1d_model_lmmse__spoof_sir0 | 10 | 0.0477 | 0.9317 | +0.8840 [+0.8284, +0.9221] | +0.0000 | 0.00195 | – | – |
| v3p1d_model_lmmse_guard__spoof_sir0 | 10 | 0.0477 | 0.7313 | +0.6837 [+0.5905, +0.7688] | +0.1766 | 0.00195 | 0.253 [101/400] | 0.000 [0/950] |
| v3p1d_model_ml_guard__spoof_sir0 | 10 | 0.0053 | 0.7302 | +0.7249 [+0.6322, +0.8122] | +0.0438 | 0.00195 | 0.253 [101/400] | 0.000 [0/950] |
| v3p1d_online_deepsic__spoof_sir0 | 10 | 0.0285 | 0.7676 | +0.7391 [+0.6850, +0.7902] | +0.1011 | 0.00195 | – | – |
| v3p1f_citadel_qam16w__sir0 | 5 | 0.1024 | 0.6301 | +0.5277 [+0.4398, +0.6196] | +0.0211 | 0.0625 | 0.715 [143/200] | 0.960 [456/475] |
| v3p1f_model_kbest_qam16w__sir0 | 5 | 0.0001 | 0.4527 | +0.4525 [+0.4132, +0.4882] | +0.0000 | 0.0625 | – | – |
| v3p1f_model_lmmse_qam16w__sir0 | 5 | 0.0083 | 0.9570 | +0.9486 [+0.9294, +0.9595] | +0.0000 | 0.0625 | – | – |
| v3p1f_online_deepsic_qam16w__sir0 | 5 | 0.1101 | 0.9885 | +0.8784 [+0.8500, +0.8981] | +0.6852 | 0.0625 | – | – |

## Clean-only runs (mean SER over blocks 5+)

| run | S | SER |
|---|---|---|
| v3p1R_R0sed_citadel__clean | 3 | 0.0158 |
| v3p1R_R0sed_frozen_deepsic__clean | 3 | 0.0403 |
| v3p1R_R0sed_model_kbest__clean | 3 | 0.0067 |
| v3p1R_R0sed_model_lmmse__clean | 3 | 0.0562 |
| v3p1R_R0sed_model_ml__clean | 3 | 0.0067 |
| v3p1R_R0sed_online_deepsic__clean | 3 | 0.0336 |
| v3p1R_R1cgm_citadel__clean | 3 | 0.0690 |
| v3p1R_R1cgm_frozen_deepsic__clean | 3 | 0.9986 |
| v3p1R_R1cgm_model_kbest__clean | 3 | 0.0085 |
| v3p1R_R1cgm_model_lmmse__clean | 3 | 0.0916 |
| v3p1R_R1cgm_model_ml__clean | 3 | 0.0085 |
| v3p1R_R1cgm_online_deepsic__clean | 3 | 0.0427 |
| v3p1R_R2adc3_citadel__clean | 3 | 0.1319 |
| v3p1R_R2adc3_frozen_deepsic__clean | 3 | 0.9987 |
| v3p1R_R2adc3_model_kbest__clean | 3 | 0.0344 |
| v3p1R_R2adc3_model_lmmse__clean | 3 | 0.1397 |
| v3p1R_R2adc3_model_ml__clean | 3 | 0.0344 |
| v3p1R_R2adc3_online_deepsic__clean | 3 | 0.0889 |
| v3p1R_R3sat_citadel__clean | 3 | 0.1174 |
| v3p1R_R3sat_frozen_deepsic__clean | 3 | 0.9990 |
| v3p1R_R3sat_model_kbest__clean | 3 | 0.0479 |
| v3p1R_R3sat_model_lmmse__clean | 3 | 0.1212 |
| v3p1R_R3sat_model_ml__clean | 3 | 0.0479 |
| v3p1R_R3sat_online_deepsic__clean | 3 | 0.0815 |
| v3p1R_R4iq_citadel__clean | 3 | 0.0749 |
| v3p1R_R4iq_frozen_deepsic__clean | 3 | 0.9984 |
| v3p1R_R4iq_model_kbest__clean | 3 | 0.0253 |
| v3p1R_R4iq_model_lmmse__clean | 3 | 0.1101 |
| v3p1R_R4iq_model_ml__clean | 3 | 0.0253 |
| v3p1R_R4iq_online_deepsic__clean | 3 | 0.0436 |
| v3p1R_R5np32_citadel__clean | 3 | 0.1839 |
| v3p1R_R5np32_frozen_deepsic__clean | 3 | 0.9986 |
| v3p1R_R5np32_model_kbest__clean | 3 | 0.0119 |
| v3p1R_R5np32_model_lmmse__clean | 3 | 0.1008 |
| v3p1R_R5np32_model_ml__clean | 3 | 0.0119 |
| v3p1R_R5np32_online_deepsic__clean | 3 | 0.0729 |
| v3p1e_model_kbest_perfect__clean | 10 | 0.0055 |
| v3p1e_model_lmmse_perfect__clean | 10 | 0.0512 |
| v3p1e_model_ml_perfect__clean | 10 | 0.0055 |
| v3p1e_model_mmse_perfect__clean | 10 | 0.0096 |

## Paired comparisons (A - B; TOST margin 0.005)

| comparison | S | A - B | 95% CI | 90% CI | p | equivalent |
|---|---|---|---|---|---|---|
| Citadel-Rx vs frozen + CRC selection, excess | 10 | +0.0030 | [+0.0017, +0.0044] | [+0.0019, +0.0042] | 0.00195 | True |
| Citadel-Rx vs frozen + CRC selection, window SER | 10 | -0.0063 | [-0.0089, -0.0042] | [-0.0084, -0.0044] | 0.00195 | False |
| Citadel-Rx vs guarded ML, window SER | 10 | -0.0325 | [-0.0444, -0.0207] | [-0.0422, -0.0229] | 0.00195 | False |
| Citadel-Rx vs guarded LMMSE, window SER | 10 | -0.2463 | [-0.2883, -0.2035] | [-0.2815, -0.2110] | 0.00195 | False |
| Cold vs warm start, excess | 10 | +0.0286 | [+0.0184, +0.0395] | [+0.0195, +0.0377] | 0.00195 | False |
| Ratchet + burst vs burst, excess in the burst | 10 | -0.0041 | [-0.0082, +0.0001] | [-0.0076, -0.0005] | 0.00195 | False |

## Regime scan (group 1R, calibration seeds 0-2, clean)

Clean SER over blocks 5-99 / 50-99 (steady state); Citadel-Rx false rejections over blocks 5-99.

| regime | online_deepsic | citadel | frozen_deepsic | model_lmmse | model_ml | model_kbest | Citadel FRR | ML / best adapting (50-99) |
|---|---|---|---|---|---|---|---|---|
| R0sed | 0.0336 / 0.0327 | 0.0158 / 0.0137 | 0.0403 / 0.0347 | 0.0562 / 0.0599 | 0.0067 / 0.0062 | 0.0067 / 0.0062 | 0.000 | 0.45 |
| R1cgm | 0.0427 / 0.0200 | 0.0690 / 0.0243 | 0.9986 / 0.9988 | 0.0916 / 0.0356 | 0.0085 / 0.0054 | 0.0085 / 0.0054 | 0.000 | 0.29 |
| R2adc3 | 0.0889 / 0.0592 | 0.1319 / 0.0837 | 0.9987 / 0.9987 | 0.1397 / 0.0868 | 0.0344 / 0.0275 | 0.0344 / 0.0275 | 0.000 | 0.46 |
| R3sat | 0.0815 / 0.0385 | 0.1174 / 0.0468 | 0.9990 / 0.9989 | 0.1212 / 0.0532 | 0.0479 / 0.0257 | 0.0479 / 0.0257 | 0.000 | 0.67 |
| R4iq | 0.0436 / 0.0208 | 0.0749 / 0.0306 | 0.9984 / 0.9985 | 0.1101 / 0.0551 | 0.0253 / 0.0166 | 0.0253 / 0.0166 | 0.000 | 0.80 |
| R5np32 | 0.0729 / 0.0285 | 0.1839 / 0.0907 | 0.9986 / 0.9988 | 0.1008 / 0.0427 | 0.0119 / 0.0077 | 0.0119 / 0.0077 | 0.025 | 0.27 |

Rule (docs/v3/PHASE1.md): no regime reaches r >= 1.25 (best R4iq, r = 0.80): Phase 2 introduces the channel-conditioned backbone and repeats the scan with it
