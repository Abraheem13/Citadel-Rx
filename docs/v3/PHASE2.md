# Phase 2: the channel-conditioned backbone, the cold-start fix, and stronger model-based guards

Plan: `docs/ROADMAP_9of10.md`. Why this phase: `docs/v3/PHASE1_REPORT.md`. Job list:
`scripts/v3/phases.py::phase2`. Settings are frozen by `scripts/v3/freeze.py`. Analysis:
`scripts/v3/analyze.py --phase 2`.

The phase runs in three stages from one command. The calibration stage runs on seeds 0–2. A frozen
rule then picks the fix. The test stage runs on seeds 30–34 (fix) and 20–29 (guards).

## New code

| Item | Where | What |
|---|---|---|
| Channel-conditioned DeepSIC | `receivers/conditioning.py`, `receiver.cond=lmmse` | Each module also receives the LMMSE estimate made with the block's own LS channel estimate (2N + 2U inputs). Pre-training across channel draws then gives a usable start on unseen channels. |
| Attacks through the conditioning | `attacks/pilot_poisoning.py` | The white-box attacker differentiates through the LS estimate (`ls_torch`, `cond_features_torch`): poisoning the pilots also moves the conditioning of every data symbol. |
| F1, rejected blocks vote for the memory | `citadel.consol_mean=vote` | β = η · Σγ / \|B\|: one accepted block among \|B\| moves a slow level by at most 1/\|B\| of a full step, whatever the other verdicts. |
| F2, references seeded only by accepted blocks | `citadel.gate_warmup=prior` | No forced acceptance of the first three blocks. |
| Guards without re-base / with CRC-verified re-base | `receiver.guard_rebase=never|crc` | `crc`: a block that fails the pilot tests is accepted only if its decisions pass at least as many CRCs as those of the last accepted estimate. |

## Experiments

| Group | Stage | Seeds | Runs | Question |
|---|---|---|---|---|
| 2R | cal | 0–2 | 8 regimes × {online, Citadel-Rx, frozen} with the conditioned backbone, + LMMSE, ML, K-best; clean | Where does an adapting deep receiver beat ML with LS CSI? |
| 2F | cal | 0–2 | Citadel-Rx base / F1 / F2 / F1+F2 under A1 at SIR 0 dB, warm (random window) and cold (blocks 0–39), clean twins | Which fix closes the cold-start hole at no clean cost? |
| 2Ft | test | **30–34** (fresh) | The frozen fix against base, warm and cold | Does the fix hold on seeds that played no part in choosing it? |
| 2G | test | 20–29 | ML and LMMSE guards without re-base and with CRC-verified re-base, under A1 and the channel spoof; a legitimate redraw at block 50 for Citadel-Rx, online DeepSIC, ML and the three ML guards (clean) | Is there a model-based receiver that matches Citadel-Rx under attack, and what does each guard cost when the channel really changes? |

Regimes (all on the seed-varying complex channel, f_D·T_b = 0.01, K = 1, pre-training on 32 draws
whose channels are disjoint from every test channel):

| Regime | Setting |
|---|---|
| R1 | linear front-end |
| R2 | 3-bit ADC |
| R3 | saturation at 0.7 × rms |
| R4 | IQ imbalance |
| R5 | 32 pilot symbols |
| R6 | 2-bit ADC |
| R7 | saturation at 0.4 × rms |
| R8 | 3-bit ADC + saturation 0.7 + IQ imbalance |

## Decision rules (fixed before any Phase 2 run)

| Result | Consequence |
|---|---|
| 2R: largest r = SER(ML, LS) / min(SER(online, conditioned), SER(Citadel-Rx, conditioned)) over blocks 50–99, geometric mean over seeds 0–2, is ≥ 1.25 | That regime is the main setting of the paper. Phase 3 (attacks) and the headline grid run there on test seeds 20–29. |
| 2R: largest r < 1.25 | No tested regime makes an adapting deep receiver better than ML on clean blocks. The paper is framed as protecting a test-time learner: the principle, the theory and the attacks hold for any adapting receiver, including the CRC-verified model-based guard. The main setting is still the regime with the largest r, and the paper states that ML is the better clean detector there. |
| 2F (`freeze.py`) | Admissible: clean false rejection ≤ 2%. Chosen: the lowest mean of (warm excess, cold excess); within 0.001 of the lowest, the simplest in the order base, F2, F1, F1+F2. |
| 2Ft: adopted | The cold excess of the fix minus that of base has its 95% interval below zero, and the warm excess of the fix exceeds base's by less than 0.005 (upper 90% bound). The fix then becomes part of the receiver for every later phase. |
| 2Ft: not adopted | The cold-start hole stays a stated limitation, with its size. |
| 2G: window SER of the ML guard with CRC-verified re-base is equivalent to or below Citadel-Rx's under A1 *and* the spoof | That guard is the main competitor on SED, and it is reported as a model-based instance of the paper's principle. Citadel-Rx's claim then rests on the regimes where adaptation pays (2R). |
| 2G: otherwise | Citadel-Rx keeps the lowest window SER on SED under attack against every guard tested. |

## Commands (Windows PowerShell)

One paste runs everything: the calibration stage, the freeze, then the test stage. Results are
pushed every hour and at the end. It takes about 5–6 hours. See the message in the session for the
exact block.

## Review (done in the review session)

```bash
python scripts/v3/analyze.py --phase 2
```

This writes `docs/v3/PHASE2_TABLES.md`. The decisions are recorded in `docs/v3/PHASE2_REPORT.md`.
