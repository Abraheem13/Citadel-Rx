# Roadmap: Citadel-Rx from 5.5/10 to 9/10

Owner: A. Rashid. Started 2026-11-12.

Compute is one workstation with an RTX 5080. Every experiment runs there; analysis and code
changes happen in review sessions. Each phase ends at a review gate. Nothing from a phase is
used until its gate has passed.

## 0. Where the paper stands and why

Current estimate: 5.5/10 for IEEE TWC. Four things hold it there:

| # | Weakness | Evidence in this repository |
|---|---|---|
| W1 | The main channel is real-valued and deterministic, and it is the same for every seed. Pre-training sees block 0 of the test channel. | `channels/base.py::_synthetic` (cosine: no RNG); `eval/runner.py::pretraining_blocks` (static = `H_mean`) |
| W2 | ML detection with the LS estimate beats every deep receiver on clean blocks (0.0066 against 0.0159), so it is unclear why the deep receiver needs protecting. | `paper/numbers.tex` `p1.ml.wb0.clean` |
| W3 | The adaptive attacks never search the acceptance boundary: every one runs at full budget, and 0/200 blocks are accepted while the surrogate predicts acceptance. A4 cannot degrade its references. A3* ignores `theta_bad`. The gate state can be written by the attacker. | `attacks/pilot_poisoning.py::_soft_ctx`, `_soft_gamma`; `gates/physics.py:199` (`n_accepted < 3` always accepts) |
| W4 | The method fails in the only realistic setting, the coded 3GPP link, and at 16-QAM. The theory bounds weight displacement, not error rate. | Tables X and XI, Fig. 5; Theorem 1 |

A 9/10 needs four things:

1. A seed-varying complex channel where an adapting deep receiver beats the model-based receivers.
2. An attacker that finds the gates' acceptance boundary.
3. A working coded 3GPP link.
4. A theorem that predicts the measured excess error rate.

All on held-out seeds, with pre-registered settings and equivalence statistics.

## 1. Protocol rules (they apply to every phase)

1. **Seeds.** Seeds 0–2 are for calibration only. The new test seeds are 20–29 (10 seeds on every
   cell that a claim rests on). Seeds 10–19 are retired: they were seen in two revision rounds.
2. **Pre-registration.** Every setting is frozen by a rule committed before its test runs, in
   `configs/v3_frozen_*.json`, written by a script and never by hand. A change after a test run is
   disclosed and re-tested on fresh seeds 30–34.
3. **Matched clean twins.** Every attacked run has a clean twin from the same machine (the existing
   `JT` mechanism).
4. **Primary endpoint.** Window excess SER (attacked minus clean twin) of white-box A1 at SIR 0 dB on
   the new main channel. Everything else is secondary, with Holm families declared before the runs.
5. **"No difference" claims** use two one-sided tests (TOST) against a margin fixed in advance:
   0.005 SER. The phrase "not distinguishable" is no longer used.
6. **Absolute numbers.** Absolute window SER is reported next to excess SER in every table.
7. **Traceability.** Every number in the paper comes from `scripts/revision_numbers.py` (or its v3
   successor). Nothing is typed by hand.

## 2. Phases

Rough compute is in GPU-workstation hours. It assumes about 16 parallel single-threaded runs; Phase 0
measures the real throughput, and these estimates are rescaled afterwards.

### Phase 0: Setup, reproducibility and benchmark (≈ 2 h)

- Import the repository into the new GitHub repository with a clean history.
- Create the environment on the RTX 5080: PyTorch with CUDA 12.8 (Blackwell needs it) and Sionna 2.2.
- Run the unit tests.
- Reproduce one stored headline record (Citadel-Rx, seed 10, plus its clean twin) and compare it
  block by block. This tells us whether the new machine agrees with the old records.
- Benchmark one run on CPU and on GPU (`run.device=cuda`), alone and with N runs in parallel, to
  choose how the queue is scheduled.

**Gate:** tests pass; the reproduction matches (or the size of the difference is documented); the
throughput is known.

### Phase 1: Decisive cheap checks (≈ 15 h). These can change the story.

| ID | Experiment | Why |
|---|---|---|
| 1a | Frozen pre-trained DeepSIC with per-sub-block CRC selection against LMMSE | Under attack Citadel-Rx runs on its anchor in 99% of blocks. If this receiver matches it, the contribution changes. |
| 1b | Cold-start attack: A1 from block 0 (the gates accept the first three blocks, and the slow levels are not formed yet) | A real hole in the code |
| 1c | Ratchet attack: weak, accepted perturbations that inflate the gates' running statistics, followed by a strong burst | Attacks on the gate state are outside Theorem 1 |
| 1d | Tracked-CSI LMMSE and ML with a pilot-residual / noise-inflation test and fallback to the previous estimate | The strongest simple model-based defense. Citadel-Rx must beat it on window SER. |
| 1e | ML, K-best (K = 16) and MMSE-SIC, each with LS CSI and with perfect CSI | The missing model-based baselines |
| 1f | 16-QAM with the reference width (64 · 16 = 1024 hidden units) | The failure may come from the width cut |

Seeds 20–29, white-box A1 at SIR 0 dB, on the existing SED channel.

**Gate (decision point):**
- If 1a matches Citadel-Rx, the claim moves to settings where adaptation is needed (Phase 2), and
  the paper says so.
- If 1b or 1c succeeds, the gate warm-up and state updates are fixed (statistics seeded from
  pre-training, frozen on rejected blocks) before Phase 2.

### Phase 2: The channel and regime that make the paper (≈ 60 h)

- **New channel model `complex_gm`.** Complex Gauss–Markov fading around the SED mean, with a
  per-seed random draw and per-user phase, and f_D·T_b ∈ {0.01, 0.05}.
- **3GPP CDL-C (Sionna)** as the second family. COST2100 starts at a seed-dependent frame.
- **Ensemble pre-training.** About 64 channel draws that exclude every test draw.
- **The regime where adaptation pays.** Run all receivers, clean, on three regimes and pick the main
  one by a pre-registered rule (the largest clean gain of online DeepSIC over ML with LS CSI):
  - the tanh PA nonlinearity,
  - few pilots (N_p = 32),
  - phase noise plus IQ imbalance.
- **Frozen settings** for Citadel-Rx and the tuned baselines on seeds 0–2 in that regime.
- **Test grid on seeds 20–29:**
  - the headline cell (all receivers, clean and A1 at −10, 0, +10 dB, plus transfer),
  - the ablations K = 1, K = 2, no fallback, G2 only and the minimal core,
  - 1a and 1d.

**Gate:** an adapting deep receiver beats ML with LS CSI on clean blocks in the main regime, and
Citadel-Rx keeps that advantage under attack. If no regime gives a clean win, the paper is reframed
as "protecting test-time learners", and this decision is recorded here.

### Phase 3: Attacks that model the defense (≈ 80 h)

- **3a. Boundary search.** Per-block bisection of the perturbation scale (8 steps) over 4 PGD-restart
  directions, each candidate tried on an exact copy of the receiver. Report the most damaging
  accepted candidate. SIR −10, 0, +10 and +20 dB.
- **3b. Complete soft objective.** G1, G2 and G3, the tightening and the CRC selection, with C&W
  hinge margins per gate and a search over the trade-off constant.
- **3c. Adam unroll.** A truncated, checkpointed unroll of the victim's Adam, delta rule and
  proximal pull (instead of plain SGD steps).
- **3d. Corrected A4.** References recomputed on the perturbed block, 20–50 PGD steps, and a
  convergence check (objective against iteration).
- **3e. Directed A3*.** Maximize D_K toward `theta_bad` subject to acceptance; 1000 blocks; measure
  the harm after the attack ends.
- **3f. CRC forgery** under the "+data" threat model (CRC-consistent error patterns), or a narrowed
  threat model with justification.
- **3g. Sanity checks.**
  - Attack success rises with the budget.
  - The unbounded attack reaches 100%.
  - Transfer is weaker than white-box.
  - Surrogate acceptance agrees with the real acceptance.

**Gate:** the worst case over all attacks is reported as the security number. If it breaks the
defense, the gate is fixed and re-tested on seeds 30–34.

### Phase 4: The coded 3GPP link works (≈ 60 h)

- **Backbone input.** Add the LS channel estimate (or the LMMSE-equalized symbols) as extra inputs
  to the DeepSIC modules. This is the fix for per-block phase rotation, a hypothesis to be tested.
- **Pre-training** on a UMi drop ensemble that excludes the test drops.
- **Soft LLRs** from the posteriors into the LDPC decoder (replacing hard decisions with |LLR| = 3).
- **Finish or delete** `channels/sionna_pusch.py`.
- **Test** on UMi drops for seeds 20–29 at 35, 75 and 150 m and at two speeds (3 and 30 km/h):
  BLER and goodput.

**Gate:** Citadel-Rx's clean BLER is at or below LMMSE's, and its excess BLER under attack is below
that of every adapting baseline.

### Phase 5: Theory tied to harm (analysis, ≈ 5 h of compute)

- **Theorem (excess error rate).** With probability at least 1 − 2e^{−2 J_c t²}:

  excess window SER ≤ (1 − RR) · U(ξ + t) + RR · Δ_anchor,

  where Δ_anchor is bounded through Eq. (33) by a measured local Lipschitz constant of the anchor's
  SER. Every term is measurable.
- Plot the bound against the measured excess for every attack in Phases 1–4.
- Check the i.i.d. sub-block error assumption on the records (the paper admits it was not checked).
- Keep Theorem 1(i) as a lemma.

### Phase 6: Statistics, simplification and writing (≈ 10 h of compute)

- TOST, the endpoint hierarchy and Holm families; 10 seeds everywhere a claim rests on them.
- **Minimal method.** One slow level, G2 against the protected memory, anchor fallback and CRC
  selection. Any component the ablations do not support goes to the appendix.
- **Rewrite.**
  - Lead with the principle and the CRC-Rollback failure.
  - An abstract with four numbers.
  - Three contributions.
  - An honest limitations section.
  - The real co-authors.
  - Choose between TIFS and TWC.
- Fix the "Citradel" typo in the repository URL; record the frozen environment in a lock file.

## 3. Working loop for every phase

1. **Review session (code).** Implement the phase, run the unit tests and a tiny smoke run here,
   then push to `main` with a `phaseN` tag.
2. **Workstation.** `git pull`, then `python scripts/v3/run_phase.py --phase N`. The run is
   resumable and pushes results every 45 minutes to the branch `results/phaseN`.
3. **Review session (analysis).** Check every record:
   - completeness;
   - the twin check: identical before the attack window;
   - NaN or diverged runs;
   - that the gate criteria hold.
   Then write `docs/v3/PHASE_N_REPORT.md` and decide whether to move on.

## 4. Status

| Phase | Code | Runs | Report | Gate |
|---|---|---|---|---|
| 0 | done (pushed) | on ws5080 | – | – |
| 1 | done (pushed) | – | – | – |
| 2 | – | – | – | – |
| 3 | – | – | – | – |
| 4 | – | – | – | – |
| 5 | – | – | – | – |
| 6 | – | – | – | – |
