# Results log (regenerated from JSON run records; nothing here is typed by hand)

Setting unless stated: 4×4 QPSK uplink, SED channel with the reference cosine
fading, SNR 10 dB, 200 pilot bits + 50 000 data bits per coherence block,
100 blocks, A1 availability poisoning (white-box PGD through a 2-step unrolled
adaptation, 20 PGD steps) on blocks 30–69, seed 0, CPU. Records:
`results/full2/*.json` (commit `git log -1`).

## E3 — A1 availability attack vs. SIR (24 Oct 2026, 1 seed, preliminary)

| receiver | clean SER | SER in attack window, SIR 0 / 5 / 10 dB | SER after attack | recovery (blocks) | gate rejection of attacked / false rejection of clean |
|---|---|---|---|---|---|
| online DeepSIC (TWC 2021) | 0.056 | 0.795 / 0.483 / 0.279 | 0.093 / 0.081 / 0.078 | 12 / 11 / 9 | – |
| Meta-DeepSIC (TWC 2023) | 0.058 | – / – / 0.246 | 0.134 | 30 (censored: never recovers) | – |
| **Citadel-Rx** (K=3, C=(1,8,32), G1+G2+G3, fallback) | **0.031** | **0.027 / 0.033 / 0.034** | 0.030 / 0.031 / 0.030 | **0** | 0.97 / 0.02, 0.95 / 0.00, 0.93 / 0.00 |

Reading:
* Under attack Citadel-Rx stays on its clean trajectory at every budget,
  including SIR 0 dB where the attacker spends as much energy as all four
  users together and online DeepSIC is destroyed (80 % SER).
* The mechanism is visible in the records: 93–97 % of attacked blocks are
  rejected by the gates, their fast update is reverted, and the data are
  detected with the slow memory (`fallback` flag); the slow level's
  displacement at the end of the run is 16–22 (parameter-norm units) for the
  attacked runs vs 16 for the clean run, i.e. the poison did not reach it.
* Meta-DeepSIC is the most vulnerable receiver *after* the attack: the
  poisoned pilots stay in its meta-training buffer, so it never recovers
  within 30 blocks. This is the Wu et al. observation, reproduced.
* Clean condition: Citadel-Rx is 45 % below online DeepSIC in SER. The
  pre-training and the proximal anchoring to the slow memory act as a
  regulariser; this must be separated in the ablations (E2 with
  `receiver.pretrain=true` for online DeepSIC as well).

Figure: `docs/figures/fig_ser_vs_block_a1_sir10.png`, `..._sir5.png`,
`..._sir0.png` (SER vs block, clean trajectories dashed, attack window shaded).

## E3 full sweep from the GPU workstation (25 Oct 2026; 3 seeds; records `results/e3/`)

SER in the attack window (blocks 30–69), mean over 3 seeds. Clean-window SER of every
receiver is in the "pre" column; "post" is the mean after the attack; "rec" the recovery
time in blocks (30 = censored, never recovered within the run).

| receiver | pre | **white-box A1**, SIR −10 / −5 / 0 / 5 / 10 dB | post (SIR 0) | rec | **transfer A1**, SIR −10 / −5 / 0 / 5 / 10 dB | rec | data jamming, 0 dB (control) |
|---|---|---|---|---|---|---|---|
| LMMSE (no adaptation) | 0.056 | n/a¹ | – | – | 0.873 / 0.740 / 0.447 / 0.149 / 0.064 | 0 | 0.892 |
| online DeepSIC | 0.071 | 0.973 / 0.936 / 0.769 / 0.474 / 0.279 | 0.087 | 11 | 0.353 / 0.367 / 0.347 / 0.289 / 0.205 | 10 | 0.855 |
| Meta-DeepSIC | 0.062 | 0.863 / 0.800 / 0.594 / 0.400 / 0.243 | 0.187 | 30† | 0.194 / 0.206 / 0.214 / 0.207 / 0.171 | 14 | 0.851 |
| drift-detection | 0.077 | 0.975 / 0.942 / 0.776 / 0.459 / 0.265 | 0.097 | 10 | 0.345 / 0.359 / 0.337 / 0.277 / 0.199 | 7 | 0.858 |
| MedBN-style | 0.065 | 0.933 / 0.853 / 0.738 / 0.549 / 0.397 | 0.204 | 30† | 0.724 / 0.641 / 0.544 / 0.423 / 0.296 | 30† | 0.858 |
| single-memory Titans | 0.068 | 0.975 / 0.939 / 0.788 / 0.486 / 0.276 | 0.075 | 6 | 0.363 / 0.368 / 0.354 / 0.290 / 0.200 | 6 | 0.861 |
| **Citadel-Rx** | **0.039** | **0.025 / 0.025 / 0.026 / 0.029 / 0.032** | **0.029** | **0** | **0.026 / 0.026 / 0.027 / 0.029 / 0.037** | **0** | 0.848 |

Citadel gate statistics across the sweep: rejection of attacked blocks 0.87–0.99
(white-box), 0.77–0.98 (transfer); false rejection of clean blocks 0.000–0.017.

¹ The white-box attacker differentiates through the victim's adaptation map; LMMSE has
none, so the "white-box" record for LMMSE contains no perturbation. The transfer column
(perturbation crafted on a surrogate and injected) is the valid LMMSE row; it shows that
pilot poisoning also wrecks model-based channel estimation at high budgets. Fixed in the
code: receivers without an adaptation map are now attacked through the surrogate.
† Censored: SER had not returned to within 10 % of the pre-attack level 30 blocks after the attack.

Reading:
* Against Citadel-Rx, pilot poisoning is worthless at every budget and under both
  knowledge models: the attack-window SER (0.025–0.037) is at or below the receiver's own
  clean level (0.039, blocks 0–29), and recovery is immediate. Every other receiver is
  destroyed at ≤ 0 dB (SER 0.6–0.98) and still loses 4–6× at 10 dB.
* The equal-energy jamming control makes the point a security reviewer wants: against
  every baseline, poisoning the 200 pilot bits is as damaging as jamming the 50 000 data
  bits with the same energy (0.77 vs 0.86 at 0 dB) *and* leaves persistent damage
  (Meta-DeepSIC and MedBN never recover; jamming leaves no trace). Against Citadel the
  attacker is reduced to plain jamming, which costs continuous power and has no persistence.
* Transfer attacks are weaker than white-box for the baselines (as Wu et al. report) but
  not harmless (0.2–0.37); Citadel is indifferent to the knowledge model.
* The vision-style robust-gradient defence (MedBN) is the worst receiver under attack and
  the only baseline besides Meta-DeepSIC with permanent damage.

## E2 clean parity → clean *gain* (26 Oct; 3 seeds; `results/e2/`; full table: `docs/TABLES.md`)

Clean SER at 10 dB, no attack, 100 blocks: cosine fading — LMMSE 0.054, online 0.059,
Meta 0.053, drift 0.065, MedBN 0.064, single-memory Titans 0.053, **Citadel 0.030**;
Jakes f_D T_b = 0.05 — LMMSE 0.0095, online 0.011, Meta 0.010, **Citadel 0.0053**. Citadel
is the best receiver at every SNR from 4 to 12 dB on both fading models (at 14–16 dB all
receivers are at the 1e-4 floor of a 100-block run and differences are noise). Since
pre-trained online DeepSIC is *not* better than online DeepSIC (0.074 vs 0.069 pre-attack
in the SIR-10 runs), the gain comes from the memory hierarchy: the slow levels accumulate
channel knowledge across blocks and the proximal anchor turns it into a prior for the
per-block fit from 100 pilot symbols. The proposal's parity target (≤ 0.2 dB cost) is
replaced by a ~2 dB clean gain, which must be presented as a second contribution and
ablated (see below).

## E1 reproduction of the attack (3 seeds; `results/e1/`)

White-box A1 destroys online DeepSIC and Meta-DeepSIC at ≤ 0 dB SIR on both the linear
and the tanh-PA channel (0.78–0.97) and still costs 4–5× at 10 dB; Meta-DeepSIC never
recovers (30 blocks censored, post-attack SER 0.18–0.20 vs 0.06–0.07 clean). The transfer
attacker is much weaker on the linear channel (0.26–0.30) but nearly as strong as white-box
on the nonlinear channel (0.67–0.77): the surrogate transfers better when the receiver's
nonlinearity is what the attack exploits. (The Wu et al. "3.09 dB at 15 dB" figure uses a
per-symbol ε budget; the Δ_dB comparison comes from E3snr.)

## Ablations under white-box A1 at SIR 0 dB (3 seeds; `results/ablate/`)

| variant | clean (pre) | attack window | recovery | rejection | false rej. |
|---|---|---|---|---|---|
| full Citadel (K=3, C=1/8/32, G1+G2+G3, DGD, surprise η, proximal anchor, fallback) | 0.039 | **0.026** | 0 | 0.97 | 0.006 |
| K=1 (single memory, gates active, no slow level to fall back on) | 0.068 | 0.788 | 6.3 | 0.98 | 0.222 |
| K=2 (C=1/8) | 0.038 | 0.050 | 0 | 0.97 | 0.006 |
| K=4 (C=1/4/16/64) | 0.038 | 0.029 | 0 | 0.97 | 0.011 |
| periods misaligned with coherence (C=1/3/7) | 0.037 | 0.031 | 0 | 0.95 | 0.000 |
| no gates | 0.039 | 0.540 | 0 | 0.00 | – |
| G1 only | 0.039 | 0.031 | 0 | 0.97 | 0.000 |
| G2 only | 0.039 | 0.028 | 0 | 0.97 | 0.000 |
| G3 only | 0.039 | 0.507 | 0 | 0.08 | 0.000 |
| adaptable = last layer only | 0.052 | 0.029 | 0 | 0.98 | 0.011 |
| plain GD fast rule | 0.066 | 0.048 | 0 | 0.90 | 0.072 |
| Adam without the delta-rule decay | 0.040 | 0.030 | 0 | 0.97 | 0.006 |
| fixed η (no surprise) | 0.040 | 0.027 | 0 | 0.97 | 0.011 |
| **no anchoring** (λ = 0, β = 0) | **0.058** | 0.031 | 0 | 0.99 | 0.178 |
| jump re-anchoring (Eq. 72, β = 0.25) instead of proximal | 0.058 | 0.031 | 0 | 0.97 | 0.150 |
| **no fallback** (rejected block still detected by the fast level) | 0.040 | **0.245** | 0 | 0.97 | 0.011 |
| keep (not revert) the fast update of a rejected block | 0.040 | 0.025 | 0 | 1.00 | 0.017 |

Reading:
* **The proximal anchor is the clean gain.** Without it clean SER goes 0.039 → 0.058
  (online DeepSIC: 0.069), and the jump re-anchoring of the CMS paper is no better than no
  anchoring at all; both also raise clean false rejections to 15–18 % because the fast
  level drifts away from the memory it is compared against. Continuous proximal pull
  toward the slow projection is what turns the memory hierarchy into a prior.
* **The fallback is the attack-window protection.** Reverting a rejected update alone
  leaves the data of that block to a poisoned fast level (0.245); detecting it with the
  slow projection brings it to 0.026. Whether the rejected update is reverted or kept
  makes no difference once the fallback is active (0.025 vs 0.026).
* **The slow memory is the mechanism.** With a single level the gates still fire (0.98)
  but there is nothing uncorrupted to fall back on, and the receiver collapses like online
  DeepSIC; two levels already give 0.050 and three or four give the clean level.
* G1 or G2 alone defeats the non-adaptive A1 (E7 shows G1 alone does not survive a
  gate-aware attacker); G3 alone is useless against A1, as the proposal predicted — its
  role is A2/A3.
* Honest negatives: the delta-rule decay and the surprise-driven rate each buy only
  2–3 % clean SER; period alignment with the coherence structure does not matter on this
  channel; plain GD costs clean performance and false rejections.
* (The `no_reanchor` row of the first GPU sweep set the jump weight while the anchoring
  mode is proximal and is discarded; the four corrected variants above were run here.)

## E4 — A2 targeted drift spoofing, Jakes f_D T_b = 0.05, SIR 0 dB (3 seeds; `results/e4/`)

Online DeepSIC and Meta-DeepSIC lose all users (window SER 0.44 / 0.35; user-0 SER 0.16 /
0.11, others 0.16 / 0.13 — with λ = 1 the attack is not very selective), Citadel stays at
its clean level (0.010) with 82 % rejection. G3 on/off makes no measurable difference:
G1/G2 catch this attack anyway. G3's value has to be shown on A3 (E5) or reported as
not needed in these settings.

## E3 on the nonlinear (tanh PA) and COST2100 channels (3 seeds; `results/e3nl/`, `results/e3cost/`)

Nonlinear channel, white-box A1, SER in attack window at SIR −10 / −5 / 0 / 5 / 10 dB:
online 0.97 / 0.94 / 0.78 / 0.54 / 0.32 (recovery 12 blocks); Meta 0.87 / 0.80 / 0.66 / 0.46 / 0.31
(never recovers, post 0.20); drift 0.97 / 0.94 / 0.79 / 0.52 / 0.32; MedBN 0.91 / 0.82 / 0.71 /
0.51 / 0.36 (never recovers); single-memory Titans 0.97 / 0.94 / 0.80 / 0.53 / 0.31;
**Citadel 0.026 / 0.026 / 0.026 / 0.026 / 0.029** (clean 0.042, recovery 0, rejection 0.98,
false rejection 0.008). COST2100 (SNR 10 dB, where all receivers are at SER ≤ 1e-3 clean):
online 0.93 / 0.85 / 0.64 / 0.28 / 0.13 (recovery 18 blocks), Meta 0.79 / 0.66 / 0.35 / 0.16 /
0.07 (never recovers), **Citadel 0.0022 / 0.0032 / 0.0054 / 0.0122 / 0.0111** (clean 0.0003,
post 0.0006, recovery 13 blocks, rejection 0.64 ± 0.33, false rejection 0.004). Citadel is
50–400× better than online DeepSIC at every budget, but this is the one setting where it
does *not* stay on its clean trajectory: at a 3e-4 operating point the CRC gate's SER
slack (an absolute 1 percentage point, Prop. 2.3) is 30× the clean SER, so the attacker
can degrade the receiver to ~1e-2 while passing G2 (rejection falls to 0.64). The same
effect appears at 14–16 dB in E3snr. It is a threshold-design limit, not a structural one;
a relative slack (a multiple of the reference SER) is the fix and is being tested
(`results/e3cost_slack/`).

## E2 on the nonlinear and COST2100 channels (3 seeds; `results/e2nl/`, `results/e2cost/`)

Nonlinear channel: Citadel is the best receiver at every SNR (10 dB: 0.033 vs LMMSE 0.056,
online 0.065, Meta 0.060, Titans 0.057). COST2100 (a nearly diagonal 4×4 channel on which
LMMSE is close to optimal): Citadel matches LMMSE within 2–15 % at 4–8 dB (0.139 / 0.035 /
0.0047 vs 0.134 / 0.034 / 0.0041) while every DeepSIC baseline is 1.5–2.3× worse than LMMSE;
above 10 dB all receivers sit at the 1e-4 floor of a 100-block run. The clean gain is
therefore channel-dependent — large where interference cancellation matters, nil where
LMMSE is already optimal — and the paper must say so.

## E3snr — degradation Δ_dB (3 seeds; `results/e3snr/`; `figures/e3snr/table_degradation_db.md`)

Δ_dB = extra SNR needed under white-box A1 at SIR 0 dB to reach the clean SER. For every
baseline the attacked SER stays at 0.45–0.91 across the whole 4–16 dB grid, so Δ_dB is
unbounded (> 12 dB at 4 dB, never reached within the grid). For Citadel: Δ_dB ≤ 0 at 4–10 dB
(the attacked window is detected by the slow memory and happens to sit on the easy part of
the fade), 1.8 dB at 12 dB, > 2 dB at 14 dB and unbounded at 16 dB — at high SNR the
clean SER is 1e-4–7e-4 and the attacked window runs on a frozen slow memory plus the
rare leaked block (3e-3–6e-3). This is the honest limit of the defence: it holds the
receiver near 1e-2–1e-3 under attack, it does not preserve a 1e-4 operating point.
Reported as such; the mechanism to improve it is a faster re-admission of clean blocks
(the gate's clean-EMA warm-up) and is left as future work.

## E5 — boiling-frog A3 and the retention certificate (3 seeds; `results/e5/`; `docs/figures/fig_e5_certificate.png`)

A3 (per-block budget 5 % of the pilot energy, 300 attacked blocks, objective: push the
receiver toward a spoofed-channel basin while keeping the SER within the gate's slack)
passes the gates by construction (rejection 0.00) and raises the window SER by one point
(0.029–0.032 → 0.039–0.040, post 0.023). The paired displacement of the slowest level,
‖θ^(K)_adv − θ^(K)_clean‖, grows linearly in the number of attacked blocks with slope
0.084 / 0.029 / 0.0083 per block for C_K = 8 / 32 / 128 — ratios 1 : 0.35 : 0.10 against the
certificate's 1 : 0.25 : 0.0625 (i.e. ∝ C_K^−0.85). End-of-window displacement 30.5 / 9.1 /
2.0. Corollary 2.2's 1/C_K structure is confirmed within a factor 1.6 over a 16× range of
C_K; the constant (η_K ρ ε G (1 − p^rej)) is not yet measured and must be, for the bound
line to be drawn on the figure.

## 3-seed replication of the key cells (seeds 0, 1, 2; mean ± std over seeds)

| receiver | clean SER (no attack, 100 blocks) | pre-attack SER | SER in attack window (SIR 10 dB) | SER after | recovery |
|---|---|---|---|---|---|
| online DeepSIC | 0.0575 ± 0.0014 | 0.0696 ± 0.0033 | 0.2779 ± 0.0095 | 0.0772 ± 0.0041 | 9, 9, 12 |
| **Citadel-Rx** | **0.0305 ± 0.0006** | 0.0395 ± 0.0010 | **0.0342 ± 0.0006** | 0.0299 ± 0.0005 | 0, 0, 0 |

Seed-to-seed spread is an order of magnitude below the effect; the headline
numbers are not a seed artefact.

## Baselines and ablations at SIR 10 dB (1 seed)

| receiver | clean SER (blocks 0–29) | SER in attack window | SER after | recovery (blocks) |
|---|---|---|---|---|
| online DeepSIC | 0.069 | 0.279 | 0.078 | 9 |
| online DeepSIC + joint pre-training | 0.074 | 0.274 | 0.082 | 12 |
| drift-detection receiver (TWC 2025 style, "adapt less") | 0.088 | 0.265 | 0.080 | 4 |
| MedBN-style median-of-means gradient (vision TTA defence) | 0.073 | 0.365 | 0.170 | 30 (censored) |
| single-memory Titans receiver (DGD + surprise rate, K=1, no gates) | 0.069 | 0.269 | 0.073 | 8 |
| **Citadel-Rx** | **0.039** | **0.034** | **0.030** | **0** |

Reading:
* Pre-training does not explain Citadel's clean advantage (pre-trained online
  DeepSIC: 0.074), nor its robustness. The gain comes from the levels, the
  gates and the proximal anchoring.
* A single test-time memory with the same fast rule is exactly as vulnerable
  as online DeepSIC: NL-style memory without the frequency hierarchy is not a
  defence (consistent with the Titans reimplementation study).
* The drift-detection receiver trades clean performance (0.088) for a small
  robustness gain and a faster recovery; the vision-style robust-gradient
  defence is worse than no defence and leaves a lasting poison (post 0.17).

## E7 adaptive (gate-aware) attacker and transfer attacker, SIR 10 dB (1 seed)

| receiver / gates | attacker | SER in attack window | attacked blocks accepted | rejection of attacked |
|---|---|---|---|---|
| Citadel, G1 only | adaptive (G1-penalty weight 5) | 0.046 | 8 / 40 | 0.80 |
| Citadel, G1 only | adaptive (weight 500 — attacker's best effort) | 0.074 | 28 / 40 | 0.30 |
| Citadel, G1 only | adaptive (weight 50) | 0.044 | 6 / 40 | 0.85 |
| Citadel, G1+G2+G3 | adaptive (weight 5) | 0.032 | 1 / 40 | 0.97 |
| Citadel, G1+G2+G3 | adaptive (weight 500 — best effort) | 0.027 | 2 / 40 | 0.95 |
| Citadel, G1+G2+G3 | A1 transfer (surrogate receiver) | 0.041 | 14 / 40 | 0.65 |
| online DeepSIC | A1 transfer | 0.197 (white-box: 0.278) | – | – |

Reading: a gate-aware attacker partially defeats the residual gate on its
own (as the proposal predicted: G1 is necessary but weak); with the CRC and
prior gates it gains nothing. Transfer attacks are milder than white-box
(as in Wu et al.) and slip the gates more often, but the leaked blocks cost
little. The gate-aware weight sweep (5 / 50 / 500) shows the attacker's
trade-off against G1 alone (rejection 0.80 → 0.85 → 0.30, SER 0.046 → 0.044 →
0.074: evading the residual test costs poisoning strength); against the full
gate set the best-effort attacker gains nothing (rejection 0.95, SER 0.027).

## Tighter / relative CRC slack on COST2100 (31 Oct–1 Nov; 3 seeds; `results/e3cost_slack/`, `results/e3rel/`)

Absolute slack 0.001 instead of 0.01, COST2100, white-box A1 at SIR 0 dB: attack-window SER
0.0009 / 0.0008 / 0.0009 (seeds 0–2) against 0.0050 / 0.0070 / 0.0042 with the default slack;
pre-attack 0.0003–0.0004, post 0.0004; rejection 0.88 / 0.93 / 0.85 (was 0.72–0.80); false
rejection 0.00; recovery 2–9 blocks (was 9–16). The low-SER weakness is the threshold, not
the architecture. Fix: `citadel.g2_slack_mode=relative`, slack = max(δ_min, ρ · p_ref) with
p_ref the per-symbol error probability implied by the reference pass rate (Prop. 1).

First calibration (ρ = 0.3, δ_min = 0.001; `results/e3rel/`, 3 seeds): COST2100 fixed
(attack SER 0.0008–0.0010, rejection 0.78–0.88, false rejection 0) and the linear attack cell
unchanged (0.024–0.025), **but linear false rejections rose to 15–20 %**. Cause, measured from
the records: the reference per-symbol SER on the linear channel is p_ref ≈ 0.009 (median),
0.0003–0.02 across the fade, not the 0.03 any-user SER, so 0.3 · p_ref sat on the 0.001 floor
on easy blocks — 10× tighter than the absolute rule that had worked, and inside the
statistical resolution of the pass fraction (std ≈ 0.011 at n = 781 sub-blocks). Clean SER was
unaffected (0.039, the fallback detector is as good on those blocks) but a 15 % false-rejection
rate is not acceptable in a paper. Second calibration (ρ = 1.0, δ_min = 0.002 ≈ 5 sd of the pass
fraction; `results/e3rel2/`, 3 seeds) — **adopted as the default of the relative mode**:

| cell | pre | attack window | post | recovery | rejection | false rejection |
|---|---|---|---|---|---|---|
| COST2100, absolute slack 0.01 (old) | 0.0003 | 0.0042 / 0.0050 / 0.0070 | 0.0006 | 9–16 | 0.72–0.80 | 0.00 |
| COST2100, relative (ρ=1, δ_min=0.002) | 0.0003 | **0.0009 / 0.0012 / 0.0016** | 0.0004 | 1–14 | 0.82–0.88 | 0.00 |
| linear, absolute slack 0.01 (old) | 0.039 | 0.0245 / 0.0270 / 0.0272 | 0.029 | 0 | 0.95–1.00 | 0.00–0.02 |
| linear, relative (ρ=1, δ_min=0.002) | 0.040 | **0.0237 / 0.0241 / 0.0245** | 0.029 | 0 | 1.00 | 0.02 |

The relative rule removes the low-SER weakness (4–5× lower attack-window SER on COST2100,
back within 3–5× of the clean level instead of 15–25×) and leaves the linear cell exactly
where it was, with the same 2 % false rejections. The full relative-slack grid
(`sweep.py e3rel`: five budgets on COST2100, SNR 10–16 dB, the linear SIR grid) runs on
the GPU box and will replace the absolute-slack rows of the COST2100 and E3snr sections.

## Gate operating characteristics and per-block cost (`scripts/gate_roc.py`; `docs/figures/fig_gate_roc.png`)

ROC of the gate verdict γ as a detector of poisoned blocks, pooled over seeds and
budgets, blocks ≥ 5 (gate warm-up excluded):

| experiment | attack | poisoned / clean blocks | AUC γ | AUC G1 | AUC G2 | AUC G3 | rejection at γ<0.5 | false rejection at γ<0.5 |
|---|---|---|---|---|---|---|---|---|
| e3 (linear) | A1 | 1200 / 1650 | 0.989 | 0.988 | 0.999 | 0.963 | 0.944 | 0.007 |
| e3 | data jamming | 120 / 165 | 1.000 | 0.135 | 1.000 | 0.375 | 1.000 | 0.000 |
| e3nl | A1 | 600 / 825 | 0.989 | 0.989 | 0.999 | 0.973 | 0.982 | 0.008 |
| e3cost (absolute slack) | A1 | 600 / 825 | 0.932 | 0.884 | 0.925 | 0.921 | 0.637 | 0.005 |
| e4 (Jakes) | A2 | 240 / 330 | 0.992 | 0.976 | 0.999 | – | 0.821 | 0.003 |
| e7 | gate-aware | 560 / 770 | 0.982 | 0.987 | – | – | 0.912 | 0.004 |

G2 is the strongest single gate against A1 (AUC 0.999), G1 is close, G3 is weak against
A1 as designed; the min-combination inherits the best of them at every operating point.
Under data jamming G1 is *inverted* (AUC 0.135: the fast level's decisions are more
consistent with the model than the reference's under jamming) and G2 alone carries the
verdict — a reminder that the gates are not interchangeable.

Per-block compute, CPU single thread, 300 adaptation epochs (mean ± sd over all records):
LMMSE 0.09 s; online DeepSIC 4.32 ± 1.71 s (pre-training 30 s); drift 6.95 s; Meta-DeepSIC
9.50 s; single-memory Titans 12.18 s; **Citadel 11.15 ± 6.48 s (2.6× online DeepSIC)**;
MedBN 29.93 s. The white-box attacker's PGD costs 3.20 ± 1.70 s per poisoned block.
Citadel's overhead over the single-memory receiver is the gate (one LMMSE detection and one
CRC check of the data block); the levels cost memory (K copies of the adaptable
parameters), not compute.

## Certificate with measured constants (`scripts/certificate_check.py`; `docs/figures/fig_e5_certificate_bound.png`)

Constants measured by finite differences on 10 clean blocks of the E5 configuration
(`docs/certificate_constants.json`): block-adaptation input sensitivity G_Φ = 5.21 (max over
blocks and probes; mean 3.13), state contraction L_θ = 0.86 (mean 0.76), anchor sensitivity
L_a = 0.35 (mean 0.32), A3 budget ε = 1.05 per block, single-gradient constant 2.96.

* L_θ + L_a = 1.20 ≥ 1: the random probes do **not** certify the contraction that the
  Lipschitz branch of Theorem 1 (part ii) needs, so the paper reports the structural
  branch (part i), which needs no regularity of the fast learner and uses the measured
  paired fast-level displacement Δ_f (max over the window: 33.4 / 17.2 / 15.9 for
  C_K = 8 / 32 / 128).
* Structural bound D_K(W) ≤ Δ_f (1 − (1 − η_K)^{n(W)}) holds at every W: max ratio measured /
  bound 0.94 / 0.53 / 0.26. Nearly tight at C_K = 8, loose at 128 (the slow level has only
  two consolidations in 300 blocks and the bound charges the full Δ_f to each).
* The measured fast displacement is of the size the geometric sum predicts from L_θ alone
  (ε G_Φ /(1 − L_θ) ≈ 39 vs 16–34 measured), i.e. the anchor coupling does not compound.
* `prox_lambda` sweep of the constants (`docs/certificate_constants_lambda.json`, 5 clean
  blocks each): λ = 0.5 (default) / 1 / 2 / 4 → G_Φ 5.21 / 1.54 / 2.22 / 2.21, L_θ 0.86 / 0.54 /
  0.40 / 0.38, L_a 0.35 / 0.54 / 0.82 / 1.01. Anchoring lowers the state sensitivity exactly as
  it raises the anchor sensitivity: L_θ + L_a ≈ 1 is structural (the fast map converges toward
  the anchor), so the contraction branch of Theorem 1 cannot be bought with λ and the paper
  claims the design bound and the structural bound of its Theorem 1 (Section IV of
  paper/main.tex; docs/THEORY.md records the first version and is superseded).
  Side result worth a sentence in the paper: λ = 1 roughly halves the input sensitivity G_Φ
  of the fast level (5.2 → 1.5) — a stronger prior makes the per-block fit less steerable by
  the pilots, clean or poisoned.

## Full relative-slack grid (GPU box, 2 Nov; 3 seeds; `results/e3rel/`, 57 records; ρ = 1, δ_min = 0.002)

COST2100, white-box A1, SER in the attack window at SIR −10 / −5 / 0 / 5 / 10 dB:
**0.0011 / 0.0012 / 0.0012 / 0.0015 / 0.0028** (clean 0.0003, post 0.0004, recovery 0–9 blocks;
rejection 0.89 / 0.90 / 0.86 / 0.74 / 0.40; false rejection 0.00). Against the absolute-slack rows
(0.0022 / 0.0032 / 0.0054 / 0.0122 / 0.0111) this is 2–8× lower and 4–9× the clean level instead
of 7–40×. At SIR 10 dB the weak attacker slips under the slack more often (rejection 0.40)
but the harm it can do while passing is, by construction, bounded by the slack.

Linear channel, same grid (no-regression check): 0.0255 / 0.0252 / 0.0247 / 0.0250 / 0.0285
at SIR −10 … 10 dB, clean 0.039, rejection 0.93–1.00, false rejection 0.00–0.02 — identical to
the absolute-slack rows of the E3 table.

SNR sweep at SIR 0 dB, clean / attacked window: 10 dB 0.0305 / 0.0250; 12 dB 0.0059 / 0.0062;
14 dB 0.0008 / 0.0018; 16 dB 0.0001 / 0.0009 (rejection 0.97–1.00 / 0.97–1.00 / 0.93–0.97 /
0.88–0.93). Δ_dB is now ≈ 0 at 12 dB (was 1.8) and the attacked window sits at 1e-3 at
14–16 dB (was 3e-3–6e-3). Δ_dB at 14–16 dB remains outside the grid: the ~5 % of poisoned
blocks that pass the gate set a floor near 1e-3 that a 1e-4 operating point cannot absorb.
Stated as a limitation; closing it needs rejection → 1, not a different slack.

Gate ROC on this grid: AUC 0.988 (γ), 0.956 (G1), 0.974 (G2), 0.947 (G3); rejection 0.90 at
0.7 % false rejection (`docs/figures/fig_gate_roc.png`, regenerated with e3rel/e8/e9).

## 8×8 QPSK (GPU box, 2 Nov; 3 seeds; `results/e8/`, 84 records)

Linear SED channel with eight users (cosine fading periods extended with co-prime periods
for users 5–8), SNR 10 dB, white-box A1 on blocks 30–69.

| receiver | clean (no attack) | pre | attack window, SIR −10 / 0 / 10 dB | post (0 dB) | recovery | rejection / false rej. |
|---|---|---|---|---|---|---|
| LMMSE | 0.129 | 0.141 | 0.983 / 0.793 / 0.200 (transfer) | 0.129 | 7 | – |
| online DeepSIC | 0.204 | 0.250 | 0.998 / 0.971 / 0.615 | 0.316 | 11 | – |
| Meta-DeepSIC | 0.187 | 0.220 | 0.972 / 0.934 / 0.603 | 0.656 | 30† | – |
| drift-detection | 0.217 | 0.259 | 0.997 / 0.971 / 0.608 | 0.316 | 11 | – |
| MedBN-style | 0.177 | 0.158 | 0.995 / 0.923 / 0.644 | 0.396 | 30† | – |
| single-memory Titans | 0.177 | 0.234 | 0.998 / 0.969 / 0.583 | 0.280 | 9 | – |
| **Citadel-Rx** | **0.102** | 0.127 | **0.080 / 0.080 / 0.090** | 0.096 | 6 | 0.97–1.00 / 0.03–0.05 |

With twice the users the clean gain grows (Citadel 0.102 vs LMMSE 0.129, online 0.204:
interference cancellation matters more), the attack destroys every baseline at ≤ 0 dB
(SER 0.92–0.998) and Meta-DeepSIC/MedBN again never recover (post-attack 0.40–0.66), and
Citadel-Rx stays below its own pre-attack level at every budget. False rejections rise to
3–5 % (the 8-user fade has deeper per-block dips) and are the reason the "recovery" column
reads 6 rather than 0: the post-attack SER (0.096) is within 10 % of the pre-attack level
only after the fade turns.

## Doppler sweep (GPU box, 2 Nov; 3 seeds; `results/e9/`, 63 records)

Jakes block fading, f_D T_b = 0.01 / 0.05 / 0.10, SNR 10 dB, white-box A1 at SIR 0 dB, SER in
the attack window (pre-attack in parentheses):

| receiver | 0.01 | 0.05 | 0.10 | recovery | post-attack |
|---|---|---|---|---|---|
| LMMSE (transfer) | 0.067 (0.015) | 0.067 (0.017) | 0.103 (0.021) | 0–1 | 0.002–0.009 |
| online DeepSIC | 0.719 (0.017) | 0.719 (0.019) | 0.717 (0.026) | 3–6 | 0.017–0.021 |
| Meta-DeepSIC | 0.496 (0.013) | 0.501 (0.017) | 0.531 (0.026) | 25–30† | 0.074–0.087 |
| drift-detection | 0.728 (0.023) | 0.738 (0.029) | 0.717 (0.040) | 5–11 | 0.026–0.032 |
| MedBN-style | 0.711 (0.015) | 0.692 (0.017) | 0.691 (0.025) | 30† | 0.16 |
| single-memory Titans | 0.738 (0.015) | 0.749 (0.018) | 0.736 (0.023) | 4–5 | 0.015–0.020 |
| **Citadel-Rx** | **0.0066 (0.0071)** | **0.0069 (0.0098)** | **0.0075 (0.0147)** | 0–1 | 0.001–0.003 |

Rejection 0.92 / 0.94 / 0.97, false rejection 0.006 / 0.011 / 0.033. Faster fading raises the
clean SER of every receiver and raises Citadel's false rejections (a fast channel looks more
"surprising"), but the defence does not weaken: the attack-window SER is flat at 0.007 across
a 10× range of Doppler. Gate AUC 0.996.

## Five seeds on the headline cells (seeds 0–4; `results/e3/`, `results/e2/`)

| cell | online DeepSIC | Meta-DeepSIC | Citadel-Rx |
|---|---|---|---|
| clean SER, cosine, 10 dB | 0.0590 ± 0.0008 | 0.0527 ± 0.0008 | **0.0302 ± 0.0004** |
| clean SER, Jakes 0.05, 10 dB | 0.0128 ± 0.0058 | 0.0115 ± 0.0049 | **0.0059 ± 0.0028** |
| pre-attack SER (E3) | 0.0714 ± 0.0014 | 0.0617 ± 0.0010 | 0.0397 ± 0.0007 |
| white-box A1, SIR −10 dB | 0.973 ± 0.003 | 0.861 ± 0.009 | **0.0261 ± 0.0017** |
| white-box A1, SIR 0 dB | 0.772 ± 0.013 | 0.593 ± 0.011 | **0.0277 ± 0.0021** |
| white-box A1, SIR 10 dB | 0.277 ± 0.005 | 0.241 ± 0.006 | **0.0344 ± 0.0029** |
| transfer A1, SIR 0 dB | 0.347 ± 0.013 | 0.213 ± 0.012 | **0.0270 ± 0.0026** |
| data jamming, 0 dB | 0.855 ± 0.001 | 0.851 ± 0.001 | 0.848 ± 0.001 |

(The Jakes clean cell has a large seed spread for every receiver because the realised
fade differs per seed; the ranking is the same in all five seeds.)

Record count after this round: 1926 JSON records in `results/`.

## Caveats (to be closed before any number enters the manuscript)
1. Closed: three seeds everywhere, five on the headline cells.
2. The attacked blocks' SER (0.03) is *lower* than the clean run's mean
   because the window happens to cover the easy part of the fade; the honest
   metric is the per-block difference to the clean trajectory, which the
   figure shows (≤ 0.06 at the deepest fade).
3. Closed: nonlinear, COST2100, Jakes (three Dopplers) and 8×8 all run.
4. Primary source verified by title/author search: K. Wu, W. Jiang, D. Niyato, Y. Li, C. Luo, "Transfer-based Adversarial Poisoning Attacks for Online (MIMO-)Deep Receviers", arXiv:2409.02430v3 (Sep 2024). Their specific dB figures could not be read here (arXiv not reachable from this session); the manuscript cites the paper qualitatively only.
