# Phase 2: tables from the run records (scripts/v3/analyze.py)

Pairs: 124; problems: 0.

## Cells

| run | S | clean SER | window SER | excess [95% CI] | after | p (Wilcoxon) | rej. [k/n] | false rej. [k/n] |
|---|---|---|---|---|---|---|---|---|
| v3p2F_F1F2_cold__a1_sir0 | 3 | 0.0191 | 0.0590 | +0.0400 [+0.0219, +0.0593] | +0.0009 | 0.25 | 0.967 [116/120] | 0.004 [1/285] |
| v3p2F_F1F2_warm__a1_sir0 | 3 | 0.0148 | 0.0359 | +0.0211 [+0.0109, +0.0372] | +0.0003 | 0.25 | 1.000 [120/120] | 0.004 [1/285] |
| v3p2F_F1_cold__a1_sir0 | 3 | 0.0191 | 0.0590 | +0.0399 [+0.0219, +0.0593] | +0.0009 | 0.25 | 0.958 [115/120] | 0.004 [1/285] |
| v3p2F_F1_warm__a1_sir0 | 3 | 0.0148 | 0.0359 | +0.0211 [+0.0109, +0.0372] | +0.0003 | 0.25 | 1.000 [120/120] | 0.004 [1/285] |
| v3p2F_F2_cold__a1_sir0 | 3 | 0.0189 | 0.0581 | +0.0392 [+0.0216, +0.0584] | +0.0010 | 0.25 | 0.967 [116/120] | 0.000 [0/285] |
| v3p2F_F2_warm__a1_sir0 | 3 | 0.0148 | 0.0348 | +0.0200 [+0.0112, +0.0335] | +0.0002 | 0.25 | 1.000 [120/120] | 0.000 [0/285] |
| v3p2F_base_cold__a1_sir0 | 3 | 0.0189 | 0.0578 | +0.0389 [+0.0214, +0.0579] | +0.0012 | 0.25 | 0.958 [115/120] | 0.000 [0/285] |
| v3p2F_base_warm__a1_sir0 | 3 | 0.0148 | 0.0348 | +0.0200 [+0.0112, +0.0335] | +0.0002 | 0.25 | 1.000 [120/120] | 0.000 [0/285] |
| v3p2Ft_base_cold__a1_sir0 | 5 | 0.0190 | 0.0606 | +0.0416 [+0.0271, +0.0567] | +0.0008 | 0.0625 | 0.945 [189/200] | 0.002 [1/475] |
| v3p2Ft_base_warm__a1_sir0 | 5 | 0.0137 | 0.0311 | +0.0174 [+0.0118, +0.0247] | +0.0004 | 0.0625 | 0.995 [199/200] | 0.002 [1/475] |
| v3p2Ft_fix_cold__a1_sir0 | 5 | 0.0190 | 0.0606 | +0.0416 [+0.0271, +0.0567] | +0.0008 | 0.0625 | 0.945 [189/200] | 0.002 [1/475] |
| v3p2Ft_fix_warm__a1_sir0 | 5 | 0.0137 | 0.0311 | +0.0174 [+0.0118, +0.0247] | +0.0004 | 0.0625 | 0.995 [199/200] | 0.002 [1/475] |
| v3p2G_lmmse_crc__spoof_sir0 | 10 | 0.0477 | 0.0613 | +0.0137 [+0.0042, +0.0280] | -0.0003 | 0.00195 | 1.000 [400/400] | 0.000 [0/950] |
| v3p2G_lmmse_crc__wb_sir0 | 10 | 0.0477 | 0.0488 | +0.0011 [+0.0004, +0.0019] | -0.0003 | 0.00586 | 0.907 [363/400] | 0.000 [0/950] |
| v3p2G_lmmse_never__spoof_sir0 | 10 | 0.0477 | 0.0613 | +0.0137 [+0.0042, +0.0280] | -0.0026 | 0.00195 | 1.000 [400/400] | 0.000 [0/950] |
| v3p2G_lmmse_never__wb_sir0 | 10 | 0.0477 | 0.0491 | +0.0015 [+0.0006, +0.0024] | -0.0028 | 0.0137 | 0.988 [395/400] | 0.000 [0/950] |
| v3p2G_ml_crc__spoof_sir0 | 10 | 0.0053 | 0.0363 | +0.0311 [+0.0219, +0.0413] | -0.0000 | 0.00195 | 1.000 [400/400] | 0.000 [0/950] |
| v3p2G_ml_crc__wb_sir0 | 10 | 0.0053 | 0.0515 | +0.0463 [+0.0333, +0.0615] | +0.0000 | 0.00195 | 0.450 [180/400] | 0.000 [0/950] |
| v3p2G_ml_never__spoof_sir0 | 10 | 0.0053 | 0.0363 | +0.0311 [+0.0219, +0.0413] | +0.0002 | 0.00195 | 1.000 [400/400] | 0.000 [0/950] |
| v3p2G_ml_never__wb_sir0 | 10 | 0.0053 | 0.0250 | +0.0197 [+0.0133, +0.0271] | +0.0002 | 0.00195 | 0.988 [395/400] | 0.000 [0/950] |

## Clean-only runs (mean SER over blocks 5+)

| run | S | SER |
|---|---|---|
| v3p2G_redraw_citadel__clean | 10 | 0.0907 |
| v3p2G_redraw_ml__clean | 10 | 0.0301 |
| v3p2G_redraw_ml_count__clean | 10 | 0.0379 |
| v3p2G_redraw_ml_crc__clean | 10 | 0.0301 |
| v3p2G_redraw_ml_never__clean | 10 | 0.0823 |
| v3p2G_redraw_online_deepsic__clean | 10 | 0.0981 |
| v3p2R_R1cgm_citadel_cc__clean | 3 | 0.0655 |
| v3p2R_R1cgm_frozen_cc__clean | 3 | 0.1055 |
| v3p2R_R1cgm_model_kbest__clean | 3 | 0.0085 |
| v3p2R_R1cgm_model_lmmse__clean | 3 | 0.0916 |
| v3p2R_R1cgm_model_ml__clean | 3 | 0.0085 |
| v3p2R_R1cgm_online_cc__clean | 3 | 0.0484 |
| v3p2R_R2adc3_citadel_cc__clean | 3 | 0.1190 |
| v3p2R_R2adc3_frozen_cc__clean | 3 | 0.1531 |
| v3p2R_R2adc3_model_kbest__clean | 3 | 0.0344 |
| v3p2R_R2adc3_model_lmmse__clean | 3 | 0.1397 |
| v3p2R_R2adc3_model_ml__clean | 3 | 0.0344 |
| v3p2R_R2adc3_online_cc__clean | 3 | 0.0934 |
| v3p2R_R3sat_citadel_cc__clean | 3 | 0.1031 |
| v3p2R_R3sat_frozen_cc__clean | 3 | 0.1307 |
| v3p2R_R3sat_model_kbest__clean | 3 | 0.0479 |
| v3p2R_R3sat_model_lmmse__clean | 3 | 0.1212 |
| v3p2R_R3sat_model_ml__clean | 3 | 0.0479 |
| v3p2R_R3sat_online_cc__clean | 3 | 0.0872 |
| v3p2R_R4iq_citadel_cc__clean | 3 | 0.0679 |
| v3p2R_R4iq_frozen_cc__clean | 3 | 0.1234 |
| v3p2R_R4iq_model_kbest__clean | 3 | 0.0253 |
| v3p2R_R4iq_model_lmmse__clean | 3 | 0.1101 |
| v3p2R_R4iq_model_ml__clean | 3 | 0.0253 |
| v3p2R_R4iq_online_cc__clean | 3 | 0.0483 |
| v3p2R_R5np32_citadel_cc__clean | 3 | 0.1158 |
| v3p2R_R5np32_frozen_cc__clean | 3 | 0.1174 |
| v3p2R_R5np32_model_kbest__clean | 3 | 0.0119 |
| v3p2R_R5np32_model_lmmse__clean | 3 | 0.1008 |
| v3p2R_R5np32_model_ml__clean | 3 | 0.0119 |
| v3p2R_R5np32_online_cc__clean | 3 | 0.0774 |
| v3p2R_R6adc2_citadel_cc__clean | 3 | 0.3045 |
| v3p2R_R6adc2_frozen_cc__clean | 3 | 0.3202 |
| v3p2R_R6adc2_model_kbest__clean | 3 | 0.1935 |
| v3p2R_R6adc2_model_lmmse__clean | 3 | 0.3084 |
| v3p2R_R6adc2_model_ml__clean | 3 | 0.1935 |
| v3p2R_R6adc2_online_cc__clean | 3 | 0.2703 |
| v3p2R_R7sat_citadel_cc__clean | 3 | 0.1519 |
| v3p2R_R7sat_frozen_cc__clean | 3 | 0.1779 |
| v3p2R_R7sat_model_kbest__clean | 3 | 0.1075 |
| v3p2R_R7sat_model_lmmse__clean | 3 | 0.1733 |
| v3p2R_R7sat_model_ml__clean | 3 | 0.1075 |
| v3p2R_R7sat_online_cc__clean | 3 | 0.1278 |
| v3p2R_R8hw_citadel_cc__clean | 3 | 0.2335 |
| v3p2R_R8hw_frozen_cc__clean | 3 | 0.2555 |
| v3p2R_R8hw_model_kbest__clean | 3 | 0.1785 |
| v3p2R_R8hw_model_lmmse__clean | 3 | 0.2481 |
| v3p2R_R8hw_model_ml__clean | 3 | 0.1785 |
| v3p2R_R8hw_online_cc__clean | 3 | 0.2110 |

## Paired comparisons (A - B; TOST margin 0.005)

| comparison | S | A - B | 95% CI | 90% CI | p | equivalent |
|---|---|---|---|---|---|---|
| Fix vs base, cold start, excess (seeds 30-34) | 5 | +0.0000 | [+0.0000, +0.0000] | [+0.0000, +0.0000] | 1 | True |
| Fix vs base, warm A1, excess (seeds 30-34) | 5 | +0.0000 | [+0.0000, +0.0000] | [+0.0000, +0.0000] | 1 | True |
| Citadel-Rx vs ML + CRC-verified guard, A1, window SER | 10 | -0.0247 | [-0.0399, -0.0111] | [-0.0372, -0.0128] | 0.00977 | False |
| Citadel-Rx vs ML + guard without re-base, A1, window SER | 10 | +0.0018 | [-0.0037, +0.0084] | [-0.0029, +0.0072] | 0.492 | False |
| Citadel-Rx vs ML + CRC-verified guard, spoof, window SER | 10 | -0.0011 | [-0.0100, +0.0094] | [-0.0089, +0.0081] | 0.695 | False |
| Citadel-Rx vs ML + guard without re-base, spoof, window SER | 10 | -0.0011 | [-0.0100, +0.0094] | [-0.0089, +0.0081] | 0.695 | False |

## Regime scan (group 2R, calibration seeds 0-2, clean)

Clean SER over blocks 5-99 / 50-99 (steady state); Citadel-Rx false rejections over blocks 5-99.

| regime | online_cc | citadel_cc | frozen_cc | model_lmmse | model_ml | model_kbest | Citadel FRR | ML / best adapting (50-99) |
|---|---|---|---|---|---|---|---|---|
| R1cgm | 0.0484 / 0.0223 | 0.0655 / 0.0251 | 0.1055 / 0.0391 | 0.0916 / 0.0356 | 0.0085 / 0.0054 | 0.0085 / 0.0054 | 0.000 | 0.27 |
| R2adc3 | 0.0934 / 0.0638 | 0.1190 / 0.0774 | 0.1531 / 0.0931 | 0.1397 / 0.0868 | 0.0344 / 0.0275 | 0.0344 / 0.0275 | 0.000 | 0.44 |
| R3sat | 0.0872 / 0.0417 | 0.1031 / 0.0417 | 0.1307 / 0.0554 | 0.1212 / 0.0532 | 0.0479 / 0.0257 | 0.0479 / 0.0257 | 0.000 | 0.68 |
| R4iq | 0.0483 / 0.0231 | 0.0679 / 0.0269 | 0.1234 / 0.0598 | 0.1101 / 0.0551 | 0.0253 / 0.0166 | 0.0253 / 0.0166 | 0.000 | 0.77 |
| R5np32 | 0.0774 / 0.0371 | 0.1158 / 0.0456 | 0.1174 / 0.0490 | 0.1008 / 0.0427 | 0.0119 / 0.0077 | 0.0119 / 0.0077 | 0.014 | 0.22 |
| R6adc2 | 0.2703 / 0.2411 | 0.3045 / 0.2683 | 0.3202 / 0.2824 | 0.3084 / 0.2725 | 0.1935 / 0.1779 | 0.1935 / 0.1779 | 0.000 | 0.74 |
| R7sat | 0.1278 / 0.0698 | 0.1519 / 0.0789 | 0.1779 / 0.1004 | 0.1733 / 0.1002 | 0.1075 / 0.0655 | 0.1075 / 0.0655 | 0.000 | 0.94 |
| R8hw | 0.2110 / 0.1489 | 0.2335 / 0.1652 | 0.2555 / 0.1909 | 0.2481 / 0.1861 | 0.1785 / 0.1327 | 0.1785 / 0.1327 | 0.000 | 0.89 |

Rule (docs/v3/PHASE2.md): no regime reaches r >= 1.25 (best R7sat, r = 0.94): the paper is framed as protecting a test-time learner, and the main regime is the one with the largest r
