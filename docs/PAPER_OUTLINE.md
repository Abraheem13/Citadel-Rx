# Manuscript skeleton (target: IEEE TWC; alternates JSAC special issue / TIFS)

Working title: *Citadel-Rx: Continuum-Memory Test-Time Learning Makes
Adaptive Neural Receivers Certifiably Hard to Poison*

Each section lists the claim, the evidence that backs it, and the record /
script that regenerates it. A claim without a record does not go in.

## I. Introduction
Claim: online and meta-learned receivers turn the pilot stream into a
training set; the only attack paper shows meta-learned receivers are the
most vulnerable and calls for secure architectures; no defence exists.
Evidence: §1.3 of the proposal; `docs/RESEARCH_NOTES.md` §2 (two targeted
searches, no defence found). Figure 1: mechanism diagram (`Fig. 2.1`).

## II. System model and threat model
As proposal §2.3–2.4. Budget defined as SIR over the pilot block
(`attacks/pilot_poisoning.py::Attacker.budget`). Attacks A1/A2/A3/adaptive +
equal-power jamming control.

## III. Citadel-Rx
III-A levels and periods aligned with coherence (`receivers/citadel.py`);
III-B DGD fast rule and surprise-generated rate; III-C the three gates with
statistics *relative to the model-based reference on the same block*
(`gates/physics.py`, derivation of τ₂ from Prop. 2.3); III-D gated
consolidation (Eq. 2.6′) and proximal anchoring; III-E gated fallback
(rejected block → detect with the slow projection). Cost table (III-F) from
`mean_t_rx_s` in records.

## IV. Theory
Theorem 1 (corruption-robust dynamic regret), Corollary 1 (retention
certificate), Proposition 1 (CRC gate) — `docs/THEORY.md`. Figure 3:
analytical per-level adversary term (`theory/bound.py`). Figure 4: measured
level-K displacement vs certificate (E5, `run.save_params`).

## V. Experiments
| Figure/Table | Claim | Experiment | Script |
|---|---|---|---|
| Table II clean parity | Citadel ≤ 0.2 dB from the best receiver without attack, across SNR and Doppler | E2 | `sweep.py e2`, `paper_numbers.py` |
| Fig. 5 SER vs block | under A1 Citadel stays on its clean trajectory; online/meta collapse; meta never recovers | E3 | `fig_ser_vs_block_a1_sir*.png` |
| Fig. 6 Δ_dB vs SIR | degradation reduced by ≥ 60 % at SIR 0 dB; equal-power jamming control | E3 + e3snr | `table_degradation_db.md` |
| Table III ablations | pre-training, single memory, gate subsets, periods, DGD, surprise, anchoring | `sweep.py ablate` | |
| Fig. 7 gate ROC | rejection vs false rejection per gate | E3 records | |
| Fig. 8 A2 per-user SER | G3 catches physically implausible drift | E4 | |
| Fig. 9 slow-level displacement vs W | empirical slope ∝ 1/C_K, inside the certificate | E5 | |
| Table IV coded BLER (Sionna) | gains survive LDPC + real TB-CRC at 30/60/120 km/h | E6 (GPU) | |
| Fig. 10 adaptive attacker | gate-aware attacker partially defeats G1; G2+G3 hold | E7 | |

Status (24 Oct): Fig. 5 and the first rows of Table III exist for one seed
(`docs/RESULTS.md`). Everything else: code paths exist, runs pending.

## VI. Related work / VII. Conclusion
Positioning vs. TTA-poisoning defences in vision (do not transfer: MedBN row
of Table III), Byzantine-robust learning (needs individual vectors),
drift-detection receivers (adapt-less trade-off: Table III).

## Reviewer-proofing checklist
- [ ] every number traceable to a JSON record and commit hash
- [ ] 3 seeds with std everywhere; 5 seeds for the headline
- [ ] nonlinear + COST2100 + Jakes channels, 4×4 and 8×8
- [ ] transfer attacker as well as white-box
- [ ] adaptive attacker that knows the defence (E7), reported honestly
- [ ] equal-power jamming control (poisoning vs jamming at the same energy)
- [ ] latency / FLOPs per block vs Meta-DeepSIC
- [ ] Wu et al. numbers verified at the primary source
