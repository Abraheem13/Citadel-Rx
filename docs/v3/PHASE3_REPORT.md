# Phase 3 report

Records: `results/v3/p3/`, `results/v3/clean_ws5080/`, machine ws5080, commits `bef7a7c`–`81291b5`;
1128 of 1128 runs, 0 failed. Tables: `docs/v3/PHASE3_TABLES.md`. Integrity: 670 pairs, 0 problems.
Test seeds 20–29; 3L on calibration seeds 0–2.

## 1. Two bugs (found in this review)

**NaN slow levels.** When a whole consolidation period is rejected with extreme statistics (the LS
attack drives G3 to 10²–10³), the soft verdicts underflow (γ ≈ 1e-272). The gated mean then
multiplies float32 weights by these values, which underflow to 0, and divides by a sum that rounds
to 0 in float32: 0/0 = NaN. The anchor becomes NaN and the receiver emits a constant symbol.

**A constant output passes every CRC-8 check.** All-zero decided bits carry a zero CRC, so G2 and the
CRC selection see a broken detector as perfect (pass rate 1.000). NR scrambling exists to prevent
this; the LDPC path already had it fixed, the CRC-8 sub-block framing never did.

**Affected records:**

| Set | Affected | Unaffected |
|---|---|---|
| v3 | 47: Citadel-Rx under A1 and the LS attack (`v3p3D_R4/R7_citadel_cc__a1/ls`, `v3p3S_citadel__ls`); the NaN runs and the constant-output runs are the same 47 | all other 2,000 records |
| Second campaign | 28: **every Citadel-Rx record of the coded 5G/UMi scene** (`rev2_umi_ldpc*`), including clean twins (`rev_clean_pool7/8`) | – |

The published statement that "Citadel-Rx fails in a coded 5G link over 3GPP UMi" therefore rests at
least partly on this bug, not only on the phase-rotation explanation the paper gives. These records
are excluded from every conclusion below and are re-run in Phase 4 with the fix.

## 2. Large-scale scan (3L): the deep receiver's regime

8 × 32, clean, K-best (K = 32) as the reference (ML is infeasible). SER over the second half of the
run, geometric mean over seeds 0–2:

| Setting | Online (cond.) | Citadel-Rx (cond.) | K-best | MMSE-SIC | LMMSE | r |
|---|---|---|---|---|---|---|
| R8 combined hardware, QPSK | 0.0017 | **0.0004** | 0.0008 | 0.0008 | 0.0013 | **1.75** |
| R7 saturation, QPSK | 0.0002 | 0.0001 | 0.0001 | 0.0001 | 0.0001 | 1.38 |
| R1 complex, QPSK | ≈ 0 | ≈ 0 | ≈ 0 | ≈ 0 | ≈ 0 | – |
| R1, 16-QAM | 0.0005 | 0.0022 | ≈ 0 | ≈ 0 | ≈ 0 | 0.02 |
| R7, 16-QAM | 0.439 | 0.831 | 0.396 | 0.404 | 0.412 | 0.90 |
| R8, 16-QAM | 0.700 | 0.961 | 0.610 | 0.622 | 0.638 | 0.87 |

**Decision (rule 3L): the main large-scale setting is R8 QPSK at 8 × 32 (r = 1.75).** It is the first
setting in this study where an adapting deep receiver beats the best feasible model-based detector
on clean blocks.
- At 16-QAM every adapting receiver fails; this stays a limitation.
- Citadel-Rx's clean false rejection is 0.40 in R1 16-QAM.

## 3. The capture–lock grid (3D, 3S)

### R4 (IQ imbalance, CRC-verifiable): window SER under attack, and the redraw

| Receiver | Clean | Gate-aware LS attack | LS attack | Spoof | Spoof during redraw | After a legitimate redraw (clean) |
|---|---|---|---|---|---|---|
| **Citadel-LS** | **0.0369** | 0.0713 | 0.0593 | **0.0580** | 0.3751 | 0.0562 |
| ML + CRC-verified guard | 0.0394 | **0.0598** | 0.0627 | 0.0614 | **0.2594** | **0.0440** |
| ML + guard, no re-base | 0.0394 | 0.0598 | 0.0627 | 0.0614 | 0.7242 | 0.3329 (locks) |
| ML + guard, count re-base | 0.0394 | 0.4709 (captured) | 0.6185 | 0.7207 | 0.3662 | 0.1070 |
| ML, unprotected | 0.0394 | – | 0.7812 | 0.9194 | 0.3022 | 0.0440 |
| Online DeepSIC (cond.) | 0.0521 | – | 0.7739 | 0.8645 | 0.3525 | 0.0944 |
| Citadel-Rx (cond.) | 0.0572 | (bug) | (bug) | 0.8737 | 0.3382 | 0.0972 |

**Rule (Citadel-LS escapes the dichotomy in R4):**

| Condition | Outcome |
|---|---|
| (a) not worse than any single-state guard by > 0.005 | Spoof: −0.0034 [−0.009, +0.001], **passes**. Gate-aware LS attack: +0.0114 [−0.005, +0.040], 90% upper bound +0.035, **fails**. |
| (b) lower than a re-basing guard under the gate-aware attack | −0.40 [−0.49, −0.31] vs count re-base, **passes** |
| (c) beats no-re-base under spoof during redraw | −0.349, **passes** |
| (c) after the redraw, not worse than unprotected ML by > 0.005 | +0.0122 [+0.002, +0.032], **fails** |

**Decision: Citadel-LS does not escape by the pre-registered criteria.** What the data do show:
1. **The decisive ingredient is verifying acceptance against a protected state, not the number of
   memory rates.** With a calibrated noise reference, the single-state CRC-verified guard holds under
   every lasting attack in R4 (rejection 0.998–1.000), follows a legitimate redraw at no cost
   (0.0440, as unprotected ML), and has the lowest SER in the hardest cell, the spoof during a redraw
   (0.259).
2. **Capture comes from accepting by statistical tests alone.**
   - The count re-base guard re-bases after 10 rejections: captured (0.47–0.72).
   - In Phase 2 the CRC-verified guard was captured on SED: it used the nominal noise reference, and
     each rare CRC-verified leak re-based its noise reference onto the attack, after which blocks
     passed the statistical tests without a CRC check.
3. **Never re-basing locks:** clean SER 0.33 after a redraw in R4, false rejection 0.53.
4. **Multi-rate memory helps where leaks occur.** On SED, Citadel-LS beats the CRC-verified guard:
   - gate-aware LS attack: 0.0124 against 0.0198, difference −0.0073 [−0.012, −0.003];
   - LS attack: 0.0184 against 0.0353;
   - spoof during redraw: 0.160 against 0.195.

   In R4 it costs a little after a legitimate change: +0.012, because the anchor lags by up to one
   period.

### R7 (saturation, not verifiable for two users)

- Citadel-LS falsely rejects 15.8% of clean blocks.
- The gate-aware attack is accepted on 32% of blocks against Citadel-LS and 22% against the guards.

As expected, CRC verification loses its resolution there for every receiver that relies on it.

### The deep receiver with channel conditioning: a new hole

Under the channel-estimate spoof, conditioned Citadel-Rx rejects only 11–13% of attacked blocks and
reaches window SER 0.87 (R4) and 0.86 (R7). A1 and LS-attack numbers are excluded (bug).

The conditioning feeds the poisoned LS estimate into every data symbol, and into the anchor's
fallback detection too. The LMMSE reference sees the same poisoned estimate, so G1/G2 see a
consistent picture. **Protecting the weights does not protect an input path.**

The fix follows from point 1 above: condition the network on the **verified** channel estimate
(Citadel-LS's accepted estimate or its anchor), not on the raw one.

## 4. What the paper can now claim (to be confirmed in Phase 4)

1. Every test-time learner at the PHY tested here is broken by pilot poisoning when unprotected (SER
   0.7–0.9): LS tracking, online DeepSIC, channel-conditioned DeepSIC.
2. Defenses fail in two ways:
   - **captured**, when acceptance relies on statistics the attacker can satisfy, or a reference it
     can move;
   - **locked**, when nothing can re-base.
3. **Verification against a protected state at the decision level (CRC)** avoids both in the
   verifiable regime. Multi-rate memory further limits the harm of leaks, at a small lag cost.
4. Limits:
   - CRC verification loses resolution when a user's clean pass rate saturates near zero (R7, 16-QAM);
   - input paths (conditioning) must be verified too;
   - the cold start remains.

## 5. Phase 4

1. **Fixes, then re-runs of everything the bugs touched:**
   - NaN-safe consolidation (always on), with a floor on γ;
   - per-user scrambling of the CRC-8 framing (no constant-output pass);
   - re-run of the 47 v3 records and of the coded UMi scene.
2. **Verified conditioning for the deep instance,** tested in the main large-scale setting (R8, QPSK,
   8 × 32) against K-best with and without verification, under A1, the LS attack, the spoof and the
   spoof during a redraw.
3. **A two-sided noise test** (Phase 3 observation 4).
