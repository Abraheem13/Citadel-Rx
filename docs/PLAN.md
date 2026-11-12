# Working plan (code 2 days → run → debug → run)

## Day 1 (done in this session)
- [x] Literature / code audit → `docs/RESEARCH_NOTES.md`
- [x] Functional DeepSIC backbone identical to the TWC 2023 reference
- [x] Baselines: LMMSE, online DeepSIC, Meta-DeepSIC, drift-detection, MedBN-style, single-memory Titans
- [x] Citadel-Rx: levels, DGD fast rule, surprise rate, gates G1–G3, gated consolidation, re-anchoring
- [x] Attacks: A1 white-box/transfer, A2, A3, gate-aware adaptive, equal-power jamming control
- [x] Runner, metrics (SER/BER/BLER, Δ_dB, recovery), JSON records, sweeps, paper_numbers
- [x] 24 unit/pipeline tests passing on CPU
- [x] Smoke results (30 blocks, 4x4 QPSK, 10 dB, cosine fading):
      online DeepSIC clean ≈ LMMSE floor (both track the fade);
      A1 @ SIR 0 dB: 2 % → 85 % SER, A1 @ SIR 10 dB: 4 % → 30 % SER, recovery > 10 blocks

## Day 2 (in progress)
- [x] Citadel vs online/meta under A1 at SIR {0, 5, 10} (1 seed): Citadel stays on its clean trajectory,
      recovery 0 blocks, 93–97 % of attacked blocks rejected, ≤ 2 % false rejection → `docs/RESULTS.md`
- [ ] 3 seeds, SIR −10/−5, transfer attacker, all seven receivers
- [ ] Clean parity sweep (E2) across SNR and both fading modes; fix the periods if parity costs > 0.2 dB
- [ ] Gate ROC (rejection vs false rejection) from E3 records
- [ ] E7 adaptive attacker; E4 A2; E5 certificate slope
- [ ] Nonlinear + COST2100 runs of E1/E3 (comparability with the attack paper)
- [ ] Learned surprise head and learned adaptable mask (ablations)
- [ ] Measured Lipschitz constant G in run records; certificate vs. measured displacement plot

## On the GPU box
- [ ] E6 Sionna PUSCH (`channels/sionna_pusch.py`): wire DeepSIC soft outputs into LDPC/TB-CRC
- [ ] E4/E8 DeepMIMO trajectories (`channels/deepmimo.py`)
- [ ] 8x8, 3 seeds everywhere, full 100–400 block windows

## Laptop budget
One 100-block run ≈ 4–6 min single-threaded (CPU). The full E3 sweep
(7 receivers × 5 SIRs × 2 knowledge + jamming) × 3 seeds ≈ 240 runs ≈ 20 h on
4 cores; run E3 with `--receivers citadel meta_deepsic online_deepsic` first.
