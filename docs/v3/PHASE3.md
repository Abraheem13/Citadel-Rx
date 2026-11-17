# Phase 3: the capture–lock dichotomy, Citadel-LS, and the large-scale check

Direction (decided after Phase 2, `docs/v3/PHASE2_REPORT.md`): **principle first, plus a large-scale
check.** The contribution is the principle: consolidate into persistent memory only what verifies
against that memory, over several rates. It is shown with two learners:
- the per-block LS channel estimate of an ML detector (**Citadel-LS**, new);
- the deep receiver (Citadel-Rx).

Job list: `scripts/v3/phases.py::phase3`. Analysis: `scripts/v3/analyze.py --phase 3`.

## New code

| Item | Where |
|---|---|
| Citadel-LS: fast LS estimate, slow levels H2 (C = 8) and H3 (C = 32) consolidated by the vote rule with a clip (10% … 50% of the level's norm, `citadel.ls_clip_frac`, default 0.5); gates relative to the protected memory (noise inflation against a reference that only consolidation moves; a **per-user** CRC test against the anchor's decisions); fallback to the anchor; CRC selection over (fast, anchor, H3) | `citadel_rx/receivers/modelbased.py::CitadelLS`, `receiver.type=citadel_ls` |
| White-box attack on LS-based receivers: PGD through the LS estimate and LMMSE posteriors. Gate-aware form (`attack.soft_gate`): loss × soft acceptance (noise test against the victim's reference, soft per-sub-block CRC test against the victim's protected estimate) | `attacks/pilot_poisoning.py::_ls_attack`, `attack.type=ls` |
| Redraw of the complex channel: a new drop (new line-of-sight phases, new scattering) | `channels/base.py` |

## Experiments (test seeds 20–29 unless stated)

**3D, dichotomy grid.** Run in R4 (IQ imbalance) and R7 (saturation at 0.4 × rms), both on the
seed-varying complex channel. Receivers:
- Citadel-Rx and online DeepSIC, both channel-conditioned;
- Citadel-LS (ML);
- unprotected ML;
- ML + guard with count re-base, no re-base, or CRC-verified re-base.

| Cell | What |
|---|---|
| `ls` | white-box LS attack, SIR 0 dB, random window |
| `lssg` | the gate-aware LS attack (guarded receivers) |
| `spoof` | channel-estimate spoof S_p Z^T, SIR 0 dB |
| `spoofredraw` | legitimate redraw at block 50 and the spoof at SIR 10 dB on blocks 40–89; its clean twin is the redraw alone |
| `a1` | white-box A1 through the conditioning (deep receivers) |

**3S, same dichotomy on SED.** Citadel-LS, ML guards without re-base and with CRC-verified re-base,
and Citadel-Rx, under `ls`, `lssg` and `spoofredraw`; Citadel-LS also under A1 and the spoof.

**3L, large-scale scan.** Calibration seeds 0–2, clean, 60 blocks, 8 × 32. Three regimes (R1, R7,
R8) × {QPSK at 10 dB, 16-QAM at 20 dB with width 1024}. Receivers: online, Citadel-Rx and frozen
(conditioned), K-best (K = 32), MMSE-SIC and LMMSE. ML is infeasible (4⁸ and 16⁸ hypotheses). For
cost, pre-training is capped at 16 draws and 100 epochs.

## Disclosures (decisions made before any Phase 3 test run)

1. **Per-user CRC test in Citadel-LS.** A smoke run on calibration seed 0 (R7, gate-aware LS attack)
   showed that a CRC test pooled over the users is passed by an attacker that concentrates its
   damage on one or two users: the pooled pass rate went from 0.44 to 0.29 while the vector SER went
   from 0.19 to 0.66. The test is therefore per user.
2. **R4 added to R7.** The same smoke run showed that in R7 two users have a per-symbol error of
   about 0.17 *on clean blocks*. Their 32-symbol CRC pass rate is about 0.005, so a CRC test there
   carries no information about that user. The design rule (27) needs a pass rate that is not
   saturated at zero.
   - **Verifiability condition**, computed from the Phase 2 calibration records of ML with LS CSI:
     every user passes at least half of its CRCs on clean blocks, min_u (1 − p_u)^32 ≥ 0.5.
   - **Regimes that meet it:** R1 (0.87), R2 (0.61), R4 (0.69) and R5 (0.82).
   - **Regimes that do not:** R3 (0.37), R6 (0.03), R7 (0.12) and R8 (0.05).
   - The grid runs in R7 (the Phase 2 rule) **and** in R4, the regime with the largest r among those
     that meet the condition. R7 documents what happens without it.

3. **Offline noise calibration of every guarded model-based receiver.** The same smoke run, in R4,
   showed that IQ imbalance raises the clean LS residual to about 1.6× the nominal noise. The noise
   test then rejected every clean block, so Citadel-LS never formed a memory. The gate-aware attacker
   sent pilots that fit the linear model better (0.5×), and those were accepted as the first memory.
   - **Fix:** the initial noise reference is the receiver's own clean residual level, measured
     offline on its pre-training draws at the configured SNR (`receiver.guard_noise_ref=calibrated`),
     as a deployed receiver would be calibrated.
   - **Scope:** it applies to Citadel-LS and to all three ML guards in Phase 3 alike. The Phase 1/2
     guard records used the nominal reference and stay as they are.
   - After the fix (calibration seed 0, R4, gate-aware attack on blocks 10–17), clean blocks sit at
     0.95–1.02 of the reference and every attacked block is rejected by Citadel-LS and by the
     CRC-verified guard.
4. **Observation, not acted on in this phase.** Under the gate-aware attack the pilot residual falls
   to about 0.45 of the clean level: the attacker's pilots fit the linear model too well. A two-sided
   noise test would flag this. It is a Phase 4 candidate, not part of any Phase 3 receiver.

## Decision rules (fixed before any Phase 3 test run)

**Citadel-LS escapes the capture–lock dichotomy in a regime** if all of (a)–(c) hold:
- **(a) No worse under attack:** under `lssg` and `spoof`, Citadel-LS's window SER is not worse than
  any single-state guard's by more than 0.005 (upper 90% bound of the paired difference < 0.005).
- **(b) Not captured:** under `lssg` it is lower than that of at least one re-basing guard (count or
  CRC; 95% interval below zero).
- **(c) Does not lock:**
  - under `spoofredraw` its window SER is lower than that of the guard that never re-bases (95%
    interval below zero);
  - after the redraw alone (clean twins), it is not worse than unprotected ML by more than 0.005
    (upper 90% bound).

| Result | Consequence |
|---|---|
| Escapes in R4 | Citadel-LS is the lead instance of the paper, and R4 is its main setting. SED and R7 are reported alongside. |
| Fails in R4 | The principle is reported with the condition that failed. The paper does not claim the escape for that learner. |
| R7 | Reported as the limit of CRC verification at saturated pass rates, for every CRC-verified receiver (Citadel-Rx's G2 included), with per-user pass rates. |
| 3L: r = SER(K-best) / min(online, Citadel-Rx), both conditioned, second half of the run, ≥ 1.25 in some setting | That setting is the deep instance's main large-scale setting in Phase 4 (adaptive attacks). |
| 3L: r < 1.25 everywhere | The deep instance is reported as a protected learner only; Citadel-LS leads. |

## Review

```bash
python scripts/v3/analyze.py --phase 3
```

This writes `docs/v3/PHASE3_TABLES.md`; the decisions go to `docs/v3/PHASE3_REPORT.md`.
