# Phase 4: the bug fixes, verified conditioning, and the large-scale grid

Why: `docs/v3/PHASE3_REPORT.md`. Job list: `scripts/v3/phases.py::phase4`. Analysis:
`scripts/v3/analyze.py --phase 4`.

## New code (all off by default; the stored records still reproduce bit for bit)

| Item | Setting | What |
|---|---|---|
| NaN-safe consolidation | `citadel.gamma_floor=1e-6` | Verdicts below the floor count as exact rejections; the gated mean is formed from normalised float64 weights. A non-finite mean is never written into a level (this guard is always on). |
| CRC-8 scrambling | `frame.crc_scramble=true` | Per-user NR Gold sequence (TS 38.211 Sec. 5.2.1, c_init = (u + 1) 2^15 + 1; checked bit for bit against Sionna). A constant output then passes only at the CRC-8 false-pass rate 2^-8. |
| Verified conditioning | `receiver.cond_source=verified` | The deep receiver holds an internal Citadel-LS (LMMSE decisions). It is conditioned on the block's LS estimate if that verifies against the protected memory, else on the anchor; it does not train on pilots the verifier rejects; Citadel-Rx's references use the verified estimate too. |
| Two-sided noise test | `receiver.guard_two_sided=true` | Also rejects pilots whose residual is below the lower chi-square quantile (an attacker that cancels front-end distortion). |

Every Phase 4 run uses both fixes, except the coded UMi scene, which already scrambles its LDPC
code blocks and takes only the γ floor.

## Experiments

| Group | Seeds | Runs | Question |
|---|---|---|---|
| 4X | 20–29 | The 47 Phase 3 runs hit by the bugs: conditioned Citadel-Rx in R4 and R7 under A1 and the LS attack; Citadel-Rx on SED under the LS attack. Fixes on, new clean twins. | What do these cells show without the bugs? |
| 4U | 10–14 (the UMi drops) | Coded 5G scene of the second campaign: NR LDPC, scrambled, rank-1 attacker at 35, 75 and 150 m at a user's maximum power. Citadel-Rx (fixed), and conditioned Citadel-Rx with verified conditioning and online DeepSIC (pre-training on block 0 of the drop, as in the second campaign). | Was the published failure the bug, and does conditioning fix the phase-rotation problem the paper guessed at? |
| 4V | 20–29 | Main large-scale setting: R8 combined hardware, QPSK, 8 × 32. Receivers: conditioned Citadel-Rx with verified and with raw conditioning; online DeepSIC (cond.); Citadel-LS (K-best); K-best unprotected; K-best + guard with CRC-verified re-base; K-best + guard without re-base. Cells: A1 (deep), the LS attack, the gate-aware LS attack (guarded), the spoof, the spoof during a redraw. | Does the deep instance, where it wins on clean blocks, stay protected under attack? |
| 4T | 20–29 | Citadel-LS and the ML guard (CRC re-base), one-sided and two-sided noise test, R4, gate-aware LS attack | Does the two-sided test help? |

## Decision rules (fixed before any Phase 4 run)

| Group | Rule |
|---|---|
| 4X | If Citadel-Rx's excess in the 30 blocks after the window is below 0.01 in every 4X cell, the Phase 3 failure to recover was the bug. The cells replace the Phase 3 ones. |
| 4U | The coded-scene statement of the paper is replaced by these numbers, whatever they show. If verified-conditioned Citadel-Rx has a clean BLER at or below LMMSE's (paired, 95% interval of the difference not above zero), the phase-rotation explanation is supported; otherwise it is withdrawn. |
| 4V | **Verified-conditioned Citadel-Rx is the protected deep receiver of the large-scale setting** if all three hold: (i) its clean SER is below K-best's (paired, 95% interval below zero); (ii) under every attack cell its window SER is not worse than the K-best + CRC-verified guard's by more than 0.005 (upper 90% bound); (iii) under the spoof its window SER is below raw-conditioned Citadel-Rx's (95% interval below zero). |
| 4T | The two-sided test is adopted for later phases if it lowers the window SER under the gate-aware LS attack (95% interval below zero) for both receivers, at a clean false rejection ≤ 2%. |

## Commands

See the message in the session (one PowerShell block).
