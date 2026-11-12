# Revision plan: every item of the reviewer audit

## Status after the campaign (6 Nov 2026)

All runs of the reduced campaign below finished: 52 on the cloud machine and the laptop's share,
0 failed (records in `results/rev_*`, logs in `logs/`). Every number of the revised manuscript is
computed from these records by `python scripts/revision_numbers.py`; the paper is built with
`make paper`. Items whose outcome differs from the plan:

* H3 abstain: implemented and run, but it locks on clean runs (statistics updated on accepted
  blocks only); reported as not working.
* H4 streak recovery and B3 denial: the denial spoof did not trip the gates, and streak recovery
  had no measurable effect; reported as such.
* D5 16-QAM: Citadel-Rx fails (the network is worse than LMMSE, the gates reject 97% of clean
  blocks); reported and analysed.
* D2, D3, D7, D8: not done (stated in Sec. VII of the paper).

The status column of the tables below is the plan as written before the campaign.

## Second campaign (6-8 Nov 2026): closing the reduced and open items

`scripts/revision_fast.py --campaign 2` (shards `cloud`, `windows`) and `--campaign 3` (shards
`cloudx`, `cloudy`, `cloudz`, new features). Seeds are only added inside the pre-registered test set;
the new choices (abstain threshold, second-backbone tuning) are fixed on seeds 0-2 by
`scripts/freeze_rev2.py` before any test run of those features.

Compute: the queues of the cloud machine and the Windows laptop were longer than the time left, so
`scripts/assign_pool.py` handed every unfinished run (except the helper machine's, `--campaign 4`,
and the long runs already started on the cloud) to six further 4-core cloud machines
(`--campaign 5`, shards `pool1`-`pool6`, assignment in `configs/pool_assign.json`). All runs of one
seed and receiver go to one machine, which also runs their clean twins (`results/rev_clean_poolK`),
so every attacked run is still paired with a twin from its own machine; `configs/claims.json` makes
the machines that held these runs skip them. Run names, settings and seeds are unchanged.

Corrections made in the second campaign (adversarial review of the new code and of the first
records). The first three were made before any of the affected test runs, the last four after test
runs, which are named here and disclosed in the response letter:
* UMi drops: 1 ms blocks (one NR slot at 15 kHz over 150 PRBs, the paper's block of 25,000 symbols)
  instead of 5 ms, at which the channel changed by 24% per block (synthetic model 3.5%); the
  power-control target is fixed by the model (cell-edge NLoS user without shadowing), and the
  attacker's budget is a user's maximum power through its own channel in every block.
* G2 under LDPC: the pass fraction of decoded code blocks is replaced by the virtual pass fraction of
  the raw SER on decoder-verified symbols, so the design rule holds.
* Per-user gating uses the relative CRC slack of the block gate.
* Abstain: the third version (residual on CRC-verified symbols) replaces the second, whose
  statistic followed the reference's decision errors after a legitimate redraw (3 test runs of the
  second version, A4 at alpha = 0.25 on seeds 10-12, exist and are not reported; the third version
  is therefore also tested on fresh seeds 15-19).
* Coded scene: NR data scrambling of the coded bits (TS 38.211 Sec. 6.3.1.1). Without it the
  all-zero codeword, whose CRC-24A is zero, passes the check, and the first coded runs kept constant
  detector outputs through the CRC selection (blocks with SER 0.996 and BLER 0). They are renamed
  d23s_* (pool7, pool8) and the d23_* runs are dropped; no CRC-8 record has such a block.
* C5: drift detection and median-of-means ran first (P2, `results/rev_p2`) with their reference 300
  epochs and learning rate 5e-3, because `ONLINE_BASED` in `scripts/revision_fast.py` omits them;
  they are rerun with online DeepSIC's tuned setting (`p2t_*`, `results/rev2_p2_tuned`), which the
  tables use; the first runs are given in the response letter (keys `p2u.*`).
* D4: the SED profile is stretched over the array (`channel.sed_stretch`); unstretched, 99% of the
  energy of an 8 x 32 array falls on 9 antennas. The change was made after test runs
  with the unstretched profile (8 x 32: seeds 10-14, `results/rev2_arrays`; 4 x 16: seeds 10-11,
  `results/rev_p6_arrays`, whose results were in `paper/numbers.tex` before the change); they are
  not in the tables and are disclosed in the response letter (keys `sc.unstr.*`). The unstretched
  runs not yet made were dropped (`configs/claims.json`, "dropped").

| Item | Second campaign | Status |
|---|---|---|
| E2 seeds | 5 seeds (10-14) for every experiment that had 2-3 except A3* and the first abstain version (2); 10 at the headline cell; the long clean horizon has 2 seeds, the sensitivity test 1 | done |
| B1 | physical attacker M = 1, 2, 4; CSI error 0.1 and 0.01 through the true channel | done (Table attacks) |
| B2 | A4 at 20 PGD steps (alpha = 0.25), 5 seeds | done (Table refdeg) |
| B3, H4 | denial by strong poisoning during a channel redraw, with and without streak recovery | done (Table deny2) |
| B5 | accepted drift (A3* at 5%) over 900 of 1000 blocks, paired snapshots | done (Table retention) |
| D2 | NR LDPC code blocks with NR scrambling (Sionna 2.2); G2 on decoder-verified symbols | done (Table umi): the defence fails, mechanism reported |
| D3 | 38.901 UMi drops with the attacker at 35, 75, 150 m at a user's maximum power | done (Table umi) |
| D4 | 4 x 16 and 8 x 32 with the stretched SED profile, 5 seeds | done (Table scenarios) |
| D7 | 2000-block clean horizon (Citadel-Rx, online DeepSIC) | done (Sec. VI-E) |
| D8 | second backbone: joint-symbol detector (Citadel-Rx, online, CRC-Rollback) | done (Table joint) |
| D9 | multiply-accumulates per block (`scripts/flops.py`); no GPU measurement | done (Sec. VI-H) |
| E5 | x0.75 and x1.5 for the eight settings; a two-setting grid (CRC slack x G1 slack) | done (Table sensitivity) |
| A6 | hill-climbing estimate of G_Phi, random-probe L_theta, L_a on three channel families | done (Remark 1) |
| H3 | abstain, final version (residual on CRC-verified symbols); A4, A1, redraw, SNR drop; seeds 10-14 and fresh 15-19 | done (Tables refdeg, text): not usable, mechanism reported |
| H5 | drift guard against the accepted 5% drift | done (Table retention) |
| H7 | per-user gating against a single-user attack (A2) and A1 | done (Table peruser): no gain, mechanism reported |

Status key: **done** = implemented and tested in the code; **run** = in `scripts/revision_campaign.py`
(results arrive after the GPU campaign); **text** = manuscript edit, done in the final pass with the
campaign's numbers; **deferred** = stated as a limitation, with the reason.

## Decisive early result (C1)

The simplest receiver that uses the CRC, online DeepSIC + CRC gate (G2 at the fixed slack 0.01,
judged against LMMSE alone, no CRC selection) + rollback to the last accepted weights,
**fails** under white-box A1 at SIR 0 dB (pilot runs, seeds 0-1): window SER 0.26-0.47,
post-attack SER 0.29-0.55, never recovers, and 55-58% of clean blocks are falsely rejected. Block
traces show the mechanism: one poisoned update leaks through (at SIR 0 dB the pilot poison also
degrades the LMMSE reference, so the ratio test looks normal), the leaked state becomes the state
rollback returns to, and every later clean update starting from it is rejected. Rollback has an
absorbing state; the slow memory makes a leak transient (a gamma-weighted 1/C_k share, a clean
anchor to fall back on, and a proximal pull back). This is the argument for the hierarchy the
audit asked for (C1, G2). The previous K=1 ablation (0.788) never reverted or fell back at all
(both were guarded by K > 1); this is fixed and the ablation is re-run.
The K=1 ablation keeps Citadel-Rx's gates, relative slack and CRC selection, so it is the comparison
that differs from Citadel-Rx in the memory alone; CRC-Rollback also has a fixed slack and no CRC
selection.

## Reduced campaign (GPU workstation unavailable)

The experiments run on a MacBook (M4, 10 cores) and a 4-core cloud machine with
`scripts/revision_fast.py` (instructions: `docs/RUN_LAPTOP.md`). Every item above keeps an
experiment; the reductions against the full plan (`scripts/revision_campaign.py`) are listed here
and are stated in the paper wherever the numbers are used.

| Group | Full plan | Reduced campaign |
|---|---|---|
| P1 headline | 10 test seeds in every cell | 10 seeds at white-box SIR 0 dB; 3 seeds (10-12) at SIR -10 / +10 dB, transfer and jamming |
| P2 baselines | 3 cells x 5 seeds, L2-SP 4 weights | white-box SIR 0 dB only, 2 seeds; L2-SP weights 1e-3, 1e-2, 1e-1, 1 |
| P3 adaptive (B4) | 6 variants x 2 SIR x 5 seeds; strongest = PGD 100, 5 restarts, EOT 4 | unroll 10, soft gate, PGD 100 x 5 restarts at SIR 0 and 10 dB; unroll 50 and the combined attack (soft gate, unroll 10, PGD 50, 2 restarts, EOT 2) at SIR 0 dB; 2 seeds |
| P3 reference degradation (B2) | alpha 0.25 / 0.5 / 0.75 x SIR 0 / 10 x abstain on/off, 5 seeds | alpha 0.25 / 0.75 at SIR 0 dB x abstain on/off, 2 seeds, 6 PGD steps (the joint attack optimises over all 781 data sub-blocks: 4 min per attacked block at 20 steps) |
| P3 denial (B3, D6) | redraw / 6 dB drop, 5 seeds | same cells, 2 seeds |
| P3 physical (B1) | M = 1, 2, 4; CSI error 0.01, 0.1 | M = 1, 2; CSI error 0.1 at M = 2; 2 seeds |
| P3 knowledge (B6, B8) | SIR 0 and 10 dB, 5 seeds | SIR 0 dB, 2 seeds |
| P4 paired displacement | 5 seeds | 3 seeds |
| P5 ablations | 18 variants, 5 seeds | 10 variants (K = 1, K = 2, no gate, each gate alone, no anchor, no fallback, no selection, no clip), 2 seeds |
| P6 | N_d x N_p 3 x 3; 4x16 and 8x32; 16-QAM; 2 deployable variants; 3 seeds | N_d 1000 / 5000 x N_p 32 / 100 (the default 25000 / 100 is P1); 4x16; 16-QAM; both deployable variants; 2 seeds |
| P7 sensitivity | x0.5 / 0.75 / 1.5 / 2, heat map, 2 seeds | x0.5 and x2 for 8 parameters, 1 seed; heat map dropped |
| P8 | drift attack over 1000 blocks; 2000-block clean horizon (D7) | drift attack over 400 blocks (the horizon of the paper's A3 experiment), 4 variants, 2 seeds; D7 dropped |
| Baseline tuning (C5) | grid on seeds 0-2 | unchanged |
| Citadel-Rx calibration | 3 candidates + submitted configuration on seeds 0-2 | 3 candidates (the submitted configuration is the existing record) |

## A. Theory

| Item | Action | Status |
|---|---|---|
| A1 neither branch applies | "non-expansive" removed; Theorem 1 restated: (i) structural bound with measured fast displacement, (ii) contraction branch stated as conditional and not claimed, (iii) **new design bound** D_K(W) <= 2 kappa_K n(W) from the consolidation clip, holding for any attacker and any verdicts, with no measured quantity | done (code: `citadel.consol_clip`); text |
| A2 equal verdicts | extended structural bound for unequal verdicts, computable from logged consolidation weights (w, s, r, distance to mean); drawn for A1 as well as A3 | done (`paired_disp.py`); run P4 |
| A3 mis-stated contraction bound | replaced by Delta_f(W) <= G eps (1 - L^n_W)/(1 - L); n_W defined | text |
| A4 near-tautology | renamed "retention bound"; "certificate" removed; the design bound makes it attacker-independent by construction | text |
| A5 Theorem 2 vacuous | Theorem 2 dropped from the main text (kept as a remark for the convex last-layer variant) | text |
| A6 weak Lipschitz estimates | hill-climbing estimator over channel families, max and 95% quantile; the anchor-start variant has L_theta = 0 by construction | done (`lipschitz_strong.py`); run |
| A7 delta_min hand-set | derived slack: delta = max(z sigma, rho p_ref) with sigma the running std of the clean statistic floored by its binomial value, so it adapts to block length; candidate in calibration | done (`g2_slack_mode=derived`); run A; not selected: the calibration chose the relative slack (rho = 1, floor 2e-3, both from the first version), which does not adapt to block length |
| A8 G1 mismatch argument | assumption E[m_n e_n] = 0 stated; clean G1 distribution on the tanh channel reported | text + existing records |
| A9 notation | notation table; CRC slack renamed kappa, attacked fraction pi | text |

## B. Threat model and adaptive attacks

| Item | Action | Status |
|---|---|---|
| B1 unconstrained perturbation | rank-M physical attacker E = G X_a, M = 1, 2, 4, CSI error 0.01 / 0.1; full-rank kept as worst case; SIR mapped to power/distance in text | done; run P3 |
| B2 joint pilot + data | attacker A4: per-symbol power split alpha in {0.25, 0.5, 0.75}, joint PGD on pilots and data aimed at the emitted decisions behind soft gates; with and without the abstain state (H3); jamming-only controls at the same data power | done; run P3 |
| B3 denial of adaptation | fixed channel-estimate spoof on blocks 40-90 + abrupt redraw / 6 dB drop at block 50; with and without streak recovery (H4); online and LMMSE references | done; run P3 |
| B4 adaptive strength | unroll depth 2 / 10 / 50, PGD 100 with 5 restarts, BPDA soft-gate output-level objective with exact thresholds and EMA states, EOT over noise draws; strongest attack also against online DeepSIC; attack code released | done; run P3 |
| B5 optimal slow drift | A3*: planned as a drift toward a spoofed basin with a soft-gate term; as run (against Citadel-Rx) each attacked block is optimised for the soft-gate objective of the adaptive attacker alone (data loss of the decisions times the soft acceptance probability, plus a reward for acceptance), with no spoofed-channel term; energy 5 / 20 / 50%, 1000 blocks, with and without drift guard (H5) | done; run P8 |
| B6 transfer too narrow | grey-box: Citadel-Rx surrogate from another seed; query attacker on HARQ NACK feedback | done; run P3 |
| B7 knowledge vague | knowledge table (white-box, grey-box, transfer, query), synchronisation assumption | text |
| B8 budget includes noise | signal-referenced budget option; both definitions reported | done; run P3 |

## C. Missing baselines

| Item | Action | Status |
|---|---|---|
| C1 CRC + rollback | `crc_rollback`, `rollback_allgates`; K=1 fixed. Result above | done; run P1 (10 seeds) |
| C2 regularised online | L2-SP (4 weights), EMA teacher, EWC (Fisher from pre-training) | done; run P2 |
| C3 CRC-verified decision-directed | `dd_deepsic`; also H2 inside Citadel-Rx | done; run P2 (`dd_deepsic` only; H2 not run) |
| C4 TTA defences | CoTTA-style (teacher + stochastic restore), EATA-style (entropy filter + Fisher anchor) | done; run P2 |
| C5 under-tuned baselines | epochs {30, 100, 300} x lr {1e-3, 5e-3} x weight decay {0, 1e-4} on calibration seeds, best setting used at test | done; run A (drift detection and median-of-means first ran at 300 epochs and 5e-3 and were rerun with the tuned setting, see the corrections above; the method weights are defaults, not tuned) |
| C6 MedBN mislabelled | renamed "median-of-means gradient" | text |
| C7 robust LMMSE | Huber IRLS (and trimmed) channel estimate | done; run P2 |

## D. Experimental realism

| Item | Action | Status |
|---|---|---|
| D1 block length | N_d in {1000, 5000, 25000} x N_p in {32, 100, 200}; derived slack adapts to n (not selected; the runs use the relative slack) | run P6 |
| D2 NR link-level + LDPC | **deferred**: Sionna NR slot + LDPC + 16-QAM is several days of engineering and validation; stated as the main limitation | deferred |
| D3 attacker in the scene | SIR translated to transmit power and distance under 3GPP UMi path loss (analytic); full scene **deferred** with D2 | text / deferred |
| D4 N > U | 4 x 16 and 8 x 32 | run P6 |
| D5 higher order | 16-QAM at 20 dB (same hidden width as QPSK) | done; run P6 |
| D6 abrupt change, no attack | redraw and 6 dB drop at block 50 | done; run P3 |
| D7 long horizon | 2000 clean blocks, cosine and Jakes | run P8 |
| D8 second backbone | **deferred**; the claim "applies unchanged" is deleted (F13) | deferred |
| D9 compute | 30-step and last-layer variants; per-block time reported; GPU latency/FLOPs in text | run P6; text |

## E. Statistics and protocol

| Item | Action | Status |
|---|---|---|
| E1 correlated blocks | moving-block bootstrap with measured decorrelation length (1-4 blocks measured, blocks of 5-8); seed-level exact tests; "every p < 0.001" rewritten with test, unit and n | done (`revision_stats.py`) |
| E2 too few seeds | 10 test seeds on headline cells, 5 elsewhere | run P1-P5 |
| E3 easy part of the fade | attack window randomised per seed; excess SER (attacked minus matched clean run) is the primary metric | done; run |
| E4 thresholds after test | calibration seeds 0-2 with a pre-registered automatic selection; all reported tables on fresh seeds 10-19 | done; run |
| E5 sensitivity | one-at-a-time x0.5 / 0.75 / 1.5 / 2 for 8 parameters, plus G1 x CRC-slack heat map | run P7 |
| E6 intervals and counts | Wilson intervals with k/n for every rate | done |
| E7 Fig. 3c | paired displacement of every level and the anchor under A1, mean over seeds with bands | done; run P4 |
| E8 Holm family | families listed with hypotheses and size | done |

## F. Claim consistency

All fourteen sentences (F1-F14) are rewritten in the final pass so that every abstract and
conclusion number points to one table cell of the revised tables (test seeds). "halves the SER"
is re-checked against the tuned online DeepSIC (C5). **Status: text.**

## G. Novelty, positioning, references

| Item | Action | Status |
|---|---|---|
| G1 missing prior work | pilot contamination / active attacks, CRC-aided online training (ViterbiNet / DeepSIC line), EATA, CoTTA, SAR, RoTTA, persistent TTA, L2-SP, EWC, mean teacher, adaptive-attack methodology, adversarial PHY learning, complementary learning systems; every reference verified at its source before it is cited | text |
| G2 reframing | lead with the principle; C1 result supports the hierarchy | text |
| G3 Proposition 1 | presented as a design rule | text |
| G4 Table I rows | pilot-spoofing detection, CRC-aided online training, EATA/CoTTA | text |

## H. Method upgrades

| Item | Implementation | Status |
|---|---|---|
| H1 contraction by design | fast start from the anchor (L_theta = 0), update radius R, consolidation clip kappa (clean p99: 8.5, 4.5) | done; calibration candidate |
| H2 CRC-verified labels | `receiver.dd_weight` inside Citadel-Rx | implemented, not run: `dd_weight` is 0 in every Citadel-Rx record; evaluated only as the baseline `dd_deepsic` (C3) |
| H3 abstain | reference pass rate or residual far from its running level -> no consolidation | done; run with B2 |
| H4 streak recovery | after k rejections, refit from the anchor on CRC-verified data, accept if it verifies better | done; run with B3 |
| H5 drift guard | pull of the slowest level toward pre-trained weights | done; run with B5 |
| H6 CRC selection | per (sub-block, user) first passing among fast, anchor, LMMSE | done; in all candidates |
| H7 per-user gating | per-user CRC verdicts, revert and fall back per user | done |

## I. Writing and reproducibility

| Item | Action | Status |
|---|---|---|
| I1 repo URL | rename the GitHub repository to `Citadel-Rx` (GitHub redirects the old URL); owner action | user |
| I2 algorithm box | Algorithm 1 | text |
| I3 notation | table | text |
| I4 C_K configurations | full period vectors (1,2,8), (1,8,32), (1,32,128) | text |
| I5 hyperparameter provenance | table: value, derived / tuned / fixed, on which data | text |
| I6-I8 SED, SER definitions, informal wording | defined; wording replaced by measured statements | text |
| I9-I12 table density, figure, abstract numbers, pages | as advised; proofs and full tables to a supplementary file | text |
| I13 packaging | one-command campaign and report; lock file; Zenodo DOI is an owner action | partly done / user: three commands re-run the campaigns and `make paper` rebuilds the numbers, figures and paper; no lock file (`requirements.txt` gives lower bounds) |
| I14 acknowledgements | added | text |
