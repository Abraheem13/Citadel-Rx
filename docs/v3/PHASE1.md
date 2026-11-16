# Phase 1: Cheap checks that can change the story

Plan: `docs/ROADMAP_9of10.md`. Job list: `scripts/v3/phases.py::phase1`. Runner: `scripts/v3/campaign.py`.
Analysis: `scripts/v3/analyze.py --phase 1`.

All runs use test seeds 20–29 (five seeds for 1f), the SED benchmark channel, 4×4 QPSK, SNR 10 dB,
N_p = 100 and N_d = 25,000, and the Citadel-Rx and baseline settings frozen in the second campaign.
Every attacked run has a clean twin from the same machine.

## Experiments

| Group | Runs | Question |
|---|---|---|
| 1a | Citadel-Rx, online DeepSIC, frozen pre-trained DeepSIC, frozen + per-sub-block CRC selection against LMMSE, CRC-Rollback; white-box A1, SIR 0 dB, random window | Does a receiver that never adapts, with CRC selection, do as well as Citadel-Rx? (Under attack Citadel-Rx detects with its anchor on 99% of blocks.) |
| 1b | Citadel-Rx under A1 at SIR 0 dB on blocks 0–39 (cold) against 40–79 (warm); soft-gate attack on blocks 0–39 | The gates accept their first three blocks and seed their reference statistics (ḡ₁, ḡ₂, Ī) from them, and the slow levels are not yet formed. Is a cold start a hole? |
| 1c | Blocks 10–49: soft-gate perturbations scaled down until an exact copy of the receiver accepts them (SIR 10 dB). Blocks 50–89: plain A1 at SIR 0 dB. Control: blocks 50–89 alone. | Can accepted poisoning move the gates' running statistics so that a later burst passes? |
| 1d | LMMSE, ML, K-best (K = 16) and MMSE-SIC with a pilot-domain guard (noise inflation and channel innovation, fallback to the last accepted estimate, CRC selection), under A1; the guard against a channel-estimate spoof S_p Z^T | Is a simple model-based defense as good as Citadel-Rx? |
| 1e | The same four detectors without the guard (LS CSI) under A1, and with perfect CSI (clean) | The missing model-based baselines and the genie bounds |
| 1f | 16-QAM at 20 dB with the reference width (64 × 16 = 1024 hidden units; the second campaign used 256): Citadel-Rx, online DeepSIC, LMMSE, K-best | Was the 16-QAM failure caused by the narrow network? |
| 1R | **Regime scan for Phase 2. Calibration seeds 0–2, clean runs only, run first.** Six settings: R0 = the SED benchmark; R1 = seed-varying complex Rician Gauss–Markov channel (K = 1, f_D·T_b = 0.01) with ensemble pre-training on 32 draws that exclude every test channel; R2 = R1 + 3-bit ADCs; R3 = R1 + LNA saturation at 0.7 × rms; R4 = R1 + IQ imbalance (15%, 15°); R5 = R1 + 32 pilot symbols. Six receivers: online DeepSIC, Citadel-Rx, frozen DeepSIC, LMMSE, ML and K-best (LS CSI). | Where does an adapting deep receiver beat ML detection with the LS estimate? This chooses the paper's main setting. |

## Decision rules (fixed before any result was seen)

Every comparison is paired by seed. "Equivalent" means TOST at a margin of 0.005 SER: the 90%
moving-block interval of the paired difference lies inside (−0.005, +0.005). "Better" means the 95%
interval excludes zero.

| Result | Consequence |
|---|---|
| 1a: frozen + selection is equivalent to Citadel-Rx, or better, in window SER | On SED, adaptation is not what protects the receiver. The paper's claim moves to the Phase 2 regimes, where adaptation is needed, and the paper says so. |
| 1a: Citadel-Rx is better in window SER | Adaptation pays even on SED; reported. |
| 1b: cold excess − warm excess > 0.005, interval above zero | Cold start is a hole. A fix (gate references seeded from pre-training, not from the first blocks) is calibrated on seeds 0–2 and tested on fresh seeds 30–34 before Phase 2. |
| 1c: burst excess after the ratchet − burst excess alone > 0.005, interval above zero | The gate state can be ratcheted. A fix (references updated only by blocks whose verdict exceeds a margin, and the channel tracker and surprise statistic frozen on rejected blocks) is calibrated on 0–2 and tested on 30–34. |
| 1d: a guarded model-based receiver has a window SER equivalent to or below Citadel-Rx's | It becomes the main baseline. Phase 2 must show a regime where Citadel-Rx beats it; otherwise the contribution is reframed. |
| 1f: Citadel-Rx's clean SER ≤ LMMSE's and its clean false rejection ≤ 2% | The 16-QAM failure was the width; 16-QAM moves into Phase 2 at width 1024. |
| 1f: otherwise | 16-QAM stays a reported limitation, with the width tested. |
| 1R | Main regime of Phase 2: the one of R1–R5 with the largest r = SER(ML, LS CSI) / min(SER(online DeepSIC), SER(Citadel-Rx)), clean SER over blocks 50–99, geometric mean over seeds 0–2 (`analyze.py::regime_scan`). |
| 1R: max r < 1.25 | No regime favors the plain DeepSIC backbone. Phase 2 first introduces the channel-conditioned backbone (below) and repeats the scan with it, under the same rule. |

Disclosure: before this rule was written, a three-block smoke test on calibration seed 0 (R2 with
Citadel-Rx and ML; R1 with online DeepSIC) was run to time the ensemble pre-training. Its SER was
0.92 → 0.36 (Citadel-Rx, R2), 0.60 → 0.34 (online DeepSIC, R1) and 0.087 (ML, R2). No test seed was
involved. It showed that a pre-trained DeepSIC is far from the channel when that channel is new, as
it always is outside the SED benchmark.

## Commands (Windows PowerShell, in the repository folder)

Get the Phase 1 code:

```powershell
git pull origin main
```

Check the plan and the time estimate (runs nothing):

```powershell
.venv\Scripts\python.exe scripts\v3\campaign.py --phase 1 --dry
```

Run it. The number of parallel runs and the device come from your Phase 0 benchmark. The run is
resumable: if it stops, run the same command again.

```powershell
.venv\Scripts\python.exe scripts\v3\campaign.py --phase 1 --push-every 60
```

`--push-every 60` commits and pushes the results every hour. Leave it out if pushing from the
script does not work, and push by hand at the end:

```powershell
git add results/v3 logs/v3
```

```powershell
git commit -m "Phase 1 results (ws5080)"
```

```powershell
git pull --rebase origin main
```

```powershell
git push origin main
```

## Review (done in the review session)

```bash
python scripts/v3/analyze.py --phase 1
```

This writes `docs/v3/PHASE1_TABLES.md` and `results/v3/p1_summary.json`. The decisions are then
recorded in `docs/v3/PHASE1_REPORT.md`.
