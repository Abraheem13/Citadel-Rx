# Phase 2 report

Records: `results/v3/p2/` and `results/v3/clean_ws5080/`, machine ws5080, commits `4388224`–`18c63c6`;
385 of 385 runs finished, 0 failed. Frozen choice: `configs/v3_frozen_fix.json`. Tables:
`docs/v3/PHASE2_TABLES.md`. Integrity: 124 pairs, 0 problems.

## 2R. Regime scan with the channel-conditioned backbone (seeds 0–2, clean)

The conditioning works as intended: a pre-trained network is now usable on a channel it has not
seen. Frozen SER over blocks 50–99 is 0.039 in R1, against 0.999 for the plain backbone in Phase 1.
It does not make the adapting receivers better than ML with LS CSI.

| Regime | Online (cond.) | Citadel-Rx (cond.) | ML (LS) | r |
|---|---|---|---|---|
| R1 complex | 0.0223 | 0.0251 | 0.0054 | 0.27 |
| R2 3-bit ADC | 0.0638 | 0.0774 | 0.0275 | 0.44 |
| R3 saturation 0.7 | 0.0417 | 0.0417 | 0.0257 | 0.68 |
| R4 IQ | 0.0231 | 0.0269 | 0.0166 | 0.77 |
| R5 32 pilots | 0.0371 | 0.0456 | 0.0077 | 0.22 |
| R6 2-bit ADC | 0.2411 | 0.2683 | 0.1779 | 0.74 |
| R7 saturation 0.4 | 0.0698 | 0.0789 | 0.0655 | **0.94** |
| R8 combined | 0.1489 | 0.1652 | 0.1327 | 0.89 |

(SER over blocks 50–99, geometric mean over seeds. Citadel-Rx's clean false rejection is 0 except
0.014 in R5.)

**Decision (rule 2R): r < 1.25 in every regime.** On 4×4 QPSK no tested channel or impairment makes
an adapting deep receiver better than exhaustive ML with the LS estimate on clean blocks. The paper
is framed as protecting a test-time learner. The regime closest to parity is R7 (r = 0.94).

## 2F / 2Ft. Cold-start fixes

| Variant (seeds 0–2) | Warm excess | Cold excess | Clean false rejection |
|---|---|---|---|
| base | +0.0200 | +0.0389 | 0.000 |
| F2 | +0.0200 | +0.0392 | 0.000 |
| F1 | +0.0211 | +0.0399 | 0.004 |
| F1+F2 | +0.0211 | +0.0400 | 0.004 |

**Freeze (rule 2F): base.** No fix helps, so the "fix" tested on seeds 30–34 equals base: cold excess
+0.0416 [0.0271, 0.0567], warm +0.0174.

**Decision (rule 2Ft): not adopted. The cold start remains a stated limitation of size about +0.04.**

The Phase 1 diagnosis (a leaked block owning a whole consolidation) is therefore **not** the main
cause:
- During a 40-block attack from block 0, Citadel-Rx's SER is 0.063.
- A pre-trained network that never adapts has 0.050 on the same clean blocks, and 0.035 with CRC
  selection.

Most of the cost is that the receiver cannot learn while every block is poisoned. The rest (about
0.013 beyond the frozen receiver) is not explained yet and is a Phase 3 item.

## 2G. Stronger model-based guards (seeds 20–29, SED)

| Receiver | Clean | A1 window SER | A1 rejected | Spoof window SER | After a legitimate redraw (clean) |
|---|---|---|---|---|---|
| **Citadel-Rx** (Phase 1) | 0.0124 | **0.0269** | 399/400 | **0.0353** | 0.0907 |
| ML + guard, CRC-verified re-base | **0.0053** | 0.0515 | 180/400 | 0.0363 | **0.0301** |
| ML + guard, no re-base | **0.0053** | **0.0250** | 395/400 | 0.0363 | 0.0823 |
| ML + guard, count re-base (Phase 1) | 0.0053 | 0.0593 | 168/400 | 0.7302 | 0.0379 |
| ML, no guard | 0.0053 | 0.0880 | – | – | 0.0301 |
| LMMSE + guard, CRC-verified re-base | 0.0477 | 0.0488 | 363/400 | 0.0613 | – |
| Online DeepSIC | 0.0285 | 0.7836 | – | 0.7676 | 0.0981 |

**Paired window-SER differences (Citadel-Rx minus guard):**

| Comparison | Difference [95% CI] |
|---|---|
| CRC-verified guard, A1 | −0.0247 [−0.0399, −0.0111] |
| No-re-base guard, A1 | +0.0018 [−0.0037, +0.0084] (not distinguishable) |
| Either guard, spoof | −0.0011 [−0.0100, +0.0094] (not distinguishable) |

**Decision (rule 2G): the first branch is not met.** The CRC-verified ML guard is worse than
Citadel-Rx under A1. The second branch ("Citadel-Rx keeps the lowest window SER against every guard
tested") **does not hold either**: the ML guard that never re-bases is not distinguishable from
Citadel-Rx under A1 and under the spoof, at a clean SER 2.3× lower. Its price is the legitimate
change: 0.0823 after a redraw, against 0.0301 for ML without a guard.

**Mechanism: every single-state protection is captured or locks.**
- The CRC-verified guard accepted about 22 poisoned estimates through the CRC comparison: in those
  blocks the poisoned estimate passed as many CRCs as the stale protected one (0.64 against 0.84 on
  average).
- Each acceptance re-based the noise and innovation references onto the attack, after which 198 more
  attacked blocks passed the pilot tests outright.

| Single-state protection | Under a lasting attack | Under a legitimate change |
|---|---|---|
| Count re-base | captured | follows it |
| CRC-verified re-base | captured after rare leaks | follows it |
| No re-base | holds | locks (stale estimate) |
| CRC-Rollback | absorbing poisoned state | – |

Citadel-Rx's multi-rate memory is the only design tested that holds under attack without locking
*relative to its own learner*: after the redraw it reaches 0.0907, against 0.0981 for unprotected
online DeepSIC. Its absolute level there is poor because DeepSIC re-adapts slowly, not because of
the gates.

## What this means (input to the decision on the paper's direction)

1. **At 4×4 QPSK the deep receiver is not the best detector,** clean or attacked. ML with LS CSI and
   a no-re-base guard matches Citadel-Rx under attack with a 2.3× lower clean SER, but locks under
   legitimate change.
2. **The general finding is a capture–lock dichotomy for single-state protections,** which
   multi-rate verified consolidation escapes. That is a property of the memory, not of the deep
   network.
3. The most direct test of (2), and possibly the best receiver of the study, is verified multi-rate
   consolidation applied to the **channel estimate** of an ML/K-best receiver: slow levels of
   accepted channel estimates, fallback to the anchor estimate, and CRC selection.
