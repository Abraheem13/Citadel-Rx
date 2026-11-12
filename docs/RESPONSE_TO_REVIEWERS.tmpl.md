# Response to the reviewer audit

Section, table and figure numbers in this letter refer to the extended version of the manuscript
(`paper/extended/main_extended.pdf`); the journal version (`paper/main.pdf`) condenses it to ten pages.

Every item of the audit is listed with what changed and where. Section, table and equation names
refer to the revised manuscript in its extended version (`paper/extended/main_extended.tex`); the submitted version is
`paper/main_submitted.tex`. Every number below is filled in by `scripts/fill_response.py` from
`paper/numbers.tex`, which `scripts/revision_numbers.py` computes from the run records in
`results/`; the paper and this letter therefore always agree. The experiments are listed in
`scripts/revision_fast.py`, their machines and the corrections made during the revision in
`docs/REVISION_PLAN.md`. The revision has two campaigns: the first (headline cell with ten test
seeds, most other experiments with two or three) and the second, which gives five seeds (10-14) to
every experiment that had two or three except A3* and the first abstain version (two seeds), and
adds the coded 3GPP scene, a second backbone, larger arrays, longer horizons and the new attack and
defence variants; the sensitivity test has one seed (E2).

A correction found during the revision, before any test result: the consolidation rule of the
first version divided the gated sum of buffered states by max(1, sum of verdicts). When most blocks
of a period are rejected, which is what happens under attack, this pulls the slow level toward the
origin, so Lemma 1 (convex combination) did not hold for the implementation. The revision uses the
normalised gated mean (Eq. (consol), `citadel.consol_mean=normalized`, `tests/test_consolidation.py`);
every revision result uses it.

Corrections made in the second campaign (details in `docs/REVISION_PLAN.md`). Made before any test
run they affect: the 3GPP drops use 1 ms blocks (one NR slot), not 5 ms. Made after test runs of the
version they replace: the coded link scrambles the coded bits as NR does (without it the all-zero
codeword passes the CRC-24A check; the first coded runs had this flaw and are not reported); the larger
arrays use the SED profile stretched over the array (unstretched, 99% of the energy of an 8 x 32
array falls on 9 antennas), adopted after test runs with the unstretched profile, whose results are
given under D4; drift detection and median-of-means ran first with their reference 300 epochs and
learning rate 5e-3 instead of the tuned setting of online DeepSIC and are rerun with it (C5); and the
statistic of the final abstain state was adopted after first test runs of its second version (A4,
seeds 10-12), so it is also reported on seeds 15-19, which no choice has touched. The analysis
matched some attacked runs to no clean twin when run as a script (fixed; first-campaign numbers
unchanged).

What the evaluation changed in the manuscript (all from test-seed records; no setting was
changed after the test runs except as listed above):

* The mechanism of the CRC-Rollback failure is measured, not argued: its only reference, LMMSE on
  the least-squares estimate from the poisoned pilots, passes {{c1.crc.refatt}} of the CRCs on
  attacked blocks against {{c1.crc.refcln}} on the clean twin, so the first attacked block is
  accepted on {{c1.crc.first0}} of {{c1.crc.nseeds}} seeds; at the end of the run it is still at
  {{c1.crc.endex}} excess SER. Citadel-Rx's reference (the better of LMMSE and the anchor detector on
  the slow memory) passes {{c1.cit.refatt}} vs {{c1.cit.refcln}} (Sec. VI-B). CRC-Rollback differs from
  Citadel-Rx in more than the memory (fixed slack, no CRC selection; C1); Citadel-Rx with one
  memory (the K = 1 ablation: the same gates, relative slack and CRC selection) fails as well
  ({{ab.K1.excess}}).
* Most of the clean-SER gain over online DeepSIC ({{sel.share}}%) comes from the per-sub-block CRC
  selection, not from the memory.
* The receiver fails where its network is worse than LMMSE: at 16-QAM (network {{qam.passnn}} vs
  LMMSE {{qam.passref}} CRC pass fraction on clean blocks, {{qam.frej}}% clean blocks rejected) and in
  the coded 3GPP scene (fast-level virtual pass {{d23m.d75.nncln}} vs reference {{d23m.d75.refcln}};
  {{d23.citadel.d75.frejk}} clean blocks rejected), where no receiver is protected. Both are in the
  results, the discussion and the abstract.
* Neither version of the abstain state is a usable defence (H3 below); per-user gating does not
  isolate a single-user attack (H7 below).
* Corrections of fact: d = 67 632 adaptable parameters for 4x4 QPSK (the submitted text said
  15 628); the consolidation clip rarely binds on clean runs ({{clip.cln}} consolidations) rather
  than never.

## A. Theory

| Item | Change | Where |
|---|---|---|
| A1 neither branch applies | "non-expansive" deleted. Theorem 1 is a retention theorem with (i) a design bound D_K <= 2 kappa_K n(W) from the consolidation clip, which needs no measured quantity and holds for any attacker and any verdicts, and (ii) the structural bound for unequal verdicts. The contraction branch is a remark, stated as not applying because the measured joint constant exceeds one | Sec. IV, Thm. 1, Remark 1 |
| A2 equal verdicts | Extended structural bound with the normalised weights, the steps actually taken (after the clip) and the clean buffer radius; proof in the text; evaluated on paired trajectories of A1 (5 seeds: D_K {{ret.p4sir0.DK}} vs structural {{ret.p4sir0.struct}} and design {{ret.p4sir0.design}} at SIR 0 dB) and of A3* over 300 and 900 blocks | Thm. 1(ii), Sec. VI-E, `scripts/paired_disp.py` |
| A3 mis-stated contraction bound | Corrected to G eps (1 - L^n_W)/(1 - L) after n_W attacked blocks, for the case that every block of the window is accepted in both runs; a block accepted in one run only adds the norm of that run's update, which does not scale with eps. The branch is stated as not applying (A1) | Remark 1 |
| A4 near-tautology | "Certificate" removed everywhere; the design bound is attacker-independent by construction | Sec. IV |
| A5 Theorem 2 vacuous | Withdrawn; the last-layer variant is evaluated without a regret claim | Remark 1, Sec. VI-H |
| A6 weak Lipschitz estimates | First probes (first version; the revision does not change the fast learner): L_theta + L_a between {{lip.summin}} and {{lip.summax}}. Second campaign (`scripts/lipschitz_strong.py`): a finite-difference hill climb on the input direction for G_Phi and the largest of 20 random parameter and anchor directions on each of 10 blocks for L_theta, L_a, on three channel families at the frozen settings: L_theta + L_a between {{lip2.summin}} and {{lip2.summax}}. Probes only underestimate a Lipschitz constant, so the condition L < 1 fails | Remark 1, `docs/lipschitz_strong.json` |
| A7 delta_min hand-set | Derived slack: threshold min{1 - z sigma, relative-slack threshold} with sigma the running standard deviation of the clean pass ratio, floored by its binomial value; candidate in the calibration, not selected: the rule chose the {{cal.chosen}} (score {{cal.relselectclip.score}} vs {{cal.derivedselectclip.score}}), so the evaluated receiver keeps the first version's rho = 1 and floor 2e-3 (set in the first version as about five standard deviations of the pass fraction at n = 781), and its threshold does not adapt to the block length | Sec. IV (design rule), Table (calibration) |
| A8 G1 mismatch | The uncorrelated-error condition is stated as an assumption; the clean G1 statistic on the tanh channel at 10 dB has mean {{g1nl.mean}}, p99 {{g1nl.p99}}, max {{g1nl.max}} over {{g1nl.n}} blocks, never at tau_1 = 1.25. These are first-version clean runs (seeds 0-2); on them every consolidation period has a sum of verdicts of at least one, so the first-version and the corrected consolidation rules coincide | Sec. IV |
| A9 notation | Notation table; the CRC slack is rho, the soft-step width omega, kappa the consolidation clip; the revised paper has no symbol for an attacked fraction | Table (notation) |

## B. Threat model and adaptive attacks

| Item | Change | Where |
|---|---|---|
| B1 unconstrained perturbation | Physical attacker E = G X with M = 1, 2, 4 antennas; CSI error 0.1 and 0.01 at M = 2, now passed through the true channel (the first campaign injected the perturbation designed for G_hat, a bug); full rank kept as the worst case. Citadel-Rx excess between {{atk.cit0.exmin}} and {{atk.cit0.exmax}} over all {{atk.cit0.n}} attacks at SIR 0 dB (5 seeds); an attacker placed in a 3GPP scene in D3 | Sec. II-B, Table (attacks) |
| B2 joint pilot + data | A4: fraction alpha of the energy on the pilots and 1 - alpha on all data sub-blocks, optimised jointly behind the soft gates, alpha = 0.25 and 0.75, 5 seeds; jamming controls with the same data power. The most effective attack on Citadel-Rx: excess {{a4.025.excess}} at alpha = 0.25 ({{a4.025.rejk}} rejected) against {{ab.complete.excess}} for A1 on the same seeds; at 20 PGD steps {{b2.a4pgd20.excess}}, but the 20-step attack was rejected on {{b2.a4pgd20.rejk}} blocks against {{a4.025.rejk}} with 6 steps: further ascent on the attacker's objective lost acceptances, so the objective does not follow the real gates, and a joint attacker with an exact model of the gates was not run | Table (refdeg), Sec. VI-D |
| B3 denial of adaptation | (i) Channel-estimate spoof during a redraw (5 seeds): the gates rejected only {{deny.citadel.rejattmin}}-{{deny.citadel.rejattmax}} of the spoofed blocks, so it acted as an accepted perturbation (excess {{deny.citadel.excess}}). (ii) As intended, strong poisoning (A1, SIR 0 dB, blocks 40-89) during the redraw: rejected on {{b3.citadel.rej}} of the blocks, excess {{b3.citadel.win}} in the window and {{b3.citadel.post}} after it; online DeepSIC {{b3.onlinedeepsic.win}} in the window. The weakest perturbation that the gates still reject (the attacker's cost of denial) was not searched for, and denial was not run during an SNR drop; Sec. VI-D says so | Tables (deny, deny2), Sec. VI-D |
| B4 adaptive strength | Unroll 10 and 50, PGD 100 with 5 restarts, soft-gate objective (a smooth surrogate of the gates on the forward and the backward pass; BPDA proper keeps the exact forward pass) with the defence's thresholds (untightened) and running statistics for G1 (against LMMSE only) and G2; G3 and the tightening are not modelled, EOT; combined attack also against online DeepSIC; 5 seeds | Table (attacks) |
| B5 optimal slow drift | A3* (slow small-budget attack): 300 attacked blocks of a 400-block run, perturbation norm 5, 20, 50% of the received pilots; and 900 of 1000 blocks at 5%. Each attacked block is optimised for the soft-gate objective of the adaptive attacker (the data loss of the decisions the receiver emits times the soft probability that its gates accept, plus a reward for acceptance); there is no spoofed-channel target. At 5% the attack is accepted ({{ret.p8e005.rejk}} rejected over 300 blocks, {{ret.b5.rejk}} over 900); the paired displacement stays below the structural bound ({{ret.p8e005.DK}} vs {{ret.p8e005.struct}}; over 900 blocks {{ret.b5.DK}} vs {{ret.b5.struct}}), at an excess of {{ret.p8e005.excess}}. The objective has no term for the displacement of the slow level, and an attacker that maximises the displacement subject to acceptance, which B5 asked for, was not run; Sec. VI-E says so | Sec. VI-E, Table (retention), Fig. (drift) |
| B6 transfer too narrow | Grey-box attacker with a Citadel-Rx surrogate ({{atk.citadelgreyboxsir0.excess}}); query attacker on NACK feedback ({{atk.citadelquerysir0.excess}}; one query per attacked block, 40 in a window, so not a converged query attack, as Table (knowledge) states) | Table (attacks) |
| B7 knowledge vague | Knowledge table; synchronisation and pilot knowledge stated | Table (knowledge) |
| B8 budget includes noise | Both budgets defined; the signal-referenced one evaluated ({{atk.citadelsigbudgetsir0.excess}}) | Eq. (budget), Table (attacks) |

## C. Missing baselines

| Item | Change | Where |
|---|---|---|
| C1 CRC + rollback | CRC-Rollback: online DeepSIC with the CRC gate G2 at the fixed slack 0.01 (tau_2 = 0.99^32), judged against LMMSE alone, without CRC selection, and rollback to the last accepted weights; also rollback with all three gates. It differs from Citadel-Rx in more than the memory (a fixed rather than a relative slack, LMMSE rather than the better of LMMSE and the anchor as reference, no CRC selection), so the comparison that changes only the memory is the K = 1 ablation: Citadel-Rx's gates, relative slack and CRC selection with one memory (hence LMMSE as its only reference), which also fails ({{ab.K1.excess}}). The K = 1 ablation now reverts and falls back (it previously did neither, a bug) | Sec. VI-B, Tables (headline, ablations) |
| C2 regularised online | L2-SP (4 weights; weight 1: {{p2.l2spw1.excess}}, the smallest excess of any baseline), EWC (Fisher from pre-training), EMA teacher; 5 seeds. Clean SER: no baseline closes most of the gap between tuned online DeepSIC ({{p1.online_deepsic.wb0.clean}}) and Citadel-Rx ({{ab.complete.clean}}); the lowest are {{p2.dddeepsic.clean}} (decision-directed) and {{p2.cottadeepsic.clean}} (CoTTA-style), L2-SP and EWC raise the clean SER, and Citadel-Rx without the CRC selection has {{ab.noselect.clean}}, so its clean gain comes with the selection | Table (baselines) |
| C3 CRC-verified DD | CRC-verified decision-directed training ({{p2.dddeepsic.excess}}) | Table (baselines) |
| C4 TTA defences | EATA-style and CoTTA-style receivers; the EATA entropy filter never fired (largest mean data entropy {{eata.maxent}} nats against {{eata.thr}}): the poisoned receiver is confidently wrong | Table (baselines) |
| C5 under-tuned baselines | Epochs x learning rate x weight decay grid on calibration seeds, rule fixed in advance (online DeepSIC: {{tune.onlinedeepsic.epochs}} epochs, lr {{tune.onlinedeepsic.lr}}); every receiver built on online DeepSIC uses the tuned setting. Drift detection and median-of-means, which the run script did not list among them, ran first with their reference 300 epochs and learning rate 5e-3 (excess {{p2u.driftdeepsic.excess}} and {{p2u.medbndeepsic.excess}}, clean SER {{p2u.driftdeepsic.clean}} and {{p2u.medbndeepsic.clean}}); Table (baselines) reports their reruns with the tuned setting ({{p2.driftdeepsic.excess}} and {{p2.medbndeepsic.excess}}). The method weights (L2-SP and EWC 1e-2, EMA rate 0.9, CoTTA restore probability 0.05, EATA entropy threshold 0.4 ln 4) are the methods' defaults and were not tuned; L2-SP is also reported at four weights. The second backbone is tuned the same way ({{d8.tuned}}) | Sec. V, Table (baselines) |
| C6 MedBN mislabelled | Renamed "median-of-means gradient"; the text states that MedBN takes the median of batch-normalisation statistics, which DeepSIC does not have, and that the baseline moves the median to the gradient | Sec. V |
| C7 robust LMMSE | Huber-robust LMMSE ({{p2.lmmserobust.excess}}) | Table (baselines) |

## D. Experimental realism

| Item | Change | Where |
|---|---|---|
| D1 block length | N_d in {1000, 5000} x N_p in {32, 100}: Citadel-Rx excess {{sc.bl.citexmin}} to {{sc.bl.citexmax}}, online DeepSIC {{sc.bl.onlexmin}} to {{sc.bl.onlexmax}}; 5 seeds. With N_d = 1000 the clean false rejection of Citadel-Rx is above the 2% cap of the calibration rule ({{sc.citadelnd1000np100.frej}} at N_p = 100, {{sc.citadelnd1000np32.frej}} at N_p = 32); the derived slack, which follows the block length, was not run at these lengths | Table (scenarios) |
| D2 NR link level + LDPC | NR LDPC code blocks (base graph 2, k = 520, n = 1000, CRC-24A each, NR PUSCH scrambling; Sionna 2.2) over 3GPP UMi drops, BLER after decoding; the CRC gate uses the per-user symbol error rate on decoder-verified symbols. Result: the defence fails here. The networks do not track these channels, most likely because their phases rotate from block to block; no control run with the phases held fixed establishes this cause (online DeepSIC clean BLER {{d23m.onlinedeepsic.blerfirst}} in the first 20 blocks, {{d23m.onlinedeepsic.blerlast}} in the last 20), Citadel-Rx runs on LMMSE through the CRC selection, and under attack its window BLER ({{d23.citadel.d75bler.raw}} at 75 m) lies with those of online DeepSIC ({{d23.onlinedeepsic.d75bler.raw}}) and LMMSE ({{d23.lmmse.d75bler.raw}}) | Sec. VI (coded scene), Table (umi) |
| D3 attacker in the scene | One antenna at a user's maximum power at 35, 75, 150 m in the same TR 38.901 UMi drop; its SIR follows from path loss, LoS state and shadowing: median {{d23.d35.sirmed}}, {{d23.d75.sirmed}}, {{d23.d150.sirmed}} dB over five drops | Sec. VI (coded scene) |
| D4 N > U | 4 x 16 and 8 x 32 with the SED profile stretched over the array: Citadel-Rx {{sc.citadel4x16.excess}} and {{sc.citadel8x32.excess}}, online DeepSIC {{sc.onlinedeepsic4x16.excess}} and {{sc.onlinedeepsic8x32.excess}}; 5 seeds. The stretched profile was adopted after test runs with the unstretched one (8 x 32: seeds 10-14; 4 x 16: seeds 10-11), which are not in the table: with the unstretched profile Citadel-Rx had an excess of {{sc.unstr.citadel8x32.excess}} (clean SER {{sc.unstr.citadel8x32.clean}}, {{sc.unstr.citadel8x32.rejk}} attacked blocks rejected), online DeepSIC {{sc.unstr.onlinedeepsic8x32.excess}} and LMMSE {{sc.unstr.lmmse8x32.excess}} at 8 x 32, and {{sc.unstr.citadel4x16.excess}} (clean SER {{sc.unstr.citadel4x16.clean}}, {{sc.unstr.citadel4x16.rejk}} rejected), {{sc.unstr.onlinedeepsic4x16.excess}} and {{sc.unstr.lmmse4x16.excess}} at 4 x 16 | Table (scenarios), Sec. VI-H |
| D5 higher order | 16-QAM at 20 dB: Citadel-Rx fails (clean SER {{sc.citadelqam16.clean}} vs {{sc.onlinedeepsicqam16.clean}} online DeepSIC and {{sc.lmmseqam16.clean}} LMMSE) and the failure is analysed | Table (scenarios), Sec. VI-H, VII |
| D6 abrupt change | Redraw and 6 dB SNR drop at block 50, no attack (5 seeds) | Table (deny) |
| D7 long horizon | 2000 clean blocks, 2 seeds: Citadel-Rx SER {{d7.citadel.first}} over blocks 5-499 and {{d7.citadel.last}} over the last 500, {{d7.citadel.frejk}} false rejections; online DeepSIC {{d7.onlinedeepsic.first}} and {{d7.onlinedeepsic.last}}; and the 900-block accepted small-budget attack (B5). The Jakes run and the norm of the slow levels over time asked for in D7 were not run or exported | Sec. VI-E |
| D8 second backbone | Fully connected joint-symbol detector (512 hidden units, 256 classes) in Citadel-Rx, online training and CRC-Rollback, 5 seeds: excess {{d8.citadel.excess}} vs {{d8.onlinedeepsic.excess}} and {{d8.crcrollback.excess}}; clean false rejection {{d8.citadel.frej}} (the weaker network loses more often to the reference) | Sec. VI (second backbone), Table (joint) |
| D9 compute | Multiply-accumulates per block counted from the network dimensions (`scripts/flops.py`): Citadel-Rx {{flops.citadel}} GMAC, online DeepSIC {{flops.onlinedeepsic}} GMAC, 30-step variant {{flops.citadelsteps30}} GMAC; wall time per block on the M4 laptop (Citadel-Rx {{time.citadel}} s, online DeepSIC {{time.onlinedeepsic}} s); no GPU measurement | Table (scenarios), Sec. VI-H |

## E. Statistics and protocol

| Item | Change | Where |
|---|---|---|
| E1 correlated blocks | Moving-block bootstrap with the measured decorrelation length; seed-level exact Wilcoxon tests with the smallest attainable p stated; "every p < 0.001" deleted | Sec. V |
| E2 too few seeds | 10 test seeds at the headline cell, 5 (10-14) at the other headline cells and in every other experiment except A3*, the first abstain version and the long clean horizon (2) and the sensitivity test (1); stated per table | Tables |
| E3 easy part of the fade | Attack window start drawn per seed from blocks 10-50; excess SER over the matched clean run is the primary metric | Sec. II-C, V |
| E4 thresholds after test | Calibration seeds 0-2 with rules fixed in advance; the second campaign's new choices (abstain threshold z = {{h3.z}}, second-backbone tuning) on seeds 0-2 by rules fixed before any test run of those features; two exceptions are stated: the abstain statistic, adopted after test runs of its second version and therefore also tested on fresh seeds 15-19, and the stretched SED profile of the larger arrays, adopted after unstretched test runs (D4) | Sec. V, Table (provenance) |
| E5 sensitivity | One at a time x0.5, x0.75, x1.5, x2 for eight settings on seed 10, and a two-setting grid (CRC slack x G1 slack); excess between {{sens.exmin}} and {{sens.exmax}} | Table (sensitivity) |
| E6 intervals and counts | Rates in the tables, counts in the text for some of them, and the rule for the denominators in Sec. II-C; Wilson intervals at the headline cell (rejection {{p1.citadel.wb0.rejk}} {{p1.citadel.wb0.rejci}}, false rejection {{p1.citadel.wb0.frejk}} {{p1.citadel.wb0.frejci}}) | Sec. II-C, VI-A |
| E7 Fig. 3c | Paired displacement of every level and the anchor, with the design and structural bounds, for A1 (5 seeds) and A3* (2 seeds, 400 blocks; 900 blocks); both bounds hold in the attack window in every run (after the window D_K rises once more at the next consolidation of the slowest level, Sec. VI-E) | Sec. VI-E, Figs. (retention, drift) |
| E8 Holm family | Family = the four baselines of a column, stated in the captions | Table (paired) |

## F. Claim consistency

Every sentence F1-F14 was rewritten; the abstract and conclusion carry only computed numbers, each
tied to one table cell, except the clean movement of the slowest level in the conclusion, which is given in the text of Sec. VI-E. F6/F7 ("certificate", "non-expansive") are deleted; F10 is deleted (neither
bound of Theorem 1 needs the reversion, which keeps the buffered and later fast states, and hence
Delta in the structural bound, close to the clean run; the effect of keeping a rejected update is not
evaluated in the revision); F11
is deleted (Sec. VI-C states instead that, when the gates reject nearly every attacked block, the excess depends on the power of the pilot perturbation, not on how it was optimised); F12 uses the suggested wording; F13 is deleted; F14 is replaced by the
seed-level tests of E1. "Halves the SER" is replaced by the measured relative change against the
tuned online DeepSIC ({{cmp.online_deepsic.clnpct}}% lower clean SER).

## G. Novelty, positioning, references

| Item | Change |
|---|---|
| G1 | Pilot contamination and its detection, code-verified online training, EATA / CoTTA / SAR / RoTTA / persistent TTA, L2-SP / EWC / mean teacher, adaptive-attack methodology, adversarial PHY learning, complementary learning systems; every reference checked against its record (`docs/REFERENCES_VERIFIED.md`, which marks the fields that rest on search-result records because publisher pages could not be opened; TS 38.211 is cited as V19.2.0 from the ETSI record). The pre-submission check added drift detection and Bayesian online learning in deep receivers, further test-time poisoning studies, over-the-air poisoning of wireless learners and a theory of continual learning under poisoning |
| G2 | The introduction leads with the principle; the CRC-Rollback result (Sec. VI-B) supports the hierarchy |
| G3 | The CRC rule is presented as a design rule |
| G4 | Table I has the rows for pilot-spoofing detection, code-verified online training, CRC-Rollback, filtering/restoring TTA and anchored fine-tuning |

## H. Method upgrades

| Item | Result |
|---|---|
| H1 | Consolidation clip: it binds in {{clip.cln}} consolidations of the clean twins and removing it leaves the excess unchanged ({{ab.noclip.excess}}); it provides the design bound, not the measured robustness. Anchor-start variant: calibration candidate, not chosen |
| H2 | Not evaluated inside Citadel-Rx: the option (`receiver.dd_weight`) is implemented but is 0 in every Citadel-Rx run, and CRC-verified data serve as training labels in Citadel-Rx only in streak recovery (Sec. III-C, H4). CRC-verified decision-directed training is evaluated as a baseline ({{p2.dddeepsic.excess}}, C3) |
| H3 | Abstain state. First version: locks on clean runs ({{abs.rejk}} clean blocks rejected). Final version (residual on CRC-verified symbols over the pilot noise estimate, z = {{h3.z}} from calibration): no abstention on clean blocks ({{h3.cleanabstk}} on seeds 10-14, {{h3x.cleanabstk}} on 15-19) or after an SNR drop; abstains on every attacked block of A1 and of A4 at alpha = 0.75; does not lower the A4 excess ({{h3.a4025.excess}} vs {{a4.025.excess}} without it); abstains after legitimate redraws ({{h3.redraw.abst}} of 50 blocks on average, all 50 on {{h3.redraw.nall}} of {{h3.redraw.n}} seeds) because no slot is verified for every user once one user's CRCs fail (verified fraction {{h3.redraw.verbefore}} -> {{h3.redraw.verafter}}). Reported as not usable; a per-user verified residual is the next step |
| H4 | Streak recovery: under the denial spoof attempted {{deny.streak.attempts}} times and kept {{deny.streak.accepted}} times; under denial by strong poisoning it re-fitted {{b3.citadelstreak.att}} times, kept {{b3.citadelstreak.acc}}, and the excess was {{b3.citadelstreak.win}} in the window, against {{b3.citadel.win}} without it (five seeds, no interval) |
| H5 | Drift guard against the accepted 5% drift: D_K {{ret.p8e005.DK}} -> {{ret.h5.DK}}, excess unchanged ({{ret.h5.excess}}) |
| H6 | Per-sub-block CRC selection: in the receiver and as an online-DeepSIC comparator; {{sel.share}}% of the clean gain is the selection |
| H7 | Per-user gating against an attack on one user's pilots (A2): excess {{h7.citadelperusera2.excess}} with it and {{h7.citadela2.excess}} without; the block-level gates still reject the block, so the other users are reverted on {{h7.citadelperusera2.revoth}} of the attacked blocks |

## I. Writing and reproducibility

| Item | Change |
|---|---|
| I1 | The repository URL works as given; renaming the repository to Citadel-Rx is an owner action (GitHub redirects the old URL) |
| I2 | Algorithm 1 |
| I3 | Notation table |
| I4 | The period vectors are stated wherever K or C change |
| I5 | Provenance table, including the second campaign's choices |
| I6-I8 | SED defined (with the stretched profile for the larger arrays); SER, BLER and per-user CRC defined; informal wording removed |
| I9-I12 | Tables carry the budgets; one figure replaces the dense architecture figure; four numbers in the abstract; detailed tables are in `docs/REV_*.md` |
| I13 | Three commands re-run the two campaigns (`scripts/revision_fast.py`: the first campaign's shards `--shard laptop` and `--shard cloud`, and the whole second campaign on one machine with `--campaign 6 --shard local`), and one (`make paper`) rebuilds every number, table and figure and the paper; `python scripts/fill_response.py` rebuilds this letter from the same numbers; README section "Reproducibility". `requirements.txt` gives lower version bounds, not a lock file. A Zenodo DOI is an owner action |
| I14 | Acknowledgement of the COST2100 trace release; supervision and funding to be added by the author |
