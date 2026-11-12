# Independent review panel of the ten-page version (2026-11-11)

Three reviewers, each in the role of a senior IEEE TWC reviewer, read `paper/main.pdf` (commit 93b0b90), the extended version and the code: wireless PHY, adversarial ML, statistics and reproducibility. A fourth agent merged and checked their points against the code and the records. Scores: 4, 5, 5 out of 10 (major revision). This file is the to-do list of the overhaul; every item is answered in `docs/OVERHAUL_PLAN.md`.

## Reviewer: Wireless PHY (score 4)

Major revision (borderline reject in its current form). The statistical protocol, the adapted attacks and the candour about failures are well above the TWC norm. The practical claim does not yet transfer. Every positive result comes from a real-valued, deterministic SED channel that is the same for all 'held-out' seeds, and the pre-training already covers that channel. The deep receivers lose clearly to a cheap ML detector on this linear channel, and the gates only work because their reference is a deliberately weak LMMSE. The one standardized, complex-valued scenario is a coded 3GPP link with hard decisions and a single narrowband channel per slot, and the method fails there. The receiver needs about 9 GMAC and 900 sequential optimizer steps for each 1 ms block.

### 1. No ML or model-based soft-IC baselines: ML with the same LS channel estimate beats every deep receiver on clean blocks, and the gates depend on a weak reference (major, experiment)

Sec. V lists LMMSE and Huber-LMMSE as the only model-based detectors. 4x4 QPSK is the regime where exhaustive ML (256 hypotheses) is cheap. I ran a quick Monte Carlo (/tmp/claude-0/-home-user-Citradel-Rx/55386545-c1e6-5aa0-be1b-e178205b9b42/scratchpad/rev_ml/ml_check.py) using the paper's own setup: SED (2) with the cosine fades, sigma^2 = 0.5*10^-1, Np = 100 random QPSK pilots and the regularized LS estimate of (19). Vector error rates came out as follows. ML with LS CSI is about 0.006 and ML with true CSI about 0.005. LMMSE with LS CSI is 0.051, consistent with the 0.0562 in Table VIII. By comparison, Table IV gives 0.0159 for Citadel-Rx, which already includes CRC selection among three detectors, and 0.033 for online DeepSIC. The ML detector costs about 0.1 GMAC per block, against 9.0 GMAC for Citadel-Rx (docs/flops.json). So on the paper's main channel the deep receiver is about 2.6x worse than a cheap model-based receiver. The paper's own conclusion is that 'relative gates presuppose a network at least as good as the model-based reference'. G1 and G2, (20)-(23), are protective only because the reference is a linear detector that is about 3.5x worse than ML. With an ML reference, the gates would likely reject most clean blocks, as at 16-QAM and in the coded scene.

**Fix.** (a) Add rows to Table IV and Table VIII for: ML or K-best sphere decoding (K=16); MMSE-SIC/PIC, the model-based SIC that DeepSIC replaces. Give each with LS CSI and with perfect CSI, reporting clean SER, window SER, excess under white-box A1 at SIR 0 dB, and MACs, on seeds 10-19. (b) Re-run Citadel-Rx at the headline cell with ML/K-best as the reference in (23) and as a candidate in the CRC selection (26). Report false rejection, rejection and clean SER. (c) If the deep receiver still loses on clean blocks, move the main evaluation to a regime where deep receivers are justified, and show there that ML with LS CSI is beaten. Candidates are the tanh(0.5x) nonlinear channel of [raviv2023] (already in the code as channel.linear=false), few pilots (Np = 16-32), or non-Gaussian interference.

### 2. Main channel is real-valued, deterministic and identical across the 'held-out' test seeds; pre-training sees that same channel (major, experiment)

Eq. (2) is a real matrix, c_{u,b} e^{-|nu-u|}. The paper still writes H_b in C^{NxU}, and in the code H is float64 (channels/base.py, _synthetic, cosine mode). QPSK through real gains has no phase and decouples I and Q. The cosine mode uses no random draw, so seeds 10-19 change only the noise, the symbols and the start of the attack window. Every test run sees the same channel sequence. Pre-training (runner.pretraining_blocks, fading 'static') uses H_mean at SNRs from 2 to 16 dB, and H_mean is exactly the channel of block 0. Test-time adaptation therefore only has to follow per-user amplitude fades in [0.6, 1.0] with periods of 21-51 blocks, which happen to sit around the slowest consolidation period C3 = 32. COST2100 appears only in calibration and is reduced to real gains, with the diagonal pinned to 1 and off-diagonals scaled by 0.25. Jakes appears only in Remark 1. The 'held-out seeds' therefore test neither channel generalization nor a realistic MIMO channel.

**Fix.** Re-run the headline cell (Table IV, seeds 10-19), the three strongest attacks of Table V and the key ablations of Table IX (K=1, no fallback, G2 only) on complex channels with a fresh channel draw per seed. Pre-train on an ensemble of channels that does not contain the test draw. Use three channel families: (a) correlated Rayleigh (Kronecker, exponential correlation 0.5 at the receiver) evolving as Jakes AR(1) with f_D T_b in {0.001, 0.01, 0.05}; (b) the complex COST2100 traces on the test seeds; (c) 3GPP CDL-A and CDL-C at 3 and 30 km/h. In the text, say explicitly that (2) is real and that the seeds do not change the channel.

### 3. The coded 3GPP link is not an NR link: one narrowband channel across about 27 MHz, hard-decision LDPC with fixed |LLR|=3, untuned receivers, one mobility and one SNR (major, experiment)

Sec. VI-H and Table III describe the coded scene. make_umi_channels.py keeps only the frequency response at the carrier and applies it to a block of 25,200 REs (about 27 MHz). With UMi delay spreads of roughly 100-300 ns the coherence bandwidth is only about 1-3 MHz, so the block is far from flat. The decoder (coding/ldpc.py, check) feeds the hard decisions (2b-1)*3 into BP, even though both DeepSIC (psi^(Q)) and LMMSE produce posteriors. This costs about 2 dB and sets the artificial operating point at which LMMSE has a BLER of 0.0686 with rate-0.52 QPSK at 'SNR 10 dB'. The CRC-24A on every code block is a simplification of NR. All receivers keep their SED-tuned settings, the UEs move at 3 km/h only, no BLER-vs-SNR curve is given, and neither throughput nor HARQ is modeled. channels/sionna_pusch.py, the intended OFDM PUSCH chain, raises NotImplementedError.

**Fix.** Implement the OFDM PUSCH chain with Sionna: PUSCHTransmitter + OFDMChannel with UMi/CDL, 30 kHz SCS, DMRS type 1 with one additional position, LS estimation plus interpolation, and per-PRB or per-subband processing. Feed max-log LLRs from psi^(Q) and from LMMSE (post-equalization SINR) to LDPC5GDecoder. Use TB CRC and code-block segmentation as in TS 38.212, with MCS 5, 10 and 15. Retune every receiver on calibration drops 0-2. Report BLER and goodput against SNR from -5 to 20 dB at 3, 30 and 60 km/h, clean and under A1 and the physical attacker at geometric SIR from -20 to +10 dB.

### 4. The cause of the failure in the 3GPP scene is left unresolved, and the backbone may not track complex time-varying channels (major, experiment)

Sec. VI-H says the phase rotation 'is the likely cause of this gap, not an established one'. Online DeepSIC has a clean BLER of 0.169 against 0.0686 for LMMSE, and the fast level of Citadel-Rx passes a virtual fraction of 0.03 against 0.60 for the reference. If the DeepSIC backbone, which is fed raw stacked real samples, cannot follow phase rotation, then neither the protected memory nor the gates are usable on any real channel. In that case the principle has been shown to work only where phases are absent.

**Fix.** Run a controlled experiment. (1) On SED, multiply each user's column by e^{j phi_{u,b}}, where phi follows a random walk with step sigma_phi in {0, 1, 5, 20} degrees per block. (2) Repeat the UMi drops with the phases frozen (for example the block-0 phase applied to |H_b|) and with the phases rotating. (3) Add a backbone variant whose input includes the LS estimate H_hat_b or the LMMSE-equalized symbols, as practical neural receivers do, and retune the online settings for it. For each condition report clean SER/BLER, false rejection and A1 excess. Then state the mechanism, or drop the claim.

### 5. Complexity and latency are not reported in a form that shows feasibility, and the receiver is orders of magnitude from real time (major, experiment)

The main text gives 3.03 s per block on one CPU core and '4.1 times' the MACs of online DeepSIC. docs/flops.json gives 9.0 GMAC per 1 ms block for 4x4 QPSK, 5.8 GMAC of it training, and 72 GMAC per block at 8x32. That is about 9 TMAC/s for a 4-user link. Each block runs T=300 Adam steps for each of Q=3 stages one after the other: 900 dependent steps before the data can be detected. This latency floor cannot be removed by parallel hardware and far exceeds the NR PUSCH processing budget (N2 of a few hundred microseconds at mu=1). The slow-level buffer holds up to 32 snapshots, about 8.7 MB at 4x4 and about 71 MB at 8x32. LMMSE and ML costs are not given. The 30-step and last-layer variants are mentioned only in the extended version.

**Fix.** Add a complexity table for LMMSE, ML/K-best, online DeepSIC, Meta-DeepSIC, CRC-Rollback and the Citadel-Rx variants. Give MACs per block and per decoded bit, sequential depth (dependent optimizer steps per block), memory, and measured GPU latency per block (users batched, CUDA graphs). Evaluate T in {10, 30, 100, 300}. Also evaluate a pipelined variant that detects block b with weights trained up to block b-1, which takes adaptation off the critical path. For each, report clean SER, false rejection and A1 excess on seeds 10-14, and plot excess against MACs and latency (Pareto). Compare with TS 38.214 N2.

### 6. The frame structure is unrealistic, and the statistical power of G2 depends on it (major, experiment)

Each block carries Np = 100 pilots and Nd = 24,992 data symbols per user (0.4% pilot overhead) under one constant channel. The pilots are random non-orthogonal QPSK, not NR DMRS ports. There are 781 CRC-8 sub-blocks of 32 symbols per user, a 12.5% CRC overhead that NR does not have. G2 alone rejects 99% of the poisoned blocks because the pass fraction is estimated from JU = 3124 checks per block. Table X already shows false rejection above the 2% cap at Nd = 1000, where J = 31. A typical NR allocation per user per slot has DMRS overhead of 7-29%, a few hundred to a few thousand data REs and only 1-4 code blocks, so F_X in (21) becomes nearly binary. The CRC selection that gives 70% of the clean gain also depends on the fine-grained sub-block CRCs.

**Fix.** Re-run the headline cell with NR-like slot dimensions. Use 4-16 PRBs per user, 12 data and 2 DMRS symbols per slot (Np = 24-96, Nd = 576-2304) and orthogonal DMRS ports. Give each user 1-3 LDPC code blocks per slot, with CRCs only as specified in TS 38.212. If needed, aggregate the gate statistics over several slots. Report false rejection, rejection, excess, CRC-selection gain and decision delay. Evaluate the derived slack of (28) in these settings.

### 7. Missing robust model-based defenses and trivial detectors; the comparison set is mostly deep-learning (major, experiment)

Table VIII compares mostly deep test-time-adaptation variants at default settings. A pilot-only perturbation at SIR 0 dB that lies outside span(S_b) inflates the pilot residual sigma_hat_b^2 in (19), roughly 1.2 against 0.05. If it lies inside span(S_b), it moves H_hat, which G3 sees. A simple pilot-residual or noise-consistency test therefore probably catches the headline attack. Five baselines are absent: (i) LMMSE/ML with a Kalman-tracked channel and an innovation plus pilot-residual test that falls back to the previous estimate; (ii) data-aided or semi-blind channel estimation from CRC-verified data, which should dilute pilot poisoning since Nd/Np is about 250; (iii) the pilot-spoofing detectors [9], [10] combined with freezing adaptation; (iv) the original Meta-DeepSIC of [4], which trains on decoded, re-encoded codewords without new pilots and which the paper itself says is not the attacked form; (v) frozen pre-trained DeepSIC, which Sec. VI-F says was not run.

**Fix.** Add all five rows to Table VIII with clean SER, window SER, excess, MACs, rejection and false rejection, under A1, A4 (alpha = 0.25) and the rank-1 physical attacker on seeds 10-14. Then state what Citadel-Rx adds over the best of them. Its own ablation 'No CRC selection' has an excess of +0.0053, so the comparison should be on window SER, not on excess alone.

### 8. Mobility, non-stationarity and multi-user scheduling dynamics are not evaluated (major, experiment)

The slow levels (C = 1, 8, 32 blocks) assume statistics that stay roughly fixed over 32 ms. Mobility is limited to the SED cosine fades and 3 km/h in UMi. After a legitimate redraw (Sec. VI-D) the SER is 0.250 for Citadel-Rx and 0.224 for online DeepSIC, about 4x the clean LMMSE level. Both deep receivers therefore fail to re-adapt even without an attack. In a real cell, MU-MIMO pairing changes per slot, users arrive and leave, and power control steps. DeepSIC's per-user networks, and the memory of them, depend on which users are co-scheduled.

**Fix.** Add a Jakes AR(1) sweep with f_D T_b in {0.001, 0.005, 0.02, 0.05, 0.1} and UMi at 3, 30, 60 and 120 km/h, reporting clean SER, false rejection and excess. Add a scheduling experiment in which one of the U users is replaced every 10 or 50 blocks: new channel column, its network re-initialized from theta_pre, and the slow levels handled per user. Report recovery time and excess, with LMMSE and ML for reference.

### 9. The attack regime covers too little: narrow SIR range, no ROC, no attacker constrained by the physical statistics (major, experiment)

Fig. 3(d) spans SIR from -10 to +10 dB, but the paper's own geometry gives a median SIR of -26 dB at 35 m (Fig. 5). At +10 dB online DeepSIC is still badly hurt, while the gates reject 0.945 (Table VII). The SIR at which the attack still hurts online DeepSIC but evades the gates was not located ('the weakest rejected perturbation was not searched for'). The soft-gate attacker leaves out G3 and the tightening, and 'one with an exact model of the gates was not run'. No attacker keeps the pilot residual and the innovation inside their clean range, which is what a stealthy pilot contaminator would do.

**Fix.** Sweep SIR from -30 to +30 dB in 5 dB steps for Citadel-Rx and online DeepSIC, reporting rejection, false rejection and excess, and mark where the gates stop detecting while the excess of online DeepSIC is still above 0.01. Add projected PGD onto the set where the pilot residual is at most (1+eps) times the clean value and I_b is at most tau3 times I_bar, with G3 and the tightening included in the soft objective. Plot per-gate ROC curves (detection probability against false alarm) by sweeping tau_i at SIR 0, 10 and 20 dB.

### 10. The remedy for the 16-QAM failure was not tested (major, experiment)

At 16-QAM the network keeps 256 hidden units, a quarter of the 64 per constellation point used for QPSK. It passes 0.11 of the clean CRCs against 0.93 for LMMSE, so 98% of the clean blocks are rejected. The paper says 'a wider one was not tested'. As written, the method works only for QPSK, while NR PUSCH uses QAM up to 256.

**Fix.** Re-run 16-QAM with 1024 hidden units and retuned online settings at SNR 15, 20 and 25 dB on seeds 10-14, giving clean SER, false rejection and A1 excess. Add 64-QAM at least for the references. If the failure persists, limit the title, abstract and conclusions to QPSK.

### 11. Hardware impairments and model mismatch are not evaluated for gates that assume a linear model (minor, experiment)

G1 tests the fit of the decisions to the linear model, and G3 tests the channel innovation. Clean false rejection under the tanh nonlinearity was checked only on first-version runs (extended version). CFO residue, phase noise, IQ imbalance and PA compression would raise the clean residual and innovation and could push false rejection above the 2% cap.

**Fix.** Report clean false rejection and A1 excess at the headline cell under each of the following: tanh(0.5x), a residual phase drift of 0.5-5 degrees per 100 symbols, Wiener phase noise, and IQ imbalance of 1 dB / 5 degrees.

### 12. The SNR convention, the error metric and the single operating point hide performance (minor, text)

With sigma^2 = 0.5 * 10^{-SNR/10} and unit-energy symbols, the per-antenna Es/N0 is about 3 dB above the nominal SNR, plus the SED column gain of about 1.3, so '10 dB' is effectively about 13-14 dB. The SER counts a slot in which any user is wrong (a vector error rate), and no per-user SER or BER is given. All SED results are at one SNR, so neither clean performance nor gate false rejection is shown as a function of SNR.

**Fix.** Define SNR as the received Es/N0 per antenna (or Eb/N0). Report per-user SER and BER. Add a figure of clean SER and false rejection against SNR from 0 to 20 dB for all receivers, including ML and MMSE-SIC.

### 13. Comparisons based on excess alone favour receivers with poor clean performance; no coded translation on SED (minor, analysis)

Table IV reports excess and clean SER but not the absolute SER under attack. The 'No CRC selection' row (excess +0.0053, clean SER 0.0317) shows that the excess is not monotone in usefulness. Relative to its clean twin, the headline excess of +0.0188 more than doubles the SER of Citadel-Rx (0.0159 to about 0.035). What that means for BLER or throughput is not shown on the main channel.

**Fix.** Add window SER and goodput to Table IV. Re-run the headline cell on SED with LDPC code blocks and soft LLRs, and report BLER and goodput, clean and in the window.

### 14. The larger arrays use only a stretched real SED profile and give no model-based reference (minor, experiment)

Table X shows 4x16 (clean SER 6.8e-4) and 8x32 only on the real, stretched SED profile, which was adopted after test runs with the unstretched one. LMMSE and ML numbers at these sizes are not given. With 16 or more antennas, linear detection is near-optimal, and pilot contamination can be detected from spatial signatures, so the value of a deep receiver there is unclear.

**Fix.** Report LMMSE, ZF and ML/K-best clean and excess SER at 4x16 and 8x32. Add a 16x64 configuration on complex correlated or UMi channels with a 32/64-element array, and a spatial-signature pilot-contamination detector [9] as a baseline.

### 15. The retention bounds say nothing about error rate (minor, analysis)

Theorem 1(i) is the clip times the number of consolidations. Bound (31) needs the paired clean run, and both bound parameter displacement D_K only. Sec. VI-E shows D_K and the excess moving independently: the drift guard lowers D_K but not the excess. A TWC reader will ask what D_K guarantees for SER.

**Fix.** Add an empirical mapping from D_K to excess SER across all runs (scatter with rank correlation), or a bound through the Lipschitz constant of the detector output with respect to the weights on the data distribution. State in the abstract that the bounds are on weights, not errors.

### 16. No over-the-air validation (minor, not_fixable_now)

Every result is simulated. Synchronization of a real pilot attacker, CFO, timing offsets, hardware non-idealities and measured channels all affect both the attack and the physics gates.

**Fix.** Validate on an SDR testbed (for example a multi-antenna USRP base station with 4 UEs and one attacker node) or a 5G testbed with a real PUSCH stack, with measured channels and a synchronized attacker.

## Reviewer: Adversarial ML (score 5)

Major revision. The design, the protocol (matched clean twins, held-out seeds, frozen settings) and the candour about failures are well above average. But the central security claim, that attacks adapted to the gates leave the excess unchanged, rests on attacks that do not model the defense. The records show that their surrogate predicted acceptance on almost every block while the real gates accepted none. None of them ever left the full-budget sphere, and the stateful parts of the gates, the reference attack and the retention attack were never targeted by a correctly specified, converged attacker. Until an exact-forward attack, a budget/boundary search, a gate-state ratchet/cold-start attack and a correctly specified A4/A3* are run, the paper shows detection of full-power, mis-optimized pilot attacks, not robustness to adaptive poisoning.

### 1. Adaptive attacks do not model the defense: the surrogate's predicted acceptance contradicts the real verdict (major, experiment)

Sec. II-B, eqs. (6)-(8), Table II and Table V. The attacker unrolls 2/10/50 plain-SGD steps with mu=5e-3, while the victim takes T=300 Adam steps per stage with the delta rule (15), the proximal pull (16) and the surprise-scaled step (14). The soft gates use references from the unattacked block (clean-pilot LS estimate), untightened thresholds, and leave out G3 and the CRC selection (26). The records show the result. In results/rev_p3_adaptive_g1fix/p3_citadel_strongest__sir0_* (the 'Combined' row), the attacker's objective obj = nll*p_acc + (p_acc-1) has median -0.058 and exceeds -0.5 on 200/200 attacked blocks. That implies a surrogate acceptance probability of about 0.9, yet the receiver accepted 0/200 (gamma ~1e-4; fast-level CRC pass 0.018 against 0.82 for the reference). The soft-gate rows at 0 and 10 dB behave the same way (obj > -0.5 on 97% and 95% of blocks, 0% accepted). So the attacker optimizes a fast level that barely moves from theta_{b-1}, while the real 300-step map destroys the fast level and the gates reject it. The paper also calls this BPDA, but here both the forward and the backward pass are smoothed (extended version, line 256), which is not BPDA. 'Attacks adapted to the gates ... leave the excess unchanged' is therefore not supported.

**Fix.** Implement an exact-forward attack. (1) Forward: run the victim's exact fast update (300 Adam steps x Q stages, delta rule, proximal pull to a_b, eta_b(E) from the surprise), the fused H_b(E), sigma_b^2(E), the LMMSE and anchor references, all three gates with tightening r_b(E), and the CRC selection. (2) Backward: implicit differentiation at the fast state. Use dtheta*/dE = -(Hess_theta[l + lambda/2 ||theta-a||^2])^{-1} d^2l/dtheta dE, solved by 20-50 conjugate-gradient iterations with Hessian-vector products. Alternatively, differentiate through the full Adam trajectory with gradient checkpointing (back-gradient optimization). Gates use a margin (hinge) surrogate only in the backward pass (true BPDA). (3) Check that the hard replica reproduces the receiver's gamma_b on 100% of clean and attacked blocks, and report the cosine between the surrogate gradient and finite-difference gradients of the true objective on 20 random directions. (4) Run PGD with 200 steps, 10 restarts, step eps/20 with cosine decay, keeping the best iterate by the exact receiver's emitted SER. SIR 0, 10 and 20 dB; seeds 10-19. Report objective-vs-iteration curves and predicted-vs-realized acceptance per attack row of Table V. Rewrite the abstract/Sec. VI-C claims to match. (The receiver costs about 4 s per block, so 200 exact evaluations per block is about 15 min per block, feasible on the existing pool.)

### 2. No acceptance-boundary or budget search: every adaptive attack sits on the full-budget sphere (major, experiment)

Eq. (7) uses normalized steps of length eps/4 from 0, and restarts start on the sphere of norm eps. In every adaptive record (unroll 10/50, PGD 100 with 5 restarts, soft gates, combined), ||E||/eps = 1.000 on every attacked block, so no attack ever tried a smaller perturbation. At SIR 0 dB the attacker's pilot energy equals that of all users, and any detector fires. Against a detect-and-fallback defense, the strongest attack is the largest perturbation that is still accepted, or a harmful accepted one. The paper admits that 'the weakest rejected perturbation was not searched for' (Sec. VI-D), and Fig. 3(d) has only -10, 0 and +10 dB. The trade-off weight between harm and acceptance is fixed at 1 (gate_aware_weight), and the sigmoid soft step with omega=0.1 saturates (vanishing gradients) deep in the rejection region. The headline '99% rejected at 0.1% FRR' is a detection rate for a 0 dB attacker only. The working tree now contains an uncommitted oracle_scales line search (pilot_poisoning.py, _oracle_select). It scales one fixed direction and maximizes the current block's SER, and is not reported in the paper.

**Fix.** (a) Constrained attack per block: maximize the harm of the emitted output subject to gamma_b >= 1/2, using a Carlini-Wagner-style Lagrangian with binary search (8 steps) over the trade-off constant c in [1e-3, 1e3] and a hinge margin on each gate statistic, plus bisection on ||E|| along each PGD direction. Accept a candidate only when the exact receiver copy accepts it. (b) An SIR sweep from 0 to 40 dB in 5 dB steps for A1, soft-gate and exact attacks, seeds 10-19. Plot the rejection rate at the fixed 0.1% FRR (a detection curve), the harm of accepted blocks, D_K and the window/after excess against SIR, and report the maximum excess over SIR as the security number. (c) Report the oracle_scales results if they are kept, and extend them from a fixed-direction scale to the constrained search in (a).

### 3. Gate state can be written by the attacker: ratchet and cold-start attacks are untested and outside Theorem 1 (major, experiment)

Sec. III-C, eqs. (21)-(25) and the code. The normalizers g1bar and g2bar are EMAs (0.9/0.1) of accepted-block statistics, and gates/physics.py update_clean also updates them unconditionally on the first three blocks (n_accepted < 3). An accepted block can raise g1bar by up to 2.5% (tau1 = 1.25) and lower g2bar by about 1.9% (median tau2 = 0.81 in the clean twins; 5% at the minimum, 0.49). Over 100 accepted blocks that compounds to factors of about 12 and 0.15, enough to admit fast levels like those of A1 (normalized G2 statistic about 0.02-0.1, G1 about 2-3.7 in the records). ChannelTracker.fuse (receivers/lmmse.py) sets H_prev on every block, rejected ones included, so G3's prediction rho*H_{b-1} follows the poisoned estimate, and a consistent spoof has near-zero innovation after its first block. The surprise EMA (citadel.py _surprise_ratio) also updates on every block, so a sustained attack erodes the threshold tightening and lowers eta_b afterwards. The attack window is drawn in blocks 10-50 and FRR counts b >= 5, so the warm-up, where g-bars, I-bar (maximum of the first three innovations) and the surprise median are initialized, was never attacked. Theorem 1 bounds the slow weights only, not this state.

**Fix.** (1) Ratchet attack: in phase 1 (R = 50, 100, 200 blocks), each block's perturbation is bisected with the exact receiver copy so the block is accepted with g1 just under tau1 and g2 just above tau2. Phase 2 is 40 blocks of A1 or soft-gate at 0 dB. Report the trajectories of g1bar, g2bar, I-bar and S-bar, the phase-2 acceptance and excess, and D_K, against A1 alone; 10 seeds. (2) Cold-start attack: window starting at block 0 (blocks 0-39 and 0-99), A1 and soft-gate, 10 seeds. (3) A consistent channel spoof S_b Delta^T with Delta drifting by a small step per block, against G3. (4) If any of these succeeds, harden the design: clamp each normalizer to [0.8, 1.25] of its calibration value or derive it from the slow memory, advance H_{b-1} only on accepted blocks, gate the S-bar update, and seed the statistics from pre-deployment calibration. Then re-run the headline cell and add a bound on the drift of the gate state to Sec. IV.

### 4. The reference-degradation attacker A4 cannot degrade the references, and it has not converged (major, experiment)

Sec. VI-D, Table VI, eq. (9). In _soft_ctx/_soft_gamma (attacks/pilot_poisoning.py), pass_ref and r_ref are constants computed from the unperturbed data, with LMMSE on the clean-pilot LS estimate and the anchor on y_d. The objective's gradient with respect to the data perturbation E_d and the pilot perturbation E therefore has no term that lowers F_ref = max{F_mm, F_a} or raises R_ref. The only signals are the fast level's data loss and its soft pass rate, which pull in opposite directions. The mechanism the text attributes to A4 ('degrades the references with the fast level') is incidental to an objective blind to the references. The objective also ignores the CRC selection (26): in rejected blocks the emitted output is the anchor or LMMSE, which the data perturbation could target directly. The optimization is not converged: going from 6 to 20 PGD steps raised the excess from +0.0337 to +0.0478. Only alpha in {0.25, 0.75}, one restart and five seeds were run, and the paper says that 'one with an exact model of the gates was not run'. This is the attack class the paper itself identifies as the weak point, so it needs the strongest treatment, not the weakest.

**Fix.** Re-implement A4 with differentiable references: the soft CRC pass of the anchor on y_d+E_d, and of LMMSE(H_b(E), sigma_b^2(E)) on y_d+E_d, and the G1 reference min{R(s_mm), R(s_a)} with posterior-mean symbols and the poisoned H_b(E). Use as objective the soft error of the CRC-selected output (a soft-min over the three candidates' soft passes) plus the soft acceptance, with C&W-style constant search. Run PGD with 20, 50, 100 and 200 steps x 5 restarts until the excess plateaus, and plot excess against steps. Sweep alpha in {0.05, 0.1, 0.25, 0.5, 0.75, 0.9}, seeds 10-19. Add an equal-total-energy comparison with A1 and with data jamming, and report the reference pass rates F_mm and F_a under attack.

### 5. The retention attacker A3* does not attack retention, and the retention bound is not tied to harm (major, experiment)

Sec. IV, Theorem 1, Table VII, Fig. 4(b). With soft gates enabled, A3*'s objective is the per-block soft-gate data loss (_attack_obj takes the ctx branch), so the spoofed basin theta_bad computed in craft() is never used. The paper admits that the objective 'has no term for the displacement of the slow level' and that 'an attacker that maximizes D_K subject to acceptance was not run'. The design bound (30) follows directly from the clip and is weak at the reported scales: 90 (300 blocks) and 261 (900 blocks), against a clean movement of 26.8. It grows without limit in W, and with the drift guard it saturates near 0.95*2*kappa_K/0.05, about 171. A Euclidean weight distance says nothing about SER: a small move in a sensitive direction may wreck the anchor. Every attacker here is myopic (one block at a time). None times its accepted perturbations to the consolidation instants of (18), none shares a target direction across blocks, and none erodes the anchor reference F_a before attacking.

**Fix.** (a) Directed drift attacker: maximize the inner product of theta-tilde(E) - theta^(K) with a fixed d, subject to exact acceptance, over 300 and 900 blocks at 5%, 10% and 20% of the pilot norm. Take d toward a weight state with high SER on channel phases the attacker predicts (it knows the cosine periods P_u), or toward a single target user. Report D_K against (30)/(31), and the anchor's SER on held-out clean blocks during and after the attack. (b) Sleeper-then-trigger: run (a) for 300 blocks, then 40 blocks of A1 at 0 dB, which forces fallback to the eroded anchor. Compare the phase-2 excess with +0.0188. (c) Turn the parameter bound into an output statement: worst-case anchor SER over ||delta|| <= r by PGD in weight space (r = kappa_3, 2*kappa_3, 18, 90) and over random directions of the same norms; report SER(r) next to Table VII. If SER(kappa_3) is already large, say plainly that Theorem 1 gives no SER guarantee.

### 6. Denial of adaptation and the 'never adapt' baseline are under-evaluated (major, experiment)

The defense turns accepted poisoning into a forced fallback to the anchor. The headline cost (+0.0188) is measured only where the anchor is close to the fast level: a 40-block window on SED cosine fading. Only short denial experiments exist (Table VI: one redraw, spoof at 10 dB, point estimates on five seeds). No persistent attack under continuous drift (Jakes at several Doppler values, COST2100) was run, and lock-in after long attacks (the G3 predictor and S-bar are stale) was not measured. The trivially secure defense, pre-trained DeepSIC without test-time training (zero poisoning excess by construction), was not run (Sec. VI-F), so it is unknown whether Citadel-Rx improves on 'do not adapt' on the clean/attacked frontier.

**Fix.** Run the frozen pre-trained DeepSIC, with and without CRC selection, in Tables IV and VIII (clean SER and excess, seeds 10-19). Run a continuous A1 or soft-gate attack at 0 and 10 dB with windows of 100, 300 and 1000 blocks, on Jakes (f_D*T_block in {1e-3, 1e-2}) and COST2100, and after a redraw, with streak recovery on and off. Report excess against window length, time to recover after the attack, and the post-attack false-rejection rate, for Citadel-Rx, online DeepSIC, LMMSE and frozen DeepSIC.

### 7. Claims and statistics overstate what the adaptive-attack tables show (major, analysis)

The abstract says 'Attacks adapted to the gates or their feedback leave the excess unchanged within its intervals', and Sec. II-B says white-box attackers 'bound from above what a causal attacker can know'. Maximal knowledge is not maximal strength: these attacks were mis-optimized (see the first item), all at full budget and rejected on 95-100% of blocks. Table V uses five seeds, with intervals spanning a factor of about 2.4 (e.g., [0.0120, 0.0284]), so 'unchanged within intervals' cannot detect differences of the size that matter. The paper itself notes that 'when nearly every attacked block is rejected, the excess depends on the perturbation's power, not its optimization'. The SIR 10 dB adaptive results are given as an untabulated range.

**Fix.** Rephrase the abstract, Sec. VI-C and the conclusion as: 'the attacks tested, all at full budget and rejected on at least 95% of blocks, gave the same excess as plain A1'. Separate knowledge from optimization strength in the threat model. For each Table V row, report the per-seed paired difference (adaptive minus plain A1, same seeds, machine and clean twin) with a 95% CI and a TOST equivalence test at a pre-specified margin (e.g., +/-0.005) on seeds 10-19. Also report each attack's predicted and realized acceptance, and tabulate the SIR 10 dB rows.

### 8. Standard adaptive-attack sanity checks are missing (major, experiment)

The checklists the paper cites ([7], [8]) ask for: an attack that beats random noise of the same budget; convergence curves; success at large budget, or against the defense with the attacked component removed, using the same adaptive attack; white-box at least as strong as transfer and query attacks; and checks for gradient masking (vanishing gradients through 50 unrolled steps or saturated sigmoids). The only noise control is on the data (jamming, Sec. VI-A), not the pilots. If Gaussian pilot noise at 0 dB also gives about +0.019 with 100% rejection, the optimized attacks add nothing measurable. The fact that unroll 10 and unroll 50 give identical numbers (+0.0193, +0.0192) is consistent with either vanishing or ineffective gradients. EOT averages over pilot-noise draws that a white-box attacker already knows, and the receiver is deterministic, so EOT models no randomness of the defense and can only blur the objective.

**Fix.** Add (i) a random-pilot-perturbation control (Gaussian E scaled to eps at SIR 0 and 10 dB, seeds 10-19) to Table V; (ii) attack-objective and true-excess curves against PGD iteration and restart; (iii) the same adaptive attack against 'no gates' and 'G3 only' (Table IX), to show it succeeds where it should; (iv) gradient norms through unroll depths 2/10/50 and the fraction of saturated soft steps; (v) EOT kept only for the causal or transfer attacker (unknown noise), with a text change saying so.

### 9. The CRC is a forgeable integrity check under the paper's own '+data' threat model (major, experiment)

G2 (21), the design rule (27)-(28), the CRC selection (26), the virtual pass rate and streak recovery all treat a CRC pass as proof of correct decisions. CRC-8 (D^8+D^7+D^4+D^3+D+1) is linear: any error pattern that is a multiple of g(D) passes. With 64 bits per sub-block, low-weight undetectable patterns exist. The soft-gate, A3* and A4 attackers are granted the data and its symbols (Table II, '+data'), and A4 can perturb the data, so it can steer the anchor's, LMMSE's or the fast level's decisions onto CRC-valid wrong words. The 2^-B term in (27) assumes random errors and does not hold against an adversary. The paper neither excludes this attack in the threat model nor tests it.

**Fix.** Either state in Sec. II-B that the attacker cannot target CRC-valid error patterns and argue why, or add a CRC-forgery A4: a data perturbation that pushes each targeted candidate to the nearest CRC-valid wrong word (enumerate the minimum-weight multiples of g(D) within 64 bits, choose the pattern needing the least energy, and project onto the alpha budget). Report the undetected-error rate, the G2 verdicts, F_ref and the excess SER, at SIR 0 and 10 dB, seeds 10-14. Discuss CRC-24A in the coded scene.

### 10. Query and gray-box attackers are too weak to support claims about feedback (minor, experiment)

Table V 'Query (NACK)': one NES query per block over 40 blocks, full budget; the paper concedes it is 'not converged'. It therefore supports nothing about attacks 'adapted to ... their feedback' (abstract). ACK/NACK reveals acceptance (a rejected block falls back to the anchor), so a decision-based boundary attack is the natural adversary. The gray-box attacker transfers plain A1 through a Citadel-Rx surrogate without the soft-gate objective.

**Fix.** Either remove the feedback claim, or run a decision-based attack (HopSkipJump- or boundary-style) on the ACK/NACK signal. Allow several queries per block through HARQ retransmissions (e.g., 4) or run 1000-block horizons, search over the norm as well as the direction, and report convergence. Give the gray-box surrogate the exact-forward attack of the first item.

### 11. Positioning against the poisoning and robust-aggregation literature is missing, and so are the matching baselines (minor, text)

Sec. I and Table I cite TTA poisoning ([23]-[26]) but omit the work closest to this design. Bilevel and back-gradient poisoning (Biggio et al. 2012; Munoz-Gonzalez et al. 2017; MetaPoison 2020; Witches' Brew 2021) gives the attack methodology the first item needs. Koh, Steinhardt and Liang (2022, 'Stronger data poisoning attacks break data sanitization defenses') show that anomaly-filter defenses fall to attacks constrained to pass the filter, which is the open question here. Carlini and Wagner (2017) bypassed ten detectors. Norm-bounding and robust aggregation in federated learning (Sun et al. 2019; Blanchard et al. 2017; Yin et al. 2018) are the direct analogues of the consolidation clip and the gated mean (18). Steinhardt et al. (2017) give certified poisoning bounds to compare with Theorem 1.

**Fix.** Add these references, and state how the clip and the gated mean relate to norm-bounding and robust aggregation. Add to Table VIII consolidation baselines that replace the gated mean (18) by a coordinate-wise median, a trimmed mean (20%) and Krum over the buffered states, without gates, under A1 and A3* (seeds 10-14).

### 12. Adaptive attacks are not run on the other settings used to claim generality (minor, experiment)

The abstract says 'the ordering holds with a second backbone and with 8x32 arrays', but Table X runs only plain A1 at 0 dB on three or five seeds. On the joint-symbol backbone the clean false rejection is 0.217, which leaves a wide acceptance region for an adaptive attacker.

**Fix.** Run the exact-forward constrained attack (first and second items) on the joint-symbol backbone, 4x16 and 8x32 at SIR 0 and 10 dB, five seeds, or limit the abstract's generality claim to plain A1.

### 13. Physical realizability of the white-box perturbations is not validated over the air (minor, not_fixable_now)

Every attack except the 'physical' rows is a digital additive injection on the received baseband pilots, with perfect symbol and frame synchronization and knowledge of the received noise. The physical model (10) adds only a linear channel with estimation error. Carrier frequency offset, timing jitter, attacker PA nonlinearity and the latency of computing a white-box perturbation within a slot are not modeled, so whether the reported attacker strength can be achieved, in either direction, is unknown.

**Fix.** Over-the-air validation with a software-defined-radio attacker transmitting precomputed and causally computed pilot perturbations against a base-station testbed, reporting the achieved SIR and the gate outcomes. This needs hardware that is not available; meanwhile, state the limitation in Sec. VII and simulate CFO and timing offsets on the attacker's signal.

## Reviewer: Statistics and reproducibility (score 5)

Major revision. The paper is unusually candid and fully scripted from records, but four things stop it from being accepted as is. (1) The "held-out seeds" share one deterministic, real-valued channel. (2) Most contrasts use 5 seeds and are judged by overlapping marginal intervals. (3) The adaptive attacks show clear signs of under-optimization. (4) Theorem 1 does not explain or bound the protection that is measured. Several abstract claims go beyond what the tables support.

### 1. Seeds do not vary the channel: every calibration and test seed sees the same deterministic, real-valued trajectory (major, experiment)

The main channel (eq. 2; Table III) is H_b = exp(-|nu-u|)*(0.8+0.2cos(2*pi*b/P_u)). It is fully deterministic and real-valued. In citadel_rx/channels/base.py `_synthetic`, mode 'cosine' uses no RNG, and the docstring says complex QPSK passes 'through a real gain matrix'. Seeds 0-2 (calibration) and 10-19 (test) therefore see the identical channel sequence. Only the noise, the symbols and the window start (seed+9090) change. The 'held-out seeds', the bootstrap intervals and the Wilcoxon tests therefore describe noise and symbol variability on one channel path, not channel generalization. Fig. 3(a) shows the same periodic dips for every receiver. COST2100 enters only calibration, and Jakes (also real-valued) is used only for the Lipschitz probes of Remark 1. The one complex, stochastic channel is the UMi scene of Sec. VI-H, and there the method fails. Sec. II-A writes H_b in C^{NxU}, and Sec. II-C speaks of 'channel draws', which misleads the reader.

**Fix.** State in Sec. II-A, Table III and the abstract that the SED channel is real and deterministic and identical across seeds. Re-run the headline cell (Table IV: Citadel-Rx and the four baselines, clean and A1 at 0 dB) and the A4 alpha=0.25 and A3* 20% rows on a stochastic complex channel with one realization per seed. Use complex Gauss-Markov fading around the SED mean, H_{b+1} = rho*H_b + sqrt(1-rho^2)*W_b with W_b ~ CN, plus a uniform random initial phase per user, at f_D*T_b in {0.01, 0.05}. Also run COST2100 with a seed-dependent starting frame, with test seeds 10-19 and frozen settings. Report the same columns and paired tests as Table IV.

### 2. Five seeds and comparisons by overlapping marginal intervals cannot support 'unchanged' or 'raises' claims (major, experiment)

Tables V, VI, VIII, IX and X use 5 seeds. The exact Wilcoxon test then cannot go below p=0.0625 (stated in Sec. V), so no contrast outside the headline can be significant at 0.05. The abstract and Sec. VI-C say adapted attacks 'leave the excess unchanged within its intervals' and that 'differences of a few 10^-3 lie within the intervals'. Both are absence-of-evidence inferences from overlapping marginal CIs. Conversely, 'attacks on the references ... can raise the excess' rests on A4 +0.0337 [0.0204, 0.0470] against A1 +0.0196 [0.0126, 0.0287], which overlap, and on the 20-step A4 +0.0478 [0.0279, 0.0689]. 'The ordering holds with a second backbone and 8x32 arrays' (abstract) is backed by point estimates only. Every attacked run shares its seed, window and clean twin, so a paired contrast is available and much tighter: two machines give A1 values that differ by only 3e-4. No such contrast is computed. No sample-size or minimal-detectable-effect justification is given.

**Fix.** Extend Tables V, VI, IX and X to seeds 10-19; scripts/extend_seeds.py already exists. For each row, compute the per-seed paired difference of window SER against the A1 reference row on the same seeds and twins. Report its mean with a t-interval (df=9) and a BCa interval, plus a Holm-adjusted exact Wilcoxon p within each table. Back each 'unchanged' claim with a TOST equivalence test at a margin fixed in advance (for example +/-0.005 absolute excess). Back each 'raises' claim with a one-sided paired test. Report the minimal detectable difference at 80% power, from the observed paired SD, for every contrast called null.

### 3. Adaptive attacks look under-optimized: gate-aware attacks never get a block accepted, and A4 is far weaker than noise of the same power (major, experiment)

In Table V the soft-gate and 'Combined' attacks get 0/200 blocks accepted (Rej. 1.000). Yet a 5%-norm perturbation is accepted 599/600 times (A3*, Table VII), and the budget in (5)-(7) is an inequality that allows smaller perturbations. An attack that optimizes for acceptance should therefore never do worse than shrinking toward an accepted norm. The surrogate (8) leaves out G3 and the surprise tightening of (24), and the paper itself says these 'replace the hard gates'. A4 at alpha=0.25 gives +0.0337, while Gaussian noise with A4's data power gives +0.785 (numbers.tex a4.jam025; extended Sec. VI-D). The optimized perturbation is thus about 23 times weaker than random noise of the same budget, which is a standard warning sign [7], [8]. docs/G1_SOFT_FIX.md shows the pre-fix surrogate gave a stronger A4 (+0.0531, 110/200 rejected). That variant is still a valid attacker, yet the paper reports only the weaker corrected one. A4 stops at 20 PGD steps with 'more may understate' (Sec. VI-D). 'An attacker with an exact model of the gates was not run.'

**Fix.** (a) Implement an exact-gate attacker. It uses the real forward gates, including the tightening tau_{i,b}, G3, the running statistics and the CRC pass fraction, with BPDA or straight-through gradients for the CRC. (b) Add a maximal-accepted-budget attack. For each block, binary-search (8 steps) the largest scale s in [0,1] of the A1 perturbation with hard gamma_b >= 1/2, and apply it over 40-block and 300-block windows. (c) Plot an A4 convergence curve at 6, 20, 50 and 100 PGD steps with 5 restarts, and sweep the G1-term weight over {0.5, 1, 2}. (d) Check that every adaptive attack beats random-direction perturbations of equal norm and Gaussian noise of equal budget. (e) Use seeds 10-19 throughout. Report the worst case over all variants as the security figure in the abstract and the conclusion, including the half-scale-G1 variant and the jamming-equivalent budget.

### 4. The pre-trained no-adaptation control is missing, so the value of test-time learning is unmeasured (major, experiment)

Sec. VI-F: 'its limit, pre-trained DeepSIC without test-time training (zero excess by construction), was not run, so the clean gain of adaptation over it is not measured.' Under attack Citadel-Rx rejects 99% of blocks and runs on the anchor (Sec. III-D). theta_pre is trained on the static SED mean (runner.py `pretraining_blocks`, fading 'static'), close to the cosine channel. A frozen theta_pre with the same CRC selection over (s_pre, s_mm) could have near-zero excess and a competitive clean SER. If so, the headline comparison against tuned online DeepSIC overstates the case for multi-rate gated memory.

**Fix.** Run frozen theta_pre DeepSIC, and frozen theta_pre with per-sub-block CRC selection against LMMSE, on seeds 10-19 (clean, and A1 at SIR -10, 0, +10 dB). Add both as rows of Table IV, with paired Wilcoxon and Holm tests on window SER and clean SER against Citadel-Rx. Repeat on the stochastic channel of the first item, where a frozen network should lose most.

### 5. Tuning is asymmetric: the defense is selected on attacked performance, the baselines only on clean SER, and the L2-SP sweep runs on test seeds (major, experiment)

Sec. V selects the Citadel-Rx candidate by the mean of the clean, A1 and COST2100 A1 window SERs on seeds 0-2. Online and Meta-DeepSIC are tuned on clean calibration runs only, and 'the baselines' own method settings are not tuned'. L2-SP is swept on test seeds 10-14 (Table VIII). The sweep stops at weight 1, where the excess is still falling (+0.785, +0.762, +0.590, +0.136). The EATA-style filter never fired (0.38 against 0.55 nats), so that row duplicates EWC to the last digit and is not a functioning baseline.

**Fix.** Re-tune every baseline's own hyperparameters with the identical selection rule on seeds 0-2 (same score, same 2% false-rejection cap), then freeze them and evaluate on seeds 10-19. Grids: L2-SP weight {0.01, 0.1, 1, 3, 10, 100}; EWC lambda over 4 decades; EMA decay {0.9, 0.99, 0.999}; CoTTA restore p {0.001, 0.01, 0.1}; drift threshold {1, 2, 3}; online epochs and lr as already done. Either set the EATA entropy margin so the filter fires on calibration (for example 0.4*ln 4 rescaled to the observed entropy range), or drop the row. Report the tuned settings in a table.

### 6. Theorem 1 neither explains nor bounds the protection that is measured (major, analysis)

Part (i), eq. (30), is the triangle inequality applied to the clip. The clip binds in 5/150 clean and 12/150 attacked consolidations, and removing it leaves the excess unchanged (Table IX). The design bound (90.0 for A3*) is 3.4 times the clean movement of the level (26.8), so it permits more poisoning than legitimate drift. Part (ii), eq. (31), needs Delta(W) and the clean-run weights, so it is an a-posteriori decomposition ('a diagnostic of an experiment'). Neither part involves the attack budget epsilon_b, the gate miss probability or the SER. D_K (12) counts benign lag as displacement: under A1 the attacked level moved 4.8 against 8.4 at cosine 0.94, so most of D_K=4.17 is lag. After the window D_K keeps rising (4.85; 15.16 at the end of the 900-block run), with no statement on decay. The conditions of (i) with the drift guard and of (ii) fail with the abstain state, and the text does not say which reported runs satisfy them.

**Fix.** (1) Add the a-priori statement that the corrected rule (18) makes possible. If every poisoned block of the window is rejected and streak recovery is off, then by (26) and Lemma 1 every level of the attacked run stays in conv{theta^(k)_{b0-1}, k=1..K} (union theta_pre with the guard). Hence D_K is at most the diameter of that hull plus the clean movement over the window. Each accepted poisoned block adds at most the fast map's per-block displacement bound, which can be stated a priori from T, eta_max and the Adam step bound, or measured as G_adapt. (2) Decompose D_K in Table VII into lag along the clean movement and an orthogonal (poisoning) component; the snapshots already exist. (3) Map D_K to error rate: freeze the attacked and clean slow levels at the end of the window, run the anchor detector on 20 fresh clean blocks per seed, and report the SER gap against D_K. (4) Mark each Table VII row as satisfying or not satisfying the conditions of (i) and (ii).

### 7. The persistence endpoint (harm after the attack) is under-reported, although it is the paper's thesis (major, experiment)

The paper argues that 'the harm lies ... in what the receiver keeps'. Yet the 'After' column of Table IV has no interval or test. It averages 10 to 30 blocks per seed, because windows start anywhere in 10-50 within 100-block runs. Recovery time is computed in eval/metrics.py `recovery_blocks` but not reported. Tables V, VI, IX and X give no post-window excess at all. Online DeepSIC's own post-window excess is only +0.0189 against +0.768 in the window, which contradicts the framing that persistence dominates for that baseline. No post-window rejection rate is given for Citadel-Rx, as is done for CRC-Rollback (1.00).

**Fix.** Extend runs to 200 blocks so that every seed has at least 60 post-window blocks. For every receiver and every attack row, report post-window excess with an interval and a paired test, recovery time with censoring (Kaplan-Meier median), Citadel-Rx's post-window rejection rate, and D_K(t) up to block 200. Either support the claim 'harm lies less in the attacked block' with a 1-block-window attack (W=1 at random blocks, excess in blocks b+1..b+30 per receiver), or soften it in Sec. I.

### 8. Abstract and conclusion claims go beyond the tables (major, text)

(a) '0.1% false-rejection rate' holds only on the stationary SED channel. False rejection is 0.180 after a legitimate redraw (Sec. VI-D), 0.021-0.025 at Nd=1000 (above the 2% cap), 0.217 with the joint-symbol backbone and 0.979 at 16-QAM (Table X). (b) The title says 'Three-Rate', but K=2 gives +0.0242 [0.0181, 0.0306] against +0.0199 (Table IX, overlapping), so the third rate is not shown to be needed. (c) Contribution 3 claims 'a CRC threshold set by a target excess symbol-error probability'. The evaluated receiver uses the relative slack with rho=1 and floor 2e-3, which 'were not derived' (Sec. III-E). The derived slack lost calibration by 0.0008 on 3 seeds (numbers.tex: cal.*.score 0.0133 against 0.0141) and was not run at Nd=1000. (d) The headline +0.0188 is the plain A1 cell, not the worst case found: A4 reaches +0.0478, the pre-fix A4 +0.0531 and the spoof during a redraw +0.0968. (e) During a legitimate redraw Citadel-Rx's SER after the change (0.250) is worse than online DeepSIC's (0.224); the abstract omits this cost.

**Fix.** Rewrite the abstract, the contributions and the conclusion. Qualify the 0.1% figure by channel and block length, and add the redraw false-rejection rate and its cost. Headline the worst case over the attack suite next to plain A1. Either retitle (for example 'Multi-Rate'), or run K=2 against K=3 paired on seeds 10-19 under A1, A4 and A3* and keep 'Three-Rate' only if K=3 is better. Either evaluate the derived slack on test seeds 10-19 and at Nd=1000 and 5000, or move the design rule out of the contributions.

### 9. Gate ablation runs only where the gates are not stressed, and the main lesson is never isolated (major, experiment)

Table IX ablates under A1 only. There G2 alone matches the full receiver (+0.0194 against +0.0199), so G1 and G3 have no measured role. They were never ablated under A4, A3* or the redraw, where the references degrade. The conclusion's first lesson ('a gate protects a memory only if it judges updates against that memory') is inferred by comparing different receivers (CRC-Rollback, K=1). It is not tested by removing the anchor from the reference (R_ref and F_ref in (23)) while keeping everything else. The reversion, the delta-rule decay and the surprise step are 'not ablated'.

**Fix.** Re-run the Table IX ablations (G1 only, G2 only, G3 only, no fallback, K=2, no clip) under A4 alpha=0.25, A3* 20% and the redraw, on seeds 10-19. Add an ablation that uses LMMSE only as the reference, with R_ref = R_b(s_mm) and F_ref = F_mm, keeping the slow levels, the fallback and the selection. Also add ablations of the reversion, of the delta rule (delta=0) and of a constant step size (r_b=1). Report paired contrasts against the complete receiver.

### 10. No sweep across the detection boundary, where the worst case lies (major, experiment)

A1 is evaluated only at SIR -10, 0 and +10 dB. Rejection falls from 0.96 (A1, +10 dB) to 0.225 (A3* 20%, about +14 dB) and to 0.002 (A3* 5%, about +26 dB). The most damaging perturbation for the memory sits near this transition, yet 'an attacker that maximizes D_K subject to acceptance was not run' and 'the weakest rejected perturbation was not searched for' (Secs. VI-D, VI-E).

**Fix.** Run A1 and the maximal-accepted attack of the adaptive-attack item at SIR 10, 12, 14, 16, 18, 20, 25 and 30 dB on seeds 10-19. Report rejection rate, window and post-window excess, and D_K against SIR, together with the false-rejection rate. Mark the SIR that maximizes post-window excess and D_K, and the smallest SIR rejected on 95% of blocks. Use that SIR as the denial budget in Table VI.

### 11. A3*, the long horizon and the sensitivity study are too small to support their conclusions (major, experiment)

Table VII (A3*) uses 2 seeds, and the caption admits 'an interval reflects mostly the variation between blocks'. A seed-level bootstrap over 2 seeds is not a valid interval. A3* is the case 'the bounds are for'. The 2000-block clean horizon also uses 2 seeds. The sensitivity study is one seed (seed 10), one at a time, under A1 only, and its false-rejection rate (up to 0.053) rests on 95 blocks. Yet Sec. VI-F concludes 'no setting is critical for the excess within a factor of two'.

**Fix.** Run A3* at 5, 20 and 50%, with and without the guard, on at least 5 and preferably 10 seeds, with snapshots for D_K. Run the long horizon on 5 seeds. Redo the sensitivity study on calibration seeds 0-2, so that test seeds stay untouched, under both A1 and A4 alpha=0.25: a 40-point Latin hypercube over the eight settings in [0.5x, 2x], with partial rank correlations or Sobol indices for excess and false rejection.

### 12. Calibration/test separation is partly compromised, and test seeds 10-14 were reused across revision rounds (major, experiment)

Table III lists two post-hoc changes: the abstain statistic was revised after test runs on seeds 10-12, and the stretched SED profile was adopted after test runs. L2-SP weights were swept on test seeds. docs/REVISION_PLAN.md (line 47) notes unreported A4 results of an earlier abstain version on seeds 10-12. Seeds 10-14 underlie almost every table and have shaped several design iterations. Table III says kappa was set 'before calibration', while Sec. III-B says it was set from 'the calibration runs'. Only seeds 15-19 are fresh, and only for the headline cell.

**Fix.** Commit the frozen configuration and its hash before a final confirmatory run, and cite the commit in Sec. V. Re-run the primary cell of every table on fresh seeds 20-29 and report it next to the current numbers. Add a provenance table listing every choice made after any test-seed result, with the seeds that informed it. Clarify where kappa comes from.

### 13. The interval method is unvalidated for 5 seeds and for non-stationary windows (minor, analysis)

Sec. V uses a two-stage percentile moving-block bootstrap: seeds, then circular stretches of twice the decorrelation length inside a 40-block window. The SED channel is periodic (21-51 blocks), so the excess series is non-stationary and the 1/e autocorrelation length mixes a deterministic trend with dependence. Circular wrapping joins the start and end of the window, which differ. Percentile intervals over S=5 resampled seeds are known to under-cover. No coverage check is reported.

**Fix.** Make seed-level intervals on per-seed means the primary interval (t with df=S-1, and BCa), and keep the moving-block bootstrap as a sensitivity check. Verify coverage empirically: draw A/A null pairs (clean against clean with independent noise seeds, or a placebo 'attack' with zero budget) over 200 resamples, and report the realized coverage of both interval types.

### 14. Rejection and false-rejection rates lack valid intervals outside the headline (minor, analysis)

The Wilson intervals at the headline cell (397/400; 1/950) assume independent blocks, which the paper itself calls 'too narrow'. Every other 'Rej.' and 'False rej.' entry in Tables V-X is a bare rate. Pooling blocks hides between-seed heterogeneity: the spoof rejection rate ranges from 0.04 to 0.32 per seed (numbers.tex deny.citadel.rejattmin/max).

**Fix.** Report seed-cluster bootstrap or beta-binomial intervals for every rejection and false-rejection rate, with the per-seed min-max. Add a gate ROC: rejection against false rejection as the threshold 1/2 varies, for gamma and for each g_i, at SIR 0, 10 and 20 dB, with the AUC and its cluster-bootstrap interval.

### 15. No declared hierarchy of endpoints for multiple comparisons (minor, text)

Holm correction covers only the four baselines at the headline cell (two families). The paper reports more than 100 intervals and many directional statements across Tables V-X and Fig. 3(d) ('the lowest excess at SIR +/-10 dB and under transfer', 'ordering holds') with no family structure. docs/STATS_REVISION.md lists families that the paper does not.

**Fix.** Declare the primary endpoints in Sec. V: window excess and post-window excess at the headline cell against the four baselines. Declare one secondary family per table with Holm or Benjamini-Hochberg correction. Label everything else as exploratory, and add a one-line list of families and their sizes.

### 16. Excess SER alone rewards a worse clean twin, and absolute performance is missing from most tables (minor, text)

In Table IX, 'No CRC selection' gives +0.0053 and 'No anchor' +0.0130. Both are lower than the complete receiver 'only because the clean twin is worse'. Tables V, VI, IX and X give no attacked window SER, so readers cannot compare operating points. The 70% share of the clean gain attributed to CRC selection (Sec. VI-A) has no uncertainty. Fig. 3(d) mixes 10 seeds at 0 dB with 5 elsewhere. The A1 row of Table VII (+0.0137) differs from the headline (+0.0188/+0.0199) because its window is fixed at 30-69; the text does not say so.

**Fix.** Add attacked window SER and clean SER columns to every table, plus an SNR-equivalent degradation in dB (the code exists in eval/metrics.py `degradation_db`). Add a bootstrap interval for the 70% share. Use the same seed set across Fig. 3(d), or mark which points use which seeds. Explain the fixed-window difference of Table VII.

### 17. Testable assumptions of the CRC design rule are left unchecked (minor, analysis)

Sec. III-E: (27) and the Hoeffding bound assume i.i.d. symbol errors and independent checks, and 'the independence of errors within a sub-block was not checked against the records'. The records hold per-block SER and CRC outcomes, so this can be checked now. Correlated errors would make J_c=JU overstate the effective number of checks and bias tau_2.

**Fix.** From the stored records, plot the observed per-user sub-block pass fraction against (1-p_hat)^L. Estimate the dispersion index of CRC failures across sub-blocks and the implied effective number of independent checks. Report how much tau_2 would move.

### 18. Causal explanations of the failure cases are stated but not tested, although they are testable (minor, experiment)

Sec. VI-H: 'the phase rotation is the likely cause, not an established one'. Sec. VI-G (16-QAM): the narrow width 'may contribute, and a wider one was not tested'. Both shape the conclusion's second lesson and its open directions.

**Fix.** Run the UMi scene with per-user phases held fixed, or with common-phase derotation from the LS estimate before the network, keeping all else equal (seeds 10-14 or 10-19). Run 16-QAM with width 1024, tuned on seeds 0-2. Report clean BLER/SER, the network's CRC pass fraction against LMMSE, and the excess.

### 19. A single SNR operating point (minor, experiment)

Every QPSK result is at SNR 10 dB (Table III). The relative gates and the reference quality depend on SNR, so false rejection, rejection and excess may change materially at lower SNR, where the network and LMMSE are closer.

**Fix.** Repeat the clean and A1 at 0 dB headline for Citadel-Rx and online DeepSIC at SNR 4, 7, 13 and 16 dB on seeds 10-19. Report clean SER, excess, rejection and false rejection against SNR.

### 20. Cross-machine nondeterminism and the software stack are not quantified (minor, text)

The same configuration and seeds give A1 excess +0.0196 on one machine and +0.0199 on another (Sec. VI-C). The MacBook's clean twins differ from the cloud machines' (docs/G1_SOFT_FIX.md). A4 re-runs are paired with twins from other machines through `pairs_as`. The paper does not state the PyTorch, NumPy or BLAS versions, the thread settings, or the size of the cross-machine discrepancy.

**Fix.** Add a reproducibility paragraph: software versions, thread and determinism flags, and the commit hash for each table's records. Add an A/A table: the headline cell re-run on 3 machines, with the spread of excess and rejection rate, to show this noise is far below every effect claimed.

### 21. No measured-channel or over-the-air validation of the attack and the gates (minor, not_fixable_now)

Every result is simulated: SED, COST2100 traces only in calibration, and stochastic UMi drops that are not ray-traced (Sec. VII, Assumptions). The physical attacker's CSI model and synchronization are idealized.

**Fix.** Validate with an SDR testbed (an attacker transmitter synchronized to the pilots) or with measured MIMO channel traces. This needs hardware or data the authors do not have now; for the present version, state it as a limitation.

## Merged and checked list, ranked

The three reviews (scores 4, 5, 5; 16 + 13 + 21 = 50 weaknesses) merge into 29 items. I checked each against main.tex, numbers.tex, the code and the run records. Nearly every claim holds, so almost nothing could be dropped outright. Most items the paper discloses but does not fix; those are kept.

**Confirmed against code and records:**
- **Channel:** the cosine channel is real and has no random draw, so every seed sees the same channel. Pre-training uses the static channel, which equals block 0 of the test channel.
- **ML baseline (re-run of R1's Monte Carlo):** ML with the LS estimate has SER 0.0061. LMMSE has 0.0512, Citadel-Rx 0.0159 and online DeepSIC 0.0330.
- **Combined adaptive attack:** the objective has median -0.058 and is above -0.5 on 200/200 blocks, so the surrogate predicts acceptance. The receiver accepted 0/200. The fast level passes 0.018 of CRCs against 0.82 for the reference.
- **Full budget:** ||E||/eps >= 0.999 on 100% of unroll/PGD/combined blocks and 96-97% of soft-gate blocks.
- **A4:** its references (pass_ref, r_ref) are constants computed from clean pilots, so it cannot degrade them.
- **A3\*:** with soft gates it never uses theta_bad.
- **Gate state:** the channel tracker's H_prev and the surprise EMA are updated on rejected blocks too.
- **Coded scene:** LDPC decoding uses hard decisions with |LLR| = 3, and sionna_pusch.py raises NotImplementedError.
- **Not yet run:** the exact-copy oracle attacker (commit aef1471) and extend_seeds.py are committed, but no results exist and the paper reports nothing from them.

**Dropped or corrected sub-claims:**
- R3: Fig. 3(d) mixing seeds is stated in the caption.
- R3: the kappa wording in Table III vs Sec. III-B is a check, not a contradiction.
- R1: the claim that the deep receivers "fail to re-adapt" after the redraw is unsupported. LMMSE does worse there (0.351 against 0.250 and 0.224), so the redrawn channel is simply harder.
- R2: the "BPDA" mislabel is only in the extended version (and the code docstring), not the main paper.
- R2: oracle_scales is now committed, not uncommitted.
- R2: the "1.000 on every block" norm claim is 96-97% for the soft-gate rows.
- Text parts already addressed:
  - the SNR and SER definitions (eq. 1, Sec. II-C);
  - "bounds are on weights, not error rate" (Sec. VII);
  - Table VII's fixed window (caption);
  - the coded-scene simplifications (Table III);
  - the Wilson-interval, EATA and L2-SP caveats.

The remedies for all of these still stand.

**Ranking.** Twelve items are high impact, because they undercut the paper's two main claims (generalization and security against adaptive attacks) or its motivation:
1. the deterministic real channel shared by all seeds;
2. adaptive attacks that do not model the defense and never search the acceptance boundary;
3. ML, K-best and MMSE-SIC baselines;
4. robust model-based defenses (tracked CSI with a pilot-residual test);
5. the frozen pre-trained control;
6. claims in the abstract and conclusion beyond the tables;
7. paired statistics on 10 seeds;
8. a correctly specified A4;
9. standard attack sanity checks;
10. an SIR sweep with ROC curves;
11. ratchet and cold-start attacks on the gate state;
12. a directed A3* attacker on 5+ seeds;
13. the phase-rotation mechanism.

Several are cheap:
- frozen control: about 3 CPU-h;
- sanity checks: about 10;
- claims rewrite: text only, about 1 day;
- re-analysis of existing records for the statistics, ROC, per-user SER and persistence items: 0 CPU.

The most expensive are the exact-forward attack (about 70 CPU-h scoped, about 340 in full), the A4 convergence work (about 45-200), A3\* (about 120), mobility (about 40-130) and a full NR PUSCH chain (weeks of coding plus a GPU).

**Compute.** The high-impact set needs roughly 600-700 CPU-h at the recommended scopes. Time per run, from the records:

| Run | CPU time |
|---|---|
| Citadel-Rx A1, 100 blocks | about 10 min |
| Soft-gate attack | about 18 min |
| Combined attack | about 100 min |
| A4, 6 steps | about 36 min |
| A4, 20 steps | about 105 min |
| Meta-DeepSIC | about 30 min |
| A3\*, 400 blocks | about 80 min |
| 1000-block run | about 230 min |

Doing everything in full would cost over 2,000 CPU-h.

**Ceiling.** Over-the-air validation cannot be done now. A simulation-only TWC paper can still be accepted, but a 10/10 is unlikely without the realistic channel, the ML baselines and a converged attack that models the defense exactly.

1. **Main channel is real-valued, deterministic and the same for every seed, and pre-training sees it, so the 'held-out seeds' do not test channel generalization** (high, experiment; raised by R1, R3)

   Fix: Verified: channels/base.py _synthetic('cosine') uses no RNG and returns a float64 real matrix, so seeds 0-2 and 10-19 differ only in noise, symbols and window start. runner.pretraining_blocks forces fading='static', which gives H_mean, exactly the block-0 channel (cos 0 = 1). COST2100 is reduced to real gains with the diagonal pinned to 1 and off-diagonals x0.25. Sec. II-A still writes H_b in C^{NxU}. Fix: (1) Text: state in Sec. II-A, Table III and the abstract that (2) is real, deterministic and identical across seeds. (2) Add a complex stochastic channel with one draw per seed: complex Gauss-Markov H_{b+1} = rho H_b + sqrt(1-rho^2) W_b around the SED mean, uniform random initial phase per user, f_D T_b in {0.01, 0.05}. Pre-train on an ensemble that excludes the test draw. Add COST2100 with a seed-dependent start frame. (3) Re-run on seeds 10-19 with frozen settings: the headline cell (all five receivers, clean and A1 at 0 dB), A4 alpha=0.25, A3* 20%, and the Table IX rows K=1, no fallback and G2 only. Report the same columns and paired tests as Table IV. This is linked to the phase item: if the backbone fails on complex channels, report that.

   Cost: Coding about 1 day: complex fading mode, seed-dependent draws, ensemble pre-training, COST2100 offset. Headline cell is about 110 CPU-min per seed (Citadel ~15+8, Meta-DeepSIC ~33+30, others ~3-6 each), so 10 seeds x 2 Dopplers is about 37 h. COST2100 headline about 18 h. A4 (~44 min) and A3* 20% (~115 min) on 10 seeds about 27 h. Three ablations x 10 seeds x ~18 min about 9 h. Total about 90 CPU-h.

2. **Adaptive attacks do not model the defense and never search the acceptance boundary: surrogate predicts acceptance, real gates accept nothing, and every perturbation is at full budget** (high, experiment; raised by R2, R3, R1)

   Fix: Verified from results/rev_p3_adaptive_g1fix. 'Combined' at 0 dB: objective median -0.058 and above -0.5 on 200/200 blocks, which implies a surrogate acceptance of about 0.9. Yet 0/200 blocks were accepted (gamma median 5e-5), and the fast-level CRC pass is 0.018 against 0.82 for the reference. Soft-gate rows: 0/200 accepted at 0 and 10 dB. ||E||/eps >= 0.999 on 100% of unroll, PGD and combined blocks, and on 96-97% of soft-gate blocks. The attacker unrolls 2-50 plain SGD steps; the victim runs 300 Adam steps x 3 stages with the delta rule, the proximal pull and the surprise step. _soft_ctx and _soft_gamma leave out G3, the tightening and the CRC selection. The exact-copy oracle (attack.oracle_scales, commit aef1471, scripts/oracle_runs.py, tests/test_oracle_attack.py) is committed, but results/rev_p3_oracle does not exist and the paper reports nothing from it. Fix: (a) Run oracle_runs.py (max_ser and accepted modes, A4 accepted) on seeds 10-19. Extend it to a per-block bisection on the scale (8 steps) over several candidate directions (PGD restarts), accepting a candidate only if the exact copy accepts it. (b) Add G3, the tightening r_b(E) and a soft-min CRC selection to the soft objective. Use a C&W-style search over the trade-off constant with hinge margins per gate, and add a stealthy variant constrained to keep the pilot residual and the innovation within their clean range. (c) Optional, strongest: an exact-forward attack with implicit differentiation or a checkpointed Adam trajectory. Report the predicted and the realized acceptance per Table V row, and the best-iterate selection by the exact receiver's emitted SER, at SIR 0, 10 and 20 dB. (d) Report the worst case over all variants as the security figure.

   Cost: Coding: the oracle already exists. Bisection plus multi-direction plus the full soft objective take about 1-2 days. Implicit-diff exact-forward PGD takes about 3-5 days. Compute: an oracle run is about 40-50 min (soft-gate ~18 min, plus 8 exact trials x 40 blocks x ~4 s); the A4-based one is about 130 min. Seeds 10-19 for the three experiments: about 37 h. SIR 10 and 20 dB for the two soft-gate variants: about 30 h. Recommended scope is about 70 CPU-h. Full exact-forward PGD (200 iters x ~4 s x 40 blocks, about 9 h per run) x 10 seeds x 3 SIRs adds about 270 CPU-h.

3. **No ML / K-best / MMSE-SIC baselines: ML with the same LS estimate beats every deep receiver on clean blocks, and the gates rest on a weak linear reference** (high, experiment; raised by R1)

   Fix: Verified: I re-ran the reviewer's Monte Carlo (scratchpad rev_ml/ml_check.py; same SED, noise convention, Np=100 and regularized LS). Results: ML with LS CSI 0.0061, ML with true CSI 0.0049, LMMSE with LS CSI 0.0512 (paper: 0.0562). Citadel-Rx clean is 0.0159 and online DeepSIC 0.0330 (Table IV). Sec. V lists only LMMSE and Huber-LMMSE. Table X gives no model-based numbers at 4x16 or 8x32, although LMMSE records exist (rev2_arrays_stretch d4s_lmmse_8x32s, p6s_lmmse_4x16s). Fix: (a) Add ML (256 hypotheses), K-best (K=16) and MMSE-SIC/PIC rows, each with LS CSI and with perfect CSI, to Tables IV and VIII: clean SER, window SER, A1 excess at 0 dB, MACs, seeds 10-19. (b) Re-run Citadel-Rx with ML or K-best as the reference in (23) and as a candidate in (26), reporting FRR, RR and clean SER. (c) Show a regime where the deep receiver beats ML with LS CSI, either tanh(0.5x) (channel.linear=false already exists) or Np=16-32, and make it a main evaluation. Otherwise reframe the contribution as protecting a learning receiver, not as a better detector. (d) Tabulate the existing LMMSE records for 4x16 and 8x32, and add ZF and K-best there.

   Cost: Coding about 1 day: ML, K-best and MMSE-SIC detectors, plus hooks for the ML reference and candidate. Model-based rows: 6 x 10 seeds x (clean + A1) x ~3 min, about 6 h. Citadel with an ML reference: 10 x ~23 min, about 4 h. Justified regime (tanh or Np=32): five receivers + ML x 10 seeds x ~110 min, about 18-20 h per regime. Larger arrays: existing LMMSE records cost 0 CPU; ZF/K-best is 2 sizes x 5 seeds x 2 x ~15 min, about 5 h. Total about 35-55 CPU-h.

4. **No robust model-based defenses: tracked-CSI ML/LMMSE with a pilot-residual test, semi-blind estimation, spoofing detector plus freeze, decision-directed Meta-DeepSIC** (high, experiment; raised by R1)

   Fix: Verified: Table VIII compares mostly deep TTA variants. The only pilot-domain gate is G3 (innovation), which alone rejects just 16% of A1 blocks (ab.g3). No noise-consistency or pilot-residual test and no CSI-tracking fallback exists. At SIR 0 dB a perturbation outside span(S_b) inflates sigma_hat^2 by more than 10x, so such a test is very likely to fire. Fix: add rows for (i) LMMSE and ML with a Kalman/AR(1)-tracked channel and an innovation plus pilot-residual test that falls back to the previous estimate; (ii) semi-blind or data-aided CE from CRC-verified data (Nd/Np is about 250); (iii) the detectors of [9],[10] plus freezing adaptation; (iv) the decision-directed Meta-DeepSIC of [4] without new pilots. Run them under A1, A4 alpha=0.25 and rank-1 physical on seeds 10-14 (10-19 for the headline), reporting clean SER, window SER, excess, rejection, FRR and MACs. Then state what Citadel-Rx adds over the best of them, compared on window SER, not only excess.

   Cost: Coding about 2-3 days for the four baselines and their attack surfaces (A4 through a surrogate). Model-based rows: 3 x 5 seeds x 3 attacks x 2 x ~3 min, about 2 h. A4 against the four: 4 x 5 x ~36 min, about 12 h. Decision-directed Meta-DeepSIC: 5 x 3 x ~63 min, about 16 h. Total about 30 CPU-h.

5. **The frozen pre-trained DeepSIC control ('never adapt') is missing, so the value of test-time learning on the clean/attacked frontier is unmeasured** (high, experiment; raised by R1, R2, R3)

   Fix: Verified: Sec. VI-F says the frozen network 'was not run, so the clean gain of adaptation over it is not measured'. theta_pre is trained on H_mean (block 0 of the cosine channel), so on SED a frozen network starts on the test channel. Under attack Citadel-Rx runs on the anchor in 99% of blocks. Fix: add rows for frozen theta_pre DeepSIC and for frozen theta_pre with per-sub-block CRC selection against LMMSE (and against ML, per the ML item), on seeds 10-19. Report clean SER, window SER and excess for clean and A1 at -10, 0 and +10 dB, with paired Wilcoxon/Holm against Citadel-Rx. Repeat on the stochastic complex channel, where a frozen network should lose. If frozen-plus-selection matches Citadel-Rx on SED, say so and move the claim to the stochastic channel.

   Cost: Coding about 1-2 h: online DeepSIC with zero training epochs, plus a selection variant. Compute: 2 variants x 10 seeds x 4 conditions x ~2-3 min, about 3 h, plus about 3 h on the stochastic channel.

6. **Abstract, contributions and conclusion claim more than the tables show (adapted attacks 'unchanged', feedback, generality, 0.1% FRR, 'Three-Rate', derived CRC rule)** (high, text; raised by R2, R3)

   Fix: Verified. The abstract says 'Attacks adapted to the gates or their feedback leave the excess unchanged within its intervals'. That rests on 5-seed overlapping marginal intervals, attacks rejected on at least 95% of blocks at full budget, and an unconverged one-query-per-block NES. The 0.1% FRR holds only on stationary SED: it is 0.180 after a redraw, 0.021-0.025 at Nd=1000, 0.217 on the joint-symbol backbone and 0.979 at 16-QAM. K=2 gives +0.0242 [0.0181, 0.0306] against +0.0199, so the intervals overlap. The evaluated slack is the first-version rho=1 with floor 2e-3 ('not derived'); the derived slack lost calibration (0.0141 against 0.0133). The worst cases found are A4 PGD20 +0.0478, the pre-fix A4 +0.0531 (docs/G1_SOFT_FIX.md) and the spoof during a redraw +0.0968. 'The ordering holds with a second backbone and 8x32' rests on plain A1 only. The extended version (lines 256-257) calls the both-pass soft gates 'BPDA' in a self-contradictory sentence; the main paper does not. Fix: rewrite to 'the attacks tested, all at full budget and rejected on >= 95% of blocks, gave the same excess as plain A1', and separate attacker knowledge from optimization strength in Sec. II-B. Headline the worst case of the suite next to plain A1. Qualify the 0.1% FRR by channel and block length, and add the redraw FRR (0.180) and the post-redraw SER cost (0.250 against 0.224). Drop the feedback claim unless the query item is run. Limit generality to plain A1. Retitle to 'Multi-Rate', or keep 'Three-Rate' only after a paired K=2 vs K=3 on seeds 10-19 under A1, A4 and A3*. Move the CRC design rule out of the contributions, or evaluate the derived slack on seeds 10-19 and at Nd=1000/5000. Fix the BPDA sentence in the extended version.

   Cost: Text about 1 day. Optional runs: K=2 on seeds 15-19 under A1 (~1 h), A4 on 10 seeds (~7 h), A3* 20% on 5 seeds (~10 h), about 18 CPU-h. Derived slack on seeds 10-19 and Nd=1000/5000 is about 6 CPU-h.

7. **Five seeds and overlapping marginal intervals cannot support 'unchanged' or 'raises'; no paired contrasts, equivalence tests, endpoint hierarchy, interval validation or rate intervals** (high, experiment; raised by R3, R2)

   Fix: Verified: Tables V, VI, VIII, IX and X use 5 seeds. The smallest Wilcoxon p is 0.0625, as stated. Holm covers only the 4 headline baselines. Wilson intervals at the headline treat blocks as independent ('too narrow', as the paper notes), and every other Rej./False rej. entry is a bare rate. Spoof rejection ranges 0.04-0.32 per seed. Two machines give A1 +0.0196 and +0.0199, so paired noise is tiny. scripts/extend_seeds.py exists, but no *_more results are present. Fix: (1) extend Tables V, VI, IX and X to seeds 10-19 with extend_seeds.py; (2) for each row, compute the per-seed paired difference of window SER against the A1 row on the same seeds and twins, with t(df=9) and BCa intervals and a Holm-adjusted exact Wilcoxon p per table; (3) give TOST at a pre-registered +/-0.005 for every 'unchanged' claim, a one-sided paired test for every 'raises' claim, and the MDE at 80% power for nulls; (4) make seed-level intervals primary, keep the moving-block bootstrap as a sensitivity check, and verify coverage with A/A pairs (clean against clean, independent noise, or a zero-budget placebo) from existing twins; (5) give seed-cluster bootstrap or beta-binomial intervals with the per-seed min-max for every RR and FRR; (6) declare the primary endpoints (window and post-window excess at the headline, against 4 baselines) and one secondary family per table, and label the rest exploratory.

   Cost: Analysis code about 1-2 days, with near-zero CPU for re-analysis of existing records. Seed extension: Table V about 200 min per seed, VI about 215, IX about 110, X about 130, twins about 120, so 5 extra seeds is about 65 CPU-h.

8. **The reference-degradation attacker A4 cannot degrade the references (they are constants in its objective) and it has not converged** (high, experiment; raised by R2, R3)

   Fix: Verified: in attacks/pilot_poisoning.py, _soft_ctx computes pass_ref (LMMSE and anchor) and r_ref from the unperturbed data, using an H from the clean-pilot LS estimate. _soft_gamma treats them as constants, so the gradient has no term that lowers F_ref or raises R_ref. The objective also ignores the CRC selection (26), that is, what is emitted when the block is rejected. 6 to 20 PGD steps raised the excess from +0.0337 to +0.0478. Gaussian noise with A4's data budget gives +0.785 (a4.jam025), so the optimized perturbation is far weaker than noise of the same energy. The pre-fix half-scale G1 variant (+0.0531, 110/200 rejected) is a valid attacker that is no longer reported. Fix: make the references differentiable: the soft CRC pass of the anchor on y_d+E_d and of LMMSE(H_b(E), sigma_b^2(E)) on y_d+E_d, and G1's R_ref with posterior-mean symbols and the poisoned H_b(E). Use as objective the soft error of the CRC-selected output (soft-min over the three candidates) plus soft acceptance, with a C&W constant search, and accept only via the exact copy (oracle item). Plot excess against PGD steps (20/50/100) until it plateaus. Sweep alpha in {0.1, 0.25, 0.5}, plus 0.05/0.75/0.9 if budget allows, on seeds 10-19. Report F_mm and F_a under attack, an equal-energy comparison with A1 and data jamming, and the pre-fix variant as part of the worst case.

   Cost: Coding about 2 days. A4 PGD20 is about 105 min per run (rev2_a4_pgd20_g1fix), PGD50 about 260 and PGD100 about 520. Convergence curve on 5 seeds: about 74 h. Alpha in {0.1, 0.25, 0.5} at PGD 50 on 10 seeds: about 130 h. Full is about 200 CPU-h. Minimal (alpha=0.25, PGD 50, 10 seeds, plus reporting the existing pre-fix records) is about 45 CPU-h.

9. **Standard adaptive-attack sanity checks are missing: no random pilot-noise control, convergence curves, success against weakened defenses or gradient-masking checks** (high, experiment; raised by R2, R3)

   Fix: Verified: the only noise control is data jamming (Sec. VI-A). There is no Gaussian pilot perturbation at equal budget, although [7],[8] are cited. Unroll 10 and unroll 50 give the same numbers (+0.0193, +0.0192). EOT adds noise draws that the white-box attacker already knows, and the receiver is deterministic. Fix: (i) add a random-pilot-perturbation row (Gaussian E scaled to eps) at SIR 0 and 10 dB on seeds 10-19 to Table V; if it gives about +0.019 with 100% rejection, say that the gates act as an energy detector at these budgets; (ii) give objective and true-excess curves against PGD iteration and restart; (iii) run the same adaptive attack against 'no gates' and 'G3 only' to show it succeeds where it should; (iv) log gradient norms through unroll 2/10/50 and the fraction of saturated soft steps (omega=0.1); (v) keep EOT only for transfer or causal attackers and say why.

   Cost: Coding about 0.5 day (random-pilot attack type, logging). Random control: 2 SIRs x 10 seeds x ~10 min, about 3.5 h. Weakened-defense runs: 2 x 5 x ~18 min, about 3 h. Logging runs: 2 seeds x 3 depths x ~20 min, about 2 h. Total about 10 CPU-h.

10. **No sweep across the detection boundary and no ROC: A1 only at -10, 0 and +10 dB, where nearly every block is rejected** (high, experiment; raised by R1, R2, R3)

   Fix: Verified: Fig. 3(d) spans -10 to +10 dB. Rejection falls from 0.96 (A1, +10 dB) to 0.225 (A3* 20%, about +14 dB) and 0.002 (A3* 5%, about +26 dB). The paper says 'the weakest rejected perturbation was not searched for'. The UMi geometry gives a median SIR of -26 dB at 35 m and +2 dB at 150 m. Records store gate_g1/g2/g3 and gamma per block, plus ser_user. Fix: run A1 and the soft-gate attack (and the oracle attack of the adaptive item) at SIR 0, 5, 10, 12, 14, 16, 18, 20, 25 and 30 dB for Citadel-Rx and online DeepSIC on seeds 10-19. Report RR, FRR, window and post-window excess and D_K against SIR. Mark the SIR that maximizes the post-window excess and D_K, the smallest SIR rejected on 95% of blocks, and where the gates stop detecting while online DeepSIC's excess is still above 0.01. Use that SIR as the denial budget. Give per-gate and gamma ROC curves with AUC and cluster-bootstrap intervals at 0, 10 and 20 dB by re-thresholding the stored statistics (approximate, since the trajectory depends on tau; say so).

   Cost: A1 at 8 new SIRs x 10 seeds x (Citadel ~10 + online ~3 min): about 17 h. Soft-gate at 8 SIRs x 5 seeds x ~18 min: about 12 h. Clean twins exist. ROC from stored records: analysis about 0.5 day, 0 CPU. Total about 30 CPU-h.

11. **Gate state can be written by the attacker: ratchet, cold-start and consistent-spoof attacks are untested and outside Theorem 1** (high, experiment; raised by R2)

   Fix: Verified in code. receivers/lmmse.py ChannelTracker.fuse sets H_prev = H_fused on every block (called with accept=False), so G3 predicts from the poisoned estimate, and a consistent spoof has near-zero innovation after its first block. citadel._surprise_ratio updates S_ema on every block, rejected ones included. gates/physics.update_clean accepts the first 3 blocks unconditionally (disclosed in Sec. III-C). Each accepted block can move g1bar by up to x1.025 (tau1=1.25). Attack windows start in 10-50 and FRR counts b>=5, so the warm-up was never attacked. The denial spoof (fixed S_b Z^T) is already a consistent spoof and is rejected only 16% of the time. Fix: (1) Ratchet: R in {50, 100, 200} blocks bisected with the exact copy, so each block is accepted with g1 just under tau1 and g2 just above tau2, followed by 40 blocks of A1 or soft-gate at 0 dB. Report the trajectories of g1bar, g2bar, I-bar and S-bar, the phase-2 acceptance, excess and D_K, on 10 seeds. (2) Cold start: windows 0-39 and 0-99. (3) A slowly drifting consistent spoof against G3. (4) If any succeeds, harden: advance H_prev only on accepted blocks, gate the S-bar update, clamp the normalizers to [0.8, 1.25] of their calibration values, and seed the statistics from calibration. Re-run the headline cell and add a gate-state drift bound to Sec. IV.

   Cost: Coding about 1-1.5 days: ratchet on the exact copy, cold-start window option, drifting spoof, hardening flags. Ratchet runs are about 0.7-2 h each (phase-1 blocks x ~8 exact evals x ~4 s), so 3 R values x 10 seeds is about 45 h. Cold start: 2 windows x 2 attacks x 10 seeds x ~15 min, about 10 h. Drifting spoof about 2 h. Headline re-run after hardening about 4 h. Total about 60 CPU-h.

12. **The retention attacker A3* does not attack retention, and the retention study uses two seeds** (high, experiment; raised by R2, R3)

   Fix: Verified: with soft gates, _attack_obj takes the ctx branch (_soft_objective), so theta_bad, built in craft(), is never used. The paper says no attacker maximizing D_K subject to acceptance was run. Table VII and the 2000-block clean horizon use 2 seeds, and the caption concedes the interval reflects mostly between-block variation. extend_seeds.py exists ('A3* and the 900-block run from 2 to 5 seeds') but has not been run. Fix: (a) extend all six A3* rows and the 900-block row to 5 or more seeds with extend_seeds.py, and the 2000-block clean run to 5 seeds; (b) a directed-drift attacker maximizing <theta~(E)-theta^(K), d> subject to exact acceptance (oracle copy), at 5, 10 and 20% budget over 300 and 900 blocks. d points toward a high-SER state on the predictable cosine phases, or toward one user. Time the accepted pushes to the consolidation instants of (18). Report D_K against (30)/(31) and the anchor's held-out clean SER during and after; (c) sleeper-then-trigger: (b) for 300 blocks, then 40 blocks of A1 at 0 dB forcing fallback to the eroded anchor, compared with +0.0188.

   Cost: Coding about 1 day (directed objective with exact acceptance, consolidation timing). Seed extension: 3 seeds x 6 rows x ~80 min plus 3 x ~230 min, about 36 h, plus about 15 h of twins. Directed drift: 3 budgets x 5 seeds x ~100 min, about 25 h. 900-block directed: 5 x ~250 min, about 21 h. Sleeper: 5 x ~100 min, about 8 h. Long clean horizon: 3 x ~360 min, about 18 h. Total about 120 CPU-h.

13. **The cause of the 3GPP-scene failure (phase rotation) is asserted, not tested; the backbone may not track complex time-varying channels** (high, experiment; raised by R1, R3)

   Fix: Verified: Sec. VI-H says the phase rotation is 'the likely cause of this gap, not an established one'. Clean BLER is 0.169 for online DeepSIC against 0.0686 for LMMSE, and the virtual pass is 0.03 against 0.60. Every positive result is on real channels without phase. Fix: (1) on SED, multiply each user's column by e^{j phi_{u,b}} with a random walk of step sigma_phi in {0, 1, 5, 20} degrees per block; (2) UMi drops with phases frozen (block-0 phase applied to |H_b|) against rotating; (3) a backbone variant fed H_hat_b or LMMSE-equalized symbols, retuned on seeds 0-2. For each, report clean SER/BLER, FRR, the network's pass fraction against LMMSE, and the A1 excess on seeds 10-14 (or 10-19). State the mechanism or drop the claim.

   Cost: Coding about 0.5 day (phase walk, frozen-phase UMi), plus about 2 days for the H_hat-input backbone and retuning. SED: 4 sigma_phi x 5 seeds x (Citadel ~23 + online ~6 + LMMSE ~6 min), about 12 h. UMi frozen vs rotating: 5 seeds x 4 receivers x ~35 min, about 12 h. Backbone tuning (~3 h) and test (~8 h). Total about 35 CPU-h.

14. **Theorem 1 bounds weight displacement only: no link to SER, no a-priori statement, D_K mixes benign lag with poisoning** (medium, analysis; raised by R1, R2, R3)

   Fix: Verified: (30) follows from the clip, which binds in 5/150 clean and 12/150 attacked consolidations, and removing it leaves the excess unchanged. The design bound of 90 is 3.4x the clean movement of 26.8. (31) needs the paired clean run, which the paper itself calls a diagnostic. Under A1 the attacked level moved 4.8 against 8.4 at cosine 0.94, so most of D_K=4.17 is lag. The drift guard lowers D_K but not the excess. Sec. VII already says the bounds limit displacement, not error rate, and the abstract phrases the clip in weight terms, so that text part is addressed. Fix: (1) add the a-priori corollary: if every poisoned block is rejected and streak recovery is off, every level stays in the hull of the pre-window states (plus theta_pre with the guard), so D_K <= hull diameter + clean movement; each accepted block adds at most an a-priori fast-map displacement (from T, eta_max and the Adam step bound); (2) decompose D_K in Table VII into lag along the clean movement and an orthogonal component, using the stored .levels.json snapshots; (3) map D_K to SER: freeze the attacked and clean slow levels at the end of the window, run the anchor on 20 fresh clean blocks per seed, and plot the SER gap against D_K with rank correlation; add the worst-case anchor SER under weight-space PGD and under random directions at radii kappa_3, 2kappa_3, 18 and 90; (4) mark which Table VII rows satisfy the conditions of (i) and (ii).

   Cost: Theory and writing about 1-2 days. Inference-only analysis on the existing snapshots about 3-5 CPU-h.

15. **Complexity and latency are not reported in a form that shows feasibility (9 GMAC and 900 sequential Adam steps per 1 ms block)** (medium, experiment; raised by R1)

   Fix: Verified: docs/flops.json gives Citadel-Rx 9.0 GMAC per block (5.8 of it training) at 4x4, 19.4 at 4x16 and about 72 at 8x32. The main text gives only 3.03 s on one CPU core and 4.1x the MACs of online DeepSIC. The 30-step (1.93 s) and last-layer (2.65 s) variants appear only in the extended version. T=300 x Q=3 gives 900 dependent steps per block. Sec. VII says 'far from real time'. Fix: add a complexity table for LMMSE, ML/K-best, online DeepSIC, Meta-DeepSIC, CRC-Rollback and the Citadel-Rx variants. Give MACs per block and per bit, sequential depth, memory (slow buffer up to 32 snapshots), and GPU latency (batched users, CUDA graphs). Evaluate T in {10, 30, 100, 300}, and a pipelined variant that detects block b with weights trained up to b-1. Report clean SER, FRR and A1 excess on seeds 10-14, a Pareto plot of excess against MACs and latency, and the comparison with TS 38.214 N2.

   Cost: Analysis and text about 1 day. T sweep: 3 values x 5 seeds x 2 x ~8 min, about 4 CPU-h. Pipelined variant: about 0.5 day of coding plus about 2 CPU-h. GPU latency needs a GPU: about 0.5 day and a few GPU-h.

16. **Mobility, non-stationarity, persistent attacks and multi-user scheduling are not evaluated** (medium, experiment; raised by R1, R2)

   Fix: Verified: mobility is limited to the SED cosine fades and UMi at 3 km/h, and the current receiver is not run on Jakes. The denial experiments are short (one redraw, 5 seeds, point estimates). Correction to R1: after the redraw LMMSE has SER 0.351, worse than Citadel-Rx (0.250) and online DeepSIC (0.224). The redrawn channel is harder; it does not show that the deep receivers 'fail to re-adapt', so that sub-claim is dropped. Fix: a complex Jakes sweep with f_D T_b in {0.001, 0.005, 0.02, 0.05, 0.1}, and UMi at 3/30/60/120 km/h, for Citadel-Rx, online DeepSIC, LMMSE (ML) and frozen DeepSIC, giving clean SER, FRR and excess. Add persistent A1 or soft-gate attacks at 0 and 10 dB with windows of 100, 300 and 1000 blocks on Jakes and after a redraw, with streak recovery on and off, reporting excess against window length, recovery time and post-attack FRR. Add a scheduling experiment that replaces one user every 10 or 50 blocks (new column, network re-initialized from theta_pre, per-user slow levels) and reports recovery and excess.

   Cost: Coding about 1-2 days (complex Jakes, user replacement with per-user re-init). Jakes: 5 x 10 seeds x ~39 min per seed set, about 33 h. UMi: 3 new speeds x 5 seeds x 4 receivers x ~35 min, about 35 h, plus new drops. Persistent windows (1000-block Citadel about 200-230 min): 5 seeds x 2 SIRs, about 55 h. Scheduling about 10 h. Full is about 130 CPU-h; minimal (2 Dopplers, 300-block window, 5 seeds) is about 40 CPU-h.

17. **The coded 3GPP link is not an NR link: one narrowband channel across about 27 MHz, hard-decision LDPC with |LLR|=3, untuned receivers, one speed and one SNR** (medium, experiment; raised by R1)

   Fix: Verified: make_umi_channels.py keeps only the frequency response at the carrier ('frequency selectivity within a block is not modelled'). coding/ldpc.py feeds (2b-1)*3 into BP. channels/sionna_pusch.py raises NotImplementedError. All of this is disclosed in Table III and Sec. VII, so the disclosure is addressed and the fix remains. Fix: in stages. (1) Quick: feed max-log LLRs from psi^(Q) and from LMMSE (post-equalization SINR) into the existing decoder, re-run the UMi set, and add a BLER-vs-SNR curve. (2) Full: a Sionna PUSCH chain (OFDMChannel with UMi/CDL, 30 kHz SCS, DMRS type 1 plus one additional position, LS plus interpolation, per-PRB processing, LDPC5GDecoder, TB CRC and segmentation per TS 38.212, MCS 5/10/15), with every receiver retuned on calibration drops 0-2. Report BLER and goodput for SNR from -5 to 20 dB at 3, 30 and 60 km/h, clean and under A1 and the physical attacker at SIR from -20 to +10 dB.

   Cost: Quick: about 0.5 day of coding, then 4 receivers x 3 distances x 5 seeds x ~35 min, about 35 CPU-h, plus an SNR curve of about 20 h. Full: about 1-2 weeks of coding with a GPU, and several hundred GPU/CPU-h for BLER/goodput x SNR x speed x MCS x attacks.

18. **The frame structure is unrealistic (Np=100, Nd=24,992, 781 CRC-8 sub-blocks per user), and G2's statistical power and CRC selection depend on it** (medium, experiment; raised by R1)

   Fix: Verified: Table III gives J=781 sub-blocks of L=32 per user (12.5% CRC overhead) and random non-orthogonal QPSK pilots (frames.py draws them per block). Table X already shows FRR of 0.021-0.025 above the 2% cap at Nd=1000. CRC selection gives 70% of the clean gain. Fix: re-run the headline cell with NR-like slots: 4-16 PRBs per user, 12 data plus 2 DMRS symbols (Np=24-96, Nd=576-2304), orthogonal DMRS ports, and 1-3 LDPC code blocks per user per slot with TS 38.212 CRCs only. Aggregate gate statistics over slots if needed, and report FRR, RR, excess, the CRC-selection gain and the decision delay. Evaluate the derived slack of (28) here.

   Cost: Coding about 1-2 days: orthogonal DMRS, slot-level segmentation, multi-slot aggregation. Compute: 3 configurations x 10 seeds x 4 receivers x 2 x ~5 min (short blocks; rev_p6_blocklen runs are 3-8 min), about 20 CPU-h.

19. **Gate ablations run only under plain A1, where G2 alone suffices, and the main lesson (judge against the memory) is never isolated** (medium, experiment; raised by R3)

   Fix: Verified: Table IX is A1 only. G2 only gives +0.0194 against +0.0199 for the full receiver, so G1 and G3 have no measured role. The reversion, the delta rule and the surprise step are 'not ablated'. Lesson 1 is inferred by comparing different receivers (CRC-Rollback, K=1). Fix: add an ablation with LMMSE as the only reference (R_ref = R_b(s_mm), F_ref = F_mm), keeping the slow levels, fallback and selection, under A1 and A4 on seeds 10-19. Re-run G1-only, G2-only, G3-only, no fallback, K=2 and no clip under A4 alpha=0.25 (10 seeds), A3* 20% (5 seeds) and the redraw. Add delta=0, r_b=1 and no-reversion rows under A1. Report paired contrasts against the complete receiver.

   Cost: Coding about 0.5 day (LMMSE-only reference flag). LMMSE-only reference: 10 x (~18 + ~44 min), about 10 h. Six ablations under A4: 6 x 10 x ~36 min, about 36 h. Under A3*: 6 x 5 x ~80 min, about 40 h. Redraw about 3 h. Mechanism ablations about 5 h. Full is about 95 CPU-h; minimal (LMMSE-only reference plus G-only rows under A4 on 5 seeds) is about 25 CPU-h.

20. **The persistence endpoint (harm after the attack), central to the thesis, is under-reported** (medium, analysis; raised by R3)

   Fix: Verified: the 'After' column of Table IV has no interval or test and covers 10-30 blocks per seed (window start drawn in 10-50 of 100). Tables V, VI, IX and X give no post-window excess. recovery_blocks is in every record summary but not reported. Online DeepSIC's post-window excess is only +0.0189 against +0.768 in the window, which weakens 'the harm lies less in the attacked block'. Fix: from the existing records, report post-window excess with intervals and paired tests for every row, censored recovery time (Kaplan-Meier median), and Citadel-Rx's post-window rejection rate. Extend the headline runs to 200 blocks (at least 60 post-window blocks), with D_K(t) up to block 200. Either support the thesis with W=1 single-block attacks (excess in b+1..b+30 per receiver) or soften it in Sec. I.

   Cost: Analysis about 0.5 day, 0 CPU. 200-block headline: 5 receivers x 10 seeds x 2 (Meta-DeepSIC dominates), about 35 h. W=1 runs: 5 x 10 x ~10 min, about 8 h. Total about 43 CPU-h.

21. **Tuning is asymmetric: Citadel-Rx is selected on attacked SER, baselines on clean SER only, L2-SP is swept on test seeds, EATA never fires; the sensitivity study uses one test seed** (medium, experiment; raised by R3)

   Fix: Verified: Sec. V says the baselines' own settings are not tuned and L2-SP is swept on seeds 10-14, stopping at weight 1 while the excess is still falling (+0.136). EATA never fired (0.38 against 0.55 nats) and duplicates EWC to the last digit. The sensitivity study is seed 10, one setting at a time, A1 only, with FRR up to 0.053 on 95 blocks. All of this is disclosed; the remedy remains. Fix: re-tune each baseline with Citadel-Rx's rule on seeds 0-2 (same score, same 2% FRR cap): L2-SP {0.01, 0.1, 1, 3, 10, 100}; EWC lambda over 4 decades; EMA decay {0.9, 0.99, 0.999}; CoTTA p {0.001, 0.01, 0.1}; drift threshold {1, 2, 3}. Freeze them and test on 10-19, with a table of tuned settings. Re-set EATA's margin so the filter fires on calibration, or drop the row. Redo the sensitivity study on seeds 0-2 as a 40-point Latin hypercube over the eight settings in [0.5x, 2x] under A1 (and A4), with partial rank correlations or Sobol indices.

   Cost: Coding about 0.5 day. Baseline grids: about 25 settings x 3 seeds x 2 x ~5 min, about 13 h. Tuned baselines on 10-19: 8 x 10 x 2 x ~5 min, about 13 h. LHS: 40 x 3 x (~10 + ~8 min), about 36 h, plus about 72 h with A4. Total about 60-130 CPU-h.

22. **The 16-QAM failure is diagnosed (narrow MLP) but the remedy is not tested; as written the method is QPSK-only** (medium, experiment; raised by R1, R3)

   Fix: Verified: width is kept at 256. The network passes 0.11 of clean CRCs against 0.93 for LMMSE, FRR is 0.979, and the paper says 'a wider one was not tested'. Fix: 16-QAM with width 1024 and online settings retuned on seeds 0-2, at SNR 15, 20 and 25 dB on seeds 10-14: clean SER, FRR and A1 excess, with LMMSE/ML/K-best references, plus 64-QAM for the references. If the failure persists, restrict the title, abstract and conclusion to QPSK.

   Cost: Coding about 0.5 day. A width-1024 Citadel run is about 60-80 min (about 4x training MACs; the width-256 run is about 20 min). Tuning: 4 settings x 3 seeds x ~70 min, about 14 h. Test: 3 SNRs x 5 seeds x (~70 + ~40 twin + ~15 + ~5 min), about 33 h. 64-QAM references about 5 h. Total about 50 CPU-h.

23. **Calibration/test separation is partly compromised (seeds 10-14 reused across design iterations), and reproducibility details are missing** (medium, experiment; raised by R3)

   Fix: Verified: Table III lists the post-hoc abstain change (after seeds 10-12) and the stretched SED profile adopted after test runs. L2-SP is swept on test seeds. docs/REVISION_PLAN.md notes unreported abstain-v2 A4 runs on seeds 10-12. Only seeds 15-19 are fresh, and only for the headline. Two machines give +0.0196 and +0.0199, but no software versions or determinism flags are stated. Dropped as already consistent: 'kappa before calibration' (Table III) against 'at or just above the calibration increments' (Sec. III-B) is a check, not a contradiction; a one-clause clarification is enough. Fix: commit the frozen configuration and cite its hash. Re-run the primary cell of each table on fresh seeds 20-29 and report it next to the current numbers. Add a provenance table of every post-test-seed choice and the seeds that informed it. Add a reproducibility paragraph (PyTorch, NumPy and BLAS versions, threads, determinism flags, a commit per table) and an A/A run of the headline cell on 3 machines.

   Cost: Fresh seeds 20-29: headline about 20 h, A4 about 7 h, Combined about 18 h, A3* 5% about 20 h, 8x32 about 8 h, so about 75 CPU-h. A/A: 3 machines x 10 seeds x ~18 min, about 9 h. Text about 0.5 day.

24. **The CRC is a forgeable integrity check under the paper's own '+data' threat model** (medium, experiment; raised by R2)

   Fix: Verified: G2, the design rule (27)-(28), CRC selection, the virtual pass and streak recovery all treat a CRC pass as proof. CRC-8 is linear. Table II grants soft-gate, A4 and A3* knowledge of the data and its symbols, and A4 perturbs the data. Sec. II-B neither excludes nor tests CRC-valid error patterns, and the 2^-B term in (27) assumes random errors. Fix: either exclude it in Sec. II-B with an argument, or add a CRC-forgery A4. Enumerate the minimum-weight multiples of g(D) within 64 bits, push the targeted candidate's decisions to the nearest CRC-valid wrong word under the alpha budget, and report the undetected-error rate, G2 verdicts, F_ref and the excess at 0 and 10 dB on seeds 10-14. Discuss CRC-24A in the coded scene.

   Cost: Text option about 1 h. Experiment: about 1 day of coding, then 2 SIRs x 5 seeds x ~40 min plus twins, about 8 CPU-h.

25. **SNR convention, single operating point and missing per-user error rates** (low, experiment; raised by R1, R3)

   Fix: Verified: eq. (1) defines sigma^2 = 0.5*10^{-SNR/10} and Sec. II-C defines the SER as a vector error rate, so the definitions are addressed. The per-antenna Es/N0 is about 3 dB above nominal (about 13-14 dB with the SED column gain), and this is not flagged. Every QPSK result is at 10 dB. Per-user SER is stored in every record (blocks[].ser_user) but not reported. Fix: state the received Es/N0 per antenna (or Eb/N0). Report per-user SER and BER from the records. Add clean SER, FRR, RR and A1 excess against SNR (0/4/7/13/16/20 dB) for Citadel-Rx, online DeepSIC, LMMSE, ML and MMSE-SIC on seeds 10-19.

   Cost: Text about 1 h. Per-user analysis about 0 CPU. Sweep: 5 SNRs x 10 seeds x (Citadel ~18 + online ~6 + LMMSE ~6 + ML ~6 min), about 30 CPU-h.

26. **Excess-only comparisons reward a worse clean twin; absolute window SER, goodput and coded translation on SED are missing from most tables** (low, analysis; raised by R1, R3)

   Fix: Verified: Tables IV, V, VI, IX and X have no attacked window SER. 'No CRC selection' (+0.0053, clean 0.0317) and 'No anchor' (+0.0130) show the problem. The 70% share has no interval. eval/metrics.py degradation_db exists but is not reported. Table VII's A1 row (+0.0137) uses the fixed 30-69 window; the caption states the window, but the gap to +0.0188 is not explained. Dropped as already addressed: Fig. 3(d)'s seed mix is stated in its caption. Fix: add attacked window SER, clean SER and SNR-equivalent degradation in dB to every table, a bootstrap interval for the 70% share, and one sentence on the Table VII window. Optionally re-run the headline cell on SED with LDPC code blocks and soft LLRs, and report BLER and goodput.

   Cost: Analysis and text about 0.5 day, 0 CPU. Optional coded SED: 5 receivers x 10 seeds x 2 x ~12 min, about 20 CPU-h.

27. **Positioning against bilevel poisoning, filter-evading attacks and robust aggregation is missing, and so are robust-aggregation consolidation baselines** (low, text; raised by R2)

   Fix: Verified: the references omit Biggio 2012, Munoz-Gonzalez 2017, MetaPoison, Witches' Brew, Koh-Steinhardt-Liang 2022, Carlini-Wagner 2017 (detectors), norm-bounding and robust aggregation (Sun 2019, Blanchard 2017, Yin 2018) and Steinhardt 2017. Fix: add these, and relate the clip and gated mean (18) to norm-bounding and robust aggregation. Optionally add consolidation baselines that replace (18) with a coordinate-wise median, a 20% trimmed mean or Krum, without gates, under A1 and A3* on seeds 10-14.

   Cost: Text about 0.5 day. Optional: about 0.5 day of coding, then 3 variants x 5 seeds x (~18 + ~115 min), about 33 CPU-h.

28. **Query and gray-box attackers are too weak to support claims about feedback** (low, experiment; raised by R2)

   Fix: Verified: Table II: one NES query per block over 40 blocks, 'not converged'. The gray-box attacker transfers plain A1 without the soft-gate or exact objective. Fix: the text change is covered by the claims item (drop 'or their feedback'). If kept, run a decision-based boundary attack (HopSkipJump-style) on ACK/NACK with several queries per block via HARQ (e.g., 4) or 1000-block horizons, searching norm and direction, and report convergence. Give the gray-box surrogate the exact-copy attack.

   Cost: Text about 1 h. Experiment: about 2 days of coding, then 1000-block query runs at 5 seeds x ~230 min (about 19 h) plus gray-box exact at 5 x ~45 min (about 4 h), about 23 CPU-h.

29. **Hardware impairments and model mismatch are not evaluated for gates that assume a linear model, nor attacker CFO/timing** (low, experiment; raised by R1, R2)

   Fix: Verified: tanh FRR is checked only on first-version runs in the extended version. There is no CFO, phase noise, IQ imbalance or PA compression, and the physical attacker model (10) has no CFO or timing offset. Fix: report clean FRR and A1 excess at the headline cell under tanh(0.5x), residual phase drift of 0.5-5 degrees per 100 symbols, Wiener phase noise and IQ imbalance of 1 dB / 5 degrees. Add CFO and timing jitter to the attacker's signal.

   Cost: Coding about 0.5 day. 5 impairments x 5 seeds x (~8 + ~10 min), about 8 CPU-h.

30. **Independence assumptions of the CRC design rule are testable but unchecked** (low, analysis; raised by R3)

   Fix: Verified: Sec. III-E says the independence of errors within a sub-block 'was not checked against the records'. Records hold per-block pass fractions (pass_nn, pass_mm) and SER, but not per-sub-block outcomes. Fix: log per-sub-block CRC outcomes on two clean seeds. Plot the observed pass fraction against (1-p_hat)^L, estimate the dispersion index across sub-blocks and the effective number of independent checks, and report how much tau_2 would move.

   Cost: Coding about 0.5 day (logging and analysis). 2 clean runs x ~10 min, under 1 CPU-h.

31. **No over-the-air or measured-channel validation of the attacks and gates** (low, not_fixable_now; raised by R1, R2, R3)

   Fix: Verified: every result is simulated, and Sec. VII lists the link-level and idealized-attacker assumptions. Fix: an SDR testbed (multi-antenna base station, 4 UEs, a synchronized attacker node) or measured MIMO traces. Meanwhile, state the limitation explicitly and cover attacker CFO and timing in simulation (hardware item).

   Cost: Needs hardware or data that are not available now. Text about 1 h.
