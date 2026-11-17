# Phase 1 report

Records: `results/v3/p1/` (398 records) and `results/v3/clean_ws5080/` (150 twins). The runs are on
machine ws5080, commits `a427997`–`b5ead33`; 548 of 548 finished, 0 failed. Tables:
`docs/v3/PHASE1_TABLES.md` (written by `scripts/v3/analyze.py --phase 1`). Integrity: all 250 attacked
runs paired with a twin from ws5080, and every pair is identical before its first attacked block.

Test seeds 20–29 (five seeds for 1f), white-box A1 at SIR 0 dB unless stated. Excess = attacked
minus twin, window mean, 95% moving-block bootstrap interval; tests are exact Wilcoxon (smallest
attainable p = 0.002 with 10 seeds).

## 1a. Is adaptation needed on the benchmark channel?

| Receiver | Clean SER | Window SER | Excess [95% CI] | After | Rejected | False rej. |
|---|---|---|---|---|---|---|
| **Citadel-Rx** | **0.0124** | **0.0269** | +0.0144 [0.0113, 0.0180] | +0.0001 | 399/400 | 0/950 |
| Frozen + CRC selection | 0.0217 | 0.0332 | +0.0114 [0.0094, 0.0137] | 0 | – | – |
| Frozen (never adapts) | 0.0342 | 0.0342 | 0 | 0 | – | – |
| Online DeepSIC | 0.0285 | 0.7836 | +0.755 [0.701, 0.804] | +0.0201 | – | – |
| CRC-Rollback | 0.0284 | 0.2999 | +0.272 [0.211, 0.338] | **+0.372** | 355/400 | 1/950 |

**Paired comparisons:**
- Citadel-Rx's **window SER** is lower than frozen + selection by −0.0063 [−0.0089, −0.0042],
  p = 0.002.
- Their **excess** is equivalent at the 0.005 margin (difference +0.0030; 90% CI [+0.0019, +0.0042]).

**Decision (rule 1a):** adaptation pays on SED, but by a small margin. Under attack, Citadel-Rx is
better in absolute terms because its clean level is 43% lower. It is not more robust than a receiver
that never adapts, which has the same excess by construction. The paper says this explicitly. The
case for adaptation must come from Phase 2, where frozen networks fail (R1–R5: frozen DeepSIC SER
0.998).

CRC-Rollback repeats its absorbing-state failure on fresh seeds and a new machine: excess after the
window +0.372, larger than during it.

## 1b. Cold start: a hole

| Window | Excess [95% CI] | Rejected |
|---|---|---|
| Blocks 0–39 (cold), A1 | +0.0438 [0.0329, 0.0554] | 383/400 |
| Blocks 0–39 (cold), soft-gate attack | +0.0453 [0.0337, 0.0577] | 391/400 |
| Blocks 40–79 (warm), A1 | +0.0152 [0.0125, 0.0181] | 398/400 |

Cold minus warm: +0.0286 [0.0184, 0.0395], p = 0.002. **Decision (rule 1b): a hole. It is fixed in
Phase 2.**

Mechanism, from the records (all 10 seeds):
1. The gates accept 1–4 poisoned blocks, all among the first five blocks. The cause is the first
   three blocks: whatever their verdict, they seed the running references ḡ₁ and ḡ₂
   (`GateController.update_clean`, `n_accepted < 3`). With poisoned statistics as references, the
   normalized G1 and G2 statistics become lenient.
2. The excess appears after the first consolidation: about 0.007 in blocks 0–9 against 0.05–0.06 in
   blocks 10–39.

The second point exposes a **structural weakness of the consolidation rule**. With the normalized
mean (18), the weights are γ_b / Σγ. When the other blocks of a period are rejected (γ ≈ 0), the
single accepted block carries the *whole* mean, and β = η · min(1, Σγ) ≈ η. One leak per period then
moves the slow level as far as a fully accepted period would; only the clip κ limits it. The
paper's argument that "a leaked block owns about 1/C of the average" holds only when most of the
period is accepted.

Fixes, calibrated on seeds 0–2 and tested on fresh seeds 30–34 in Phase 2:
- **F1, "rejected blocks vote for the memory":** β = η · Σγ / |B|. A rejected block counts as a
  vote for the current slow state. The update stays a convex combination (Lemma 1 holds), and one
  leak moves the level by at most 1/|B| of a full step, so the 1/C share holds again under any
  verdicts.
- **F2:** the gate references are seeded only by blocks the gates accept, against the neutral prior
  ḡ = 1. There is no forced acceptance of the first blocks.

## 1c. Ratchet: no effect

In blocks 10–49 the exact-gate attacker had all 400 perturbations accepted, at a mean scale of 0.45
of a 10 dB budget. The burst at 0 dB in blocks 50–89 then cost +0.0186 against +0.0161 without the
ratchet. The difference is −0.0041 [−0.0082, +0.0001]: not larger, and if anything smaller.
**Decision (rule 1c): no hole.** Accepted small perturbations do not move the gate references far
enough for a later burst to pass.

## 1d / 1e. Model-based receivers

| Receiver | Clean SER | Window SER (A1) | Excess A1 | Excess, channel spoof |
|---|---|---|---|---|
| ML, LS CSI (= K-best, K = 16) | **0.0053** | 0.0880 | +0.083 | – |
| ML + guard | 0.0053 | 0.0593 | +0.054 | +0.725 |
| MMSE-SIC | 0.0092 | 0.1729 | +0.164 | – |
| LMMSE | 0.0477 | 0.3766 | +0.329 | +0.884 |
| LMMSE + guard | 0.0477 | 0.2732 | +0.226 | +0.684 |
| **Citadel-Rx** | 0.0124 | **0.0269** | **+0.0144** | **+0.0228** |
| Perfect CSI: ML / MMSE-SIC / LMMSE | 0.0055 / 0.0096 / 0.0512 | | | |

**The guard is captured.** After 10 consecutive rejections it re-bases onto the current block, i.e.
onto the poisoned estimate, and from then on accepts the attack. The block patterns are
`RRRRRRRRRB` followed by accepted blocks; rejection is 0.42 under A1 and 0.25 under the spoof.

This is the paper's principle seen from the other side: a check without a protected memory either
locks the receiver (no re-base) or is captured by it (re-base). Because the guard as built is the
weaker of the reasonable designs, Phase 2 adds two stronger ones:
- **No re-base.**
- **CRC-verified re-base:** accept the new estimate only if its decisions pass at least as many
  CRCs as those of the protected estimate. This is the paper's principle applied to a model-based
  receiver.

**Decision (rule 1d):** under these attacks Citadel-Rx has the lowest window SER of every receiver
tested. The paired difference against ML + guard is −0.0325 [−0.0444, −0.0207]. On clean blocks, ML
with LS CSI is better (0.0053 against 0.0124). Its A1 excess comes from a perturbation crafted on the
online DeepSIC surrogate, not against ML; a spoof aimed at the LS estimate costs ML + guard +0.725.

## 1f. 16-QAM at the reference width (1024 units)

Citadel-Rx's clean SER is 0.102 against 0.0083 for LMMSE and 0.0001 for K-best, and it falsely
rejects 96% of clean blocks. **Decision (rule 1f): the narrow network was not the cause.** 16-QAM
stays a limitation of the plain backbone and is re-tested with the channel-conditioned backbone.

## 1R. Regime scan (calibration seeds 0–2, clean)

| Regime | Online DeepSIC | Citadel-Rx | Frozen | ML (LS) | r = ML / best adapting, blocks 50–99 |
|---|---|---|---|---|---|
| R0 SED | 0.0327 | 0.0137 | 0.0347 | 0.0062 | 0.45 |
| R1 complex Gauss–Markov | 0.0200 | 0.0243 | 0.999 | 0.0054 | 0.29 |
| R2 + 3-bit ADC | 0.0592 | 0.0837 | 0.999 | 0.0275 | 0.46 |
| R3 + saturation 0.7 | 0.0385 | 0.0468 | 0.999 | 0.0257 | 0.67 |
| R4 + IQ imbalance | 0.0208 | 0.0306 | 0.999 | 0.0166 | 0.80 |
| R5 + 32 pilots | 0.0285 | 0.0907 | 0.999 | 0.0077 | 0.27 |

(SER over blocks 50–99. Citadel-Rx's clean false rejection is 0 in R0–R4 and 0.025 in R5.)

**Decision (rule 1R): no regime reaches r ≥ 1.25.** Phase 2 introduces the channel-conditioned
backbone and repeats the scan with it.

The scan also shows two things:
- A pre-trained plain DeepSIC is useless on a channel it has not seen (SER 0.999).
- Citadel-Rx's anchoring slows adaptation from such a start (R1: 0.0690 against 0.0427 for online
  DeepSIC over blocks 5–99).

The backbone must carry the channel as an input, so that pre-training across channels gives a usable
starting point.

## Consequences for Phase 2

1. **Channel-conditioned DeepSIC:** each module also receives the LMMSE estimate computed from the
   block's pilots. The white-box attack differentiates through the LS estimate, so poisoning the
   pilots also moves the conditioning.
2. **Regime scan repeated** with this backbone, with harsher regimes added (2-bit ADC, saturation at
   0.4, combined impairments). The same rule picks the main regime.
3. **Fixes F1 and F2:** calibrated on seeds 0–2 and tested on fresh seeds 30–34 (cold start and
   warm A1).
4. **Stronger model-based guards:** no re-base and CRC-verified re-base, on test seeds 20–29.
