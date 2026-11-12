# Theory: statements and proofs

**SUPERSEDED.** This document records the theory of the first version of the receiver
(consolidation rule with max(1, sum gamma), Theorem 1 under equal verdicts, the regret bound of
Theorem 2). It is not the theory of the paper; the revised rule, Lemma 1, Theorem 1 and Remark 1
are in Section IV of `paper/main.tex`. The proof of Lemma 2 below does not hold for
sum gamma < 1, Theorem 2 is withdrawn because the measured L_theta + L_a exceeds one, and
remark (e) and Propositions 1-2 claim more than the paper does. The item numbers are kept because
other files cite them (`citadel_rx/theory/bound.py`, `scripts/certificate_check.py`); the constants
were measured by that code and are in `docs/certificate_constants.json` and `docs/RESULTS.md`.

Notation. Blocks b = 1, 2, …; U users, pilot observation Y_b (the received
pilot matrix), data observation Y_b^d. The adaptable parameters form a vector
θ ∈ R^d (the concatenation of the adaptable keys). Norms are Euclidean (Frobenius
for matrices).

## 1. The implemented algorithm, as a dynamical system

**Fast level (level 1).** Before block b the fast state is θ_{b−1}. One block of
adaptation is the map

    θ̃_b = Φ(θ_{b−1}; Y_b, a_b),

where a_b is the *anchor* (the fixed convex combination a_b = Σ_{k≥2} w_k θ^{(k)}_{b−1}
of the slow levels, Σ w_k = 1) and Φ runs T fast steps of Adam on the pilot
cross-entropy with the delta-rule decay and the proximal pull −ηλ(θ − a_b)
(`_fast_stage`). Φ is deterministic given (θ, Y, a).

**Gate.** From the data block the gate returns γ_b ∈ [0, 1] (`GateController.evaluate`).
If γ_b < 1/2 the block is *rejected*: the fast state is reverted, θ_b = θ_{b−1}
(`reject_action = revert`), and the data are detected with the anchor
(`fallback_on_reject`). Otherwise θ_b = θ̃_b.

**Consolidation (levels k ≥ 2).** Level k has period C_k, with C_1 = 1 < C_2 < … < C_K
and C_{k+1} a multiple of C_k. Every C_k blocks, level k receives the gated mean of
the level-(k−1) states buffered since its last consolidation,

    θ^{(k)} ← θ^{(k)} + s · ( Σ_j γ_j θ^{(k−1)}_j / max(1, Σ_j γ_j) − θ^{(k)} ),
    s = η^{(k)} · min(1, Σ_j γ_j),                                            (1)

with η^{(k)} ∈ (0, 1] (`_consolidate`). The buffered level-(k−1) states are the
states at the end of each level-(k−1) period, carrying the mean verdict of that
period as their weight.

### Assumptions (all measurable)

- **(A1) Input sensitivity.** ‖Φ(θ; Y + E, a) − Φ(θ; Y, a)‖ ≤ G_Φ ‖E‖ for all θ, a and
  admissible Y, E. (Measured: `estimate_adaptation_lipschitz`, first return value.)
- **(A2) State and anchor sensitivity.** ‖Φ(θ; Y, a) − Φ(θ′; Y, a)‖ ≤ L_θ ‖θ − θ′‖ and
  ‖Φ(θ; Y, a) − Φ(θ; Y, a′)‖ ≤ L_a ‖a − a′‖. Write L := L_θ + L_a. (Measured: second
  and third return values.) The delta-rule decay and the proximal pull are what make
  L_θ < 1 possible: each fast step multiplies the deviation from the anchor by
  (1 − ηλ) before the gradient step, so over T steps the proximal part alone
  contributes a factor (1 − ηλ)^T.
- **(A3) Adversary.** A set 𝒜 of blocks is attacked; on b ∈ 𝒜 the receiver sees
  Y_b + E_b with ‖E_b‖ ≤ ε, and the data block is unchanged (pilot poisoning; the
  `where = pilots` setting). ρ_blk := |𝒜 ∩ window| / |window|.
- **(A4) Gate under attack.** Let p_rej be the fraction of attacked blocks the gate
  rejects. (Measured: `gate_reject_rate_attacked`.)

Paired trajectories. Fix the clean sequence (Y_b, Y_b^d) and the gate verdicts
of the clean run; run the receiver once on the clean sequence (states θ_b^c,
θ^{(k),c}) and once with the attack (θ_b^a, θ^{(k),a}). Define the displacements

    d_b := ‖θ_b^a − θ_b^c‖,      D_k(b) := ‖θ^{(k),a}_b − θ^{(k),c}_b‖.

## 2. Lemma 1 (fast-level displacement forgets geometrically)

Suppose the two runs accept and reject the same blocks (the case of A3, where
p_rej ≈ 0 in both runs, or any attacker that evades the gate). Let χ_b = 1 if block b
is attacked and accepted, else 0. Then for every b

    d_b ≤ L_θ d_{b−1} + G_Φ ε χ_b + L_a ‖a_b^a − a_b^c‖,

and, writing Δ_slow(b) := max_{k≥2} D_k(b),

    d_b ≤ Σ_{j≤b} L_θ^{b−j} ( G_Φ ε χ_j + L_a Δ_slow(j−1) ).                     (2)

*Proof.* If block b is rejected in both runs, θ_b = θ_{b−1} in both and d_b = d_{b−1}
≤ the right-hand side. If accepted, by the triangle inequality

    ‖Φ(θ_{b−1}^a; Y_b + E_b, a_b^a) − Φ(θ_{b−1}^c; Y_b, a_b^c)‖
      ≤ ‖Φ(θ^a; Y+E, a^a) − Φ(θ^a; Y, a^a)‖ + ‖Φ(θ^a; Y, a^a) − Φ(θ^c; Y, a^a)‖
        + ‖Φ(θ^c; Y, a^a) − Φ(θ^c; Y, a^c)‖
      ≤ G_Φ ‖E_b‖ χ_b + L_θ d_{b−1} + L_a ‖a_b^a − a_b^c‖,

and ‖a_b^a − a_b^c‖ = ‖Σ_k w_k (θ^{(k),a} − θ^{(k),c})‖ ≤ Δ_slow(b−1) since the w_k
are convex weights. Unrolling the recursion gives (2). ∎

## 3. Lemma 2 (consolidation is a convex combination)

For every k ≥ 2 and every consolidation instant, the post-consolidation level-k
state is a convex combination of its pre-consolidation state and the buffered
level-(k−1) states:

    θ^{(k)}_+ = (1 − s) θ^{(k)} + s Σ_j π_j θ^{(k−1)}_j,   π_j ≥ 0,  Σ_j π_j = 1,  0 ≤ s ≤ η^{(k)} ≤ 1.

*Proof.* If Σ_j γ_j ≥ 1, (1) is the above with π_j = γ_j/Σγ and s = η^{(k)}. If
Σ_j γ_j < 1, (1) reads θ^{(k)}_+ = (1 − η^{(k)}Σγ) θ^{(k)} + η^{(k)} Σ_j γ_j θ^{(k−1)}_j,
which is the above with π_j = γ_j/Σγ and s = η^{(k)} Σγ < η^{(k)}. ∎

Consequence (paired runs with equal verdicts): the displacement of a convex
combination is at most the same convex combination of displacements, so

    D_k(after) ≤ (1 − s) D_k(before) + s · max_j D_{k−1}(j) ≤ max{ D_k(before), max_j D_{k−1}(j) },  (3)

and by induction over k, with D_1 := d,

    D_k(b) ≤ max_{j ≤ b} d_j   for every k ≥ 2 and every b.                    (4)

## 4. Theorem 1 (retention certificate; Corollary 2.2 of the proposal, implemented form)

Let the attack occupy a window of W consecutive blocks, with equal verdicts in the
paired runs, let n(W) be the number of level-K consolidation instants inside the window
(n(W) = ⌊(b_0+W)/C_K⌋ − ⌊b_0/C_K⌋ ≤ ⌈W/C_K⌉ for a window starting at block b_0), and let
n_W := Σ_{b∈window} χ_b = ρ_blk (1 − p_rej) W be the number of attacked *and accepted*
blocks in it.

**(i) Structural part (no Lipschitz assumption).** With Δ_f^meas(W) := max over the
window of the paired fast-level displacement d_b,

    D_K(W) ≤ Δ_f^meas(W) · ( 1 − (1 − η^{(K)})^{n(W)} )  ≤  η^{(K)} Δ_f^meas(W) · n(W).      (5)

**(ii) Lipschitz part.** Under (A1)–(A2) with L := L_θ + L_a < 1,

    Δ_f^meas(W) ≤ Δ_f(W) := G_Φ ε · min{ 1, (1 − L_θ) n_W } / (1 − L),                  (5′)

so that D_K(W) ≤ η^{(K)} ρ_blk (1 − p_rej) ε G_Φ (1−L_θ) W n(W)/(1−L) for short windows and
D_K(W) ≤ η^{(K)} ε G_Φ n(W)/(1 − L) for long ones: the proposal's
η^{(K)} ρ_blk ε G (1 − p_rej) W / C_K with G := G_Φ/(1 − L), the Lipschitz constant of the
*block adaptation map* in place of the gradient's, and the (1 − p_rej) factor entering
through n_W in the saturating minimum.

*Proof of (i).* Level K consolidates n(W) times inside the window. Each time, by (3)
with D_{K−1} ≤ max_j d_j ≤ Δ_f^meas (using (4) for the intermediate levels),
D_K ← (1 − s) D_K + s Δ_f^meas with s ≤ η^{(K)}. Starting from D_K = 0 and iterating n(W)
times gives D_K ≤ Δ_f^meas (1 − (1 − η^{(K)})^{n(W)}) ≤ η^{(K)} n(W) Δ_f^meas. ∎

*Proof of (ii).* Let m_b := max_{j≤b} d_j. From (2) and (4),
d_b ≤ G_Φ ε Σ_{j≤b} L_θ^{b−j} χ_j + (L_a/(1−L_θ)) m_{b−1}. Since Σ_{j≤b} L_θ^{b−j} χ_j ≤
min{1/(1−L_θ), n_W} inside the window, taking the maximum over the window and
solving for m gives m ≤ G_Φ ε min{1/(1−L_θ), n_W} / (1 − L_a/(1−L_θ))
= G_Φ ε min{1, (1−L_θ) n_W} / (1−L) = Δ_f(W). Before the window d ≡ 0. ∎

Remarks. (a) The 1/C_K factor is the *only* place the slow level's period enters (through
n(W)); it is the retention mechanism, and it needs no regularity of the fast learner at
all: part (i) is a statement about the consolidation rule alone. (b) The gate enters
through n_W, i.e. through (1 − p_rej), and the fallback through the fact that rejected
blocks inject nothing (revert). (c) Both parts are deterministic; no distributional
assumption on the channel is needed. (d) Part (ii) needs L < 1. The measured constants
of the default configuration (Section 8) give L_θ = 0.86, L_a = 0.35, L = 1.20: the
random-probe estimates do *not* certify the contraction, so for the default receiver we
report part (i) with the measured Δ_f^meas, and part (ii) as the statement of what a
more strongly anchored configuration (larger `prox_lambda`, which lowers L_θ) buys.
The measured fast displacement is nonetheless of the size the geometric sum predicts
from L_θ alone (ε G_Φ /(1 − L_θ) = 1.05 × 5.21 / 0.14 ≈ 39 against measured maxima of
16–34), which is consistent with L_a acting on a slowly moving anchor rather than
compounding every block. (e) A sweep of the proximal weight
(`docs/certificate_constants_lambda.json`; λ = 0.5 / 1 / 2 / 4 gives L_θ = 0.86 / 0.54 /
0.40 / 0.38 and L_a = 0.35 / 0.54 / 0.82 / 1.01) shows that L_θ + L_a ≈ 1 is structural:
the proximal fast map drives θ toward the anchor, so what it forgets about its own
past (1 − L_θ) it inherits from the anchor (L_a). The joint system is (approximately)
*non-expansive*, not contractive, and the appropriate statement is the injection-count
bound: if L_θ + L_a ≤ 1 then, by the same convexity argument as Lemma 2 applied to
Lemma 1, d_b ≤ max{d_{b−1}, Δ_slow(b−1)} + G_Φ ε χ_b, hence with (4)
max_{j≤b} d_j ≤ G_Φ ε n_b, where n_b is the number of accepted attacked blocks so far.
This is the second branch of Δ_f(W) without the (1 − L_θ)/(1 − L) factors; it needs no
contraction, only non-expansiveness, and it is what the measured constants support
(within the probe error: the measured sums are 1.08–1.39).

### Numerical check (`scripts/certificate_check.py`, `docs/figures/fig_e5_certificate_bound.png`)

Paired A3 runs (E5, 300 attacked blocks, p_rej = 0, 3 seeds), η^{(K)} = 0.5:

| C_K | Δ_f^meas (end of window) | max_W D_K(W) / bound (5) | measured slope of D_K per block |
|---|---|---|---|
| 8 | 33.4 | 0.94 | 0.084 |
| 32 | 17.2 | 0.53 | 0.029 |
| 128 | 15.9 | 0.26 | 0.0083 |

The structural bound (5) holds at every W for every C_K, is nearly tight for C_K = 8
(the slow level becomes a running average of the fast level), and the measured slopes
scale as 1 : 0.35 : 0.10 against the 1 : 0.25 : 0.0625 of pure 1/C_K (∝ C_K^{−0.85};
the deviation is Δ_f^meas itself decreasing with C_K, because a slower anchor moves less
and the fast level is pulled back harder).

## 5. Theorem 2 (corruption-robust dynamic regret; Theorem 2.1 of the proposal)

Let ℓ_b(θ) be the per-block detection loss of the receiver with fast state θ on the
clean data block, G_ℓ-Lipschitz in θ. Define the dynamic regret of a run against a
comparator sequence u_b as R_T(u) = Σ_b ℓ_b(θ_b) − ℓ_b(u_b).

Under the hypotheses of Theorem 1(ii) applied to the whole horizon of T blocks
(n_T attacked and accepted blocks in total, L < 1), the attacked run satisfies

    R_T^{adv}(u) ≤ R_T^{clean}(u) + G_ℓ Σ_b d_b ≤ R_T^{clean}(u) + G_ℓ T Δ_f(T),           (6)

and, when the fast level is not anchored (L_a = 0, e.g. `prox_lambda = 0`), the
sharper R_T^{adv}(u) ≤ R_T^{clean}(u) + G_ℓ G_Φ ε n_T/(1 − L_θ), linear in the number
of accepted corrupted blocks rather than in T;

and a receiver that detects with the level-k state (the fallback detector)
satisfies R_T^{adv,(k)}(u) ≤ R_T^{clean,(k)}(u) + G_ℓ Σ_b D_k(b) with, by (5) applied
to every prefix,

    Σ_b D_k(b) ≤ Δ_f(T) Σ_b (1 − (1 − η^{(k)})^{⌊b/C_k⌋}) ≤ min{ T,  η^{(k)} T² / (2 C_k) } · Δ_f(T),   (6′)

i.e. the adversary's contribution to level k is divided by C_k until it saturates.

*Proof.* R_T^{adv} − R_T^{clean} = Σ_b [ℓ_b(θ_b^a) − ℓ_b(θ_b^c)] ≤ G_ℓ Σ_b d_b by the
Lipschitz property, and Σ_b d_b ≤ T max_b d_b ≤ T Δ_f(T) by Theorem 1(ii).
Without the anchor (L_a = 0) the unrolled recursion (2) is d_b ≤ G_Φ ε Σ_{j≤b} L_θ^{b−j} χ_j;
summing over b and exchanging the order of summation gives Σ_b d_b ≤ G_Φ ε n_T/(1−L_θ).
(6′) follows from (5) applied to each prefix of
length b, with (1 − (1−η)^n) ≤ min{1, ηn}. ∎

The clean regret R_T^{clean}(u) is the dynamic regret of the fast learner alone;
for the convex (last-layer) case it is O(√(T(1+P_T))) by the standard
Zinkevich / Mokhtari et al. bound with a bounded step size (the surprise-driven
rate η_b = η_max · 2r_b/(1+r_b) ∈ (0, 2η_max) changes only constants); for the
full-MLP receiver we do not claim a rate for the clean term and report it
empirically (E2). What the theorem adds — and what the experiments test — is the
*additive, (1 − p_rej)-scaled, 1/C_k-divided* adversarial term.

## 6. Proposition 1 (CRC gate; Proposition 2.3 of the proposal)

A sub-block of L symbols carries an r-bit CRC. Let p be the post-adaptation
symbol error probability of the detector under test, assumed i.i.d. across the
symbols of a sub-block, and let the CRC syndrome of an erroneous sub-block be
uniform (the usual random-error model). Then

    P(pass | p) = (1 − p)^L + 2^{−r} (1 − (1 − p)^L).                               (7)

With n sub-blocks per block, the pass fraction F satisfies, by Hoeffding,
P(|F − P(pass|p)| ≥ t) ≤ 2 exp(−2 n t²).

*Gate rule.* G2 compares F_nn (fast level) with F_ref (the better of LMMSE and the
anchor detector on the same block) through F_nn / F_ref < τ_2, with

    τ_2 = (1 − p_ref − δ)^L / (1 − p_ref)^L,     δ = max{ δ_min, ρ_rel p_ref }       (8)

(`g2_slack_mode = relative`; the `absolute` mode is δ ≡ δ_abs, τ_2 = (1 − δ_abs)^L
up to the 2^{−r} term, which is the v1 rule). Inverting (7) at F_ref gives p_ref,
and (8) is exactly the statement "reject when the fast level's symbol error
probability exceeds the reference's by more than δ", up to the Hoeffding
fluctuation t. *Proof:* (1−p)^L is decreasing in p, so F_nn/F_ref < τ_2 ⟺
p_nn > p_ref + δ for the noiseless pass probabilities; the 2^{−r} term is ≤ 2^{−8}
and is absorbed into δ_min. ∎

*Consequence for A1.* An availability attacker whose poisoning raises the
post-adaptation SER by more than δ is rejected with probability ≥ 1 − 2exp(−2nt²)
where t is the gap between (7) at p_ref + δ and at the attacked p; with
n = 781 sub-blocks per block (50 000 bits, QPSK, L = 32) and δ = 0.01, t ≈ 0.2 and
the failure probability is below 10^{−60}: the CRC gate is essentially
deterministic against any attack that achieves its availability objective. An
attacker that keeps p ≤ p_ref + δ causes, by definition, at most δ of SER. This
is the dichotomy exploited by the design: either the attack is harmless or it
is rejected. The relative slack (8) makes δ scale with the operating point, so
the same dichotomy holds at SER 10^{−3} (COST2100, high SNR) where a fixed
δ = 0.01 is 30× the clean SER (`docs/RESULTS.md`, COST2100 sections).

## 7. Proposition 2 (residual gate G1 and model mismatch)

Let H be the (LS) channel estimate of the block and ŝ_nn, ŝ_ref the hard decisions
of the fast level and the reference. G1 uses the ratio
r_nn / r_ref, r = mean_n ‖y_n − H ŝ_n‖². Write y_n = H s_n + ν_n + m_n where m_n is
the model-mismatch term (PA nonlinearity) and ν_n noise. For a decision ŝ with
symbol error pattern e = ŝ − s,

    r = mean ‖H e_n‖² − 2 mean Re⟨H e_n, ν_n + m_n⟩ + mean ‖ν_n + m_n‖².

The last term is common to the numerator and the denominator; the cross term has
zero mean when ν is independent of the decision errors and is O(1/√N) by
concentration. Hence r_nn/r_ref ≈ (E_nn + σ²_eff)/(E_ref + σ²_eff) with
E = mean ‖H e_n‖² the decision-error energy and σ²_eff = σ² + mean‖m‖²: the ratio
is monotone in the excess error energy of the fast level over the reference and
is *invariant* to the mismatch level except through the additive σ²_eff, which only
compresses the ratio toward 1 (it does not create false alarms). This is why G1 is
evaluated as a ratio against a reference computed on the same block and normalised
by its clean running level. ∎

## 8. What is measured, and where

| Constant | Meaning | Measured by |
|---|---|---|
| G_Φ | input sensitivity of the block adaptation map | `theory.bound.estimate_adaptation_lipschitz` |
| L_θ, L_a | state / anchor sensitivity of the block map | same |
| ε | A3 per-block budget `a3_eps_small · ‖Y_p‖` | `scripts/certificate_check.py` |
| p_rej, α | gate rejection of attacked / clean blocks | run records (`gate_reject_rate_attacked`, `gate_false_reject_rate_clean`), ROC in `scripts/gate_roc.py` |
| η^{(K)}, C_K | config | `citadel.level_lr`, `citadel.periods` |
| D_K(W) | paired level-K displacement | E5 records (`paired_disp`), `scripts/analyze_e5.py` |

Measured on 10 clean blocks of the E5 configuration (`docs/certificate_constants.json`):
G_Φ = 5.21 (max; mean 3.13), L_θ = 0.86 (max; mean 0.76), L_a = 0.35 (max; mean 0.32),
ε = 1.05, and the single-gradient constant of the proposal's statement G_grad = 2.96
(max; mean 0.83). The random-probe estimates are lower bounds of the true suprema; the
certificate is therefore reported as "with the measured constants", and the empirical
check (measured D_K below bound (5) at every W, and the 1/C_K scaling of the slope) is
what supports the theorem numerically.
