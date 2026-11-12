# Research notes — what it takes to land Citadel-Rx in a ≥10-IF transactions venue

Status: 24 Oct 2026. These notes drive the code design. Everything here was
checked against the proposal (v1.0, 20 Oct 2026), the public reference
codebases, and the current literature reachable from this environment.
Items I could not verify at the primary source are flagged `[UNVERIFIED]`.

## 1. The bar at IEEE TWC / JSAC / TIFS / TNNLS (2025–2026)

TWC's own policy page says the most common decision is *reject*, that the
EIC screens for "little novelty, well-studied topics, weak model
assumptions" before papers reach reviewers, and that it aims to be
"extremely selective". Review-time estimates from third parties are ~7
months, no published acceptance rate. Reviewer patterns that get deep-receiver
papers rejected (from editorial guidelines + author reports; treat as
qualitative):

1. **Incremental architecture, no theory.** "We added X to DeepSIC and it
   gained 0.8 dB" is a conference paper. A transactions paper needs a
   *mechanism with a provable property* and experiments that test the
   property, not only the headline number.
2. **Outdated or weak baselines.** For online deep receivers in 2026 the
   bar is: online DeepSIC (TWC 2021), Meta-DeepSIC (TWC 2023), modular
   drift-detection receiver (TWC 2025), modular Bayesian single-step
   adaptation (2025), plus a model-based LMMSE floor. Missing any of
   these is a reviewer's first comment.
3. **Single synthetic channel.** Need ≥3 channel families, at least one
   with real/measured or standardized geometry (COST2100 for exact
   comparability with the attack paper; 3GPP CDL via Sionna; DeepMIMO
   ray-tracing for spatially consistent trajectories).
4. **Attacks that are not adaptive.** A security paper that only tests
   the attack from the prior paper is rejected by TIFS/JSAC-security
   reviewers. We must include an *adaptive attacker that knows the
   defense* (E7) and show the defense's failure mode honestly.
5. **No cost accounting.** Latency/FLOPs per block vs. the baseline, and
   the clean-condition cost (parity target ≤0.2 dB).
6. **Unreproducible numbers.** Every number in the manuscript must be
   traceable to a JSON run record (seed, config hash, git commit).

## 2. What exists (primary sources checked)

* **DeepSIC / online / meta / Bayesian** — `tomerraviv95/facilitating-adaptation-deep-receivers`
  (commit 06b5be1, Feb 2024). Architecture: per-user, per-iteration MLP
  `Linear(in→64·|S|) → ReLU → Linear(→|S|)`, input = received vector
  (real/imag split) ++ other users' soft symbols. Q=3 iterations.
  Online training: Adam lr 5e-3, 300 epochs *per block*, on the pilot
  part only. Meta-DeepSIC: MAML, META_LR 0.01, meta-updates every 5
  blocks on a buffer of past pilots. Channels: SED `exp(-|i-j|)` with
  deterministic cosine fading (periods 51/39/33/21 blocks per user),
  optional `tanh(0.5·y)` nonlinearity; COST2100 as 25-frame per-user
  magnitude tracks (`norm_channel`, 25×8) scaled 0.25 off-diagonal with
  unit diagonal. QPSK. Block = 200 pilot bits + 50 000 data bits in the
  paper config. SER = fraction of symbol vectors with any user wrong.
* **Attack paper** (Wu, Jiang, Niyato, Li, Luo, arXiv:2409.02430 v3) —
  transfer-based pilot poisoning against online DeepSIC / Meta-DeepSIC /
  black-box DNN / DeepRx-style ResNet; surrogate trained from observed
  pilots; perturbation crafted on the surrogate and injected into the
  channel; channels: synthetic linear, nonlinear, static, COST2100.
  `[UNVERIFIED in this environment: arXiv is network-blocked here; the
  ε=0.3 ℓ2 budget, PGD, and the 3.09 dB SER loss at 15 dB figure come from
  the proposal's own reading of the paper and must be re-checked against
  the PDF before any number is quoted in the manuscript.]` No code
  release found for the attack → we re-implement it (E1 reproduces it).
* **Drift detection** (Uzlaner, Raviv, Shlezinger, Todros, TWC 2025,
  arXiv:2407.09134) — retrain only when a per-module drift statistic
  fires. No public code found → re-implement a faithful simplified
  version (pilot-loss / posterior-entropy drift test per module).
* **Nested Learning** (Behrouz et al., NeurIPS 2025 / arXiv:2512.24695)
  — CMS: chain of blocks updated every `C^(ℓ)` steps; optimizers as
  associative memories; Delta Gradient Descent; self-modifying Titans
  surprise/retention. **Titans** (arXiv:2501.00663). Independent
  reimplementation (arXiv:2510.09551) found memory updates alone are
  insufficient with a frozen backbone → motivates multi-level + good init.
* **Defenses for this exact threat:** none found (two targeted searches).
  TTA-poisoning defenses in vision (MedBN CVPR 2024, robust BN
  statistics) do not transfer to model-based receivers. Certified
  poisoning work exists for offline RL / mean estimation / smoothing, but
  nothing couples a certificate to an *update-frequency hierarchy* and
  channel physics. The gap in the proposal holds.
* **Theory tools:** dynamic regret for OGD with moving comparator
  (Zinkevich 2003; Mokhtari et al. 2016); corruption-robust OCO
  (ICML 2025 "Unconstrained Robust OCO" gives `G(√T + k)` with `k` a
  corruption budget — the additive-`C` structure we need); dynamic regret
  under outliers (Barik et al., UAI 2026). Our Theorem 2.1 is a
  multi-rate variant: corruption enters level `k` only at `T/C_k`
  consolidation instants, each with probability `(1 − p_k^rej)`.

## 3. Design decisions that follow (and why)

| Decision | Reason |
|---|---|
| Re-implement the backbone in a *functional* style (parameters as dicts, `torch.func.functional_call`) instead of forking the reference repo | Levels, re-anchoring, MAML, and unrolled PGD all need parameters as first-class tensors. The reference code mutates `nn.Module`s in place. |
| Keep the reference architecture, hyper-parameters and SER definition *exactly* for E1/E2 | Otherwise "reproduction within ±0.5 dB" is meaningless and reviewers will ask why the baseline numbers differ from TWC 2023. |
| Levels are **full copies** of the adaptable parameter set, not disjoint partitions | Eq. (2.6) consolidates level-k *increments* into level k+1 and Eq. (2.8) bounds the displacement of level K; both need levels to live in the same coordinate system. "Which parameters are adaptable at all" (all / last layer / learned mask) is a separate ablation axis. |
| G2 uses many short CRC-protected transport sub-blocks per coherence block | With uncoded QPSK a single CRC over 10⁴ symbols fails at any SER > 1e-4, so the gate would have no dynamic range. With `L`-symbol sub-blocks the pass *fraction* `≈ (1−p)^{L·bits}` is a smooth statistic in the post-adaptation SER — exactly Proposition 2.3. A convolutional/LDPC coded variant is added for E6 (Sionna, GPU). |
| G1 = model-based *data-residual* gate (`‖Y_d − Ĥ ŝ_NN‖²` vs. `‖Y_d − Ĥ ŝ_LMMSE‖²` with a Kalman-fused LMMSE channel estimate) | Label-free, costs one matrix product, and is a genuine physical-consistency test: poisoned adaptation produces decisions inconsistent with the linear model + prior. "Probing the implied channel" of a nonlinear DeepSIC is ill-defined; this is the honest version. |
| G3 = Jakes/AR(1) innovation test on the channel estimate | Catches A2 (drift spoofing) as physically implausible jumps, independently of decisions. |
| Surprise-driven learning rate is *deterministic* in v1 (`η_b = η_max · S_b/(S_b + S̄_b)` with `S̄` an EMA) and a learned head is an ablation | Reproducible, no extra meta-training in the critical path; the self-modifying variant is kept as an option so the NL "model generates its own gate" idea is testable rather than assumed. |
| Attacks implemented as white-box (through a differentiable one-step adaptation surrogate) **and** transfer (surrogate receiver) **and** adaptive (gate-aware) | Reviewer item 4 above. |
| Every run writes a JSON record with config hash + git commit; `paper_numbers.py` regenerates every table from records | Reviewer item 6. |

## 3b. Decisions forced by the first runs (24 Oct, smoke results in `results/smoke*`)

| Observation | Change |
|---|---|
| Gate statistics compared with a clean-history EMA false-rejected 40 % of *clean* blocks: a deep fade raises the SER of every receiver, which looked like poisoning. | Every gate statistic is now **relative to a reference computed on the same block** — the LMMSE detector and, once the levels exist, the uncorrupted slow memory. "The fast level must do at least as well as the certified memory" is the test; channel-induced degradation cancels. |
| Consolidating gated *mean increments* made the slow level move ~1/C of the fast level, so re-anchoring dragged the receiver to a stale memory (clean cost). | Slow level ← gated mean of fast **states** over the period (same adversary share 1/C_k, Eq. 2.6'); re-anchoring is a proximal pull inside the fast update (default) with the Eq.-72 jump as an ablation. |
| Surprise EMA seeded by the near-zero post-pre-training gradient → ratio 10⁸. | Warm-up median + clamp to [1/8, 8]; threshold tightening floored at 0.7 of the slack. |
| During an attack the fast level still detected with poisoned parameters (attack-window SER 0.21 vs 0.30 for online DeepSIC — a reduction, not a defence). | **Gated fallback**: a rejected block's fast update is reverted and its data are detected with the slow projection. Attack-window SER → 0.10 (10 dB SIR) / 0.12 (0 dB) with zero clean false rejections. This is the mechanism the paper should lead with: the certified memory is not only protected, it *serves* when the fast memory is distrusted. |
| At SIR 0 dB the attacker also corrupts the LMMSE channel estimate the gates use as reference, letting one block through. | Reference = best of {LMMSE, slow memory} on the block. |

Meta-DeepSIC under A1 never recovered within the window (post-attack SER 0.15 vs 0.02 pre): the poisoned pilots sit in its meta-training buffer. This reproduces the qualitative Wu et al. finding and is a figure for the paper.

## 4. Open risks carried into the code

1. Wu et al. numbers unverified here (see above) — E1 is the check.
2. Clean-condition parity: Citadel's fast level *is* an online DeepSIC;
   re-anchoring to a stale slow memory at high Doppler could cost dB.
   The periods `C_k` must be set from the measured coherence (cosine
   fading periods 21–51 blocks → `C_2 ≈ 8`, `C_3 ≈ 32`) and swept.
3. A3 boiling-frog against G2 is weak by construction; the certificate
   (1/C_K) is the defence — E5 must show the empirical slope.
4. Sionna/LDPC (E6) and DeepMIMO (E4/E8) are GPU-scale; the code path is
   written but exercised only on the user's GPU.
