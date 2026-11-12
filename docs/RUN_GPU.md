# Runs for the GPU workstation (PowerShell, Windows)

Status 2 Nov 2026: sections 1–4 are done and pushed (commit 2ddc21e); the commands stay here for reruns.

Every command below resumes: records that already exist are skipped, so a reboot
costs nothing but time. Run them in order; each block says what it closes in the
paper. All grids run on CPU workers (tiny per-user MLPs; parallel CUDA processes
crashed), so `--workers 8` on the 20-core box is the right setting.

## 0. Update the code and the environment

```powershell
cd C:\Users\athawerani\Documents\Abraheem_work\paper2\Citradel-Rx
.\.venv\Scripts\Activate.ps1
git pull origin claude/fervent-cray-ah5drn
python -c "import torch; print(torch.__version__)"
python -m pytest tests -q
```

## 1. Relative CRC slack on the low-SER cells (closes Sec. VI-F of the paper; ~2 h)

19 jobs x 3 seeds: COST2100 A1 at five budgets + clean, SNR 10–16 dB clean and
attacked, and the linear SIR grid as a no-regression check.

```powershell
python scripts\sweep.py e3rel --seeds 0 1 2 --workers 8
python scripts\compare_runs.py results\e3rel
```

Expected: COST2100 attack-window SER back near the clean level (≤ 0.001 at SIR 0),
rejection ≥ 0.85; linear SIR cells unchanged (0.025–0.032).

## 2. 8x8 QPSK (reviewer item "larger system"; ~6 h)

28 jobs x 3 seeds: all seven receivers, clean and A1 at SIR −10 / 0 / 10 dB.

```powershell
python scripts\sweep.py e8 --seeds 0 1 2 --workers 8
python scripts\compare_runs.py results\e8
```

## 3. Doppler sweep (gates vs. fading speed; ~3 h)

21 jobs x 3 seeds: Jakes f_D T_b = 0.01 / 0.05 / 0.1, A1 at SIR 0 dB.

```powershell
python scripts\sweep.py e9 --seeds 0 1 2 --workers 8
python scripts\compare_runs.py results\e9
```

## 4. Five seeds on the headline cells (~3 h)

Adds seeds 3 and 4 to the E3 linear grid for the three receivers that appear in the
abstract, and to the clean-parity cell at 10 dB.

```powershell
python scripts\sweep.py e3 --seeds 3 4 --workers 8 --receivers citadel online_deepsic meta_deepsic
python scripts\sweep.py e2 --seeds 3 4 --workers 8 --receivers citadel online_deepsic meta_deepsic --snrs 10
```

## 5. Regenerate every table and figure, then push

```powershell
python scripts\analyze.py
python scripts\paper_numbers.py
python scripts\analyze_e5.py
python scripts\gate_roc.py results\e3 results\e3nl results\e3cost results\e4 results\e7 --write
$env:CERT_REUSE=1; python scripts\certificate_check.py
git add results\e3rel\*.json results\e8\*.json results\e9\*.json results\e3\*.json results\e2\*.json docs\
git commit -m "GPU runs: e3rel, e8, e9, five-seed headline cells; regenerated tables and figures"
git push origin claude/fervent-cray-ah5drn
```

Only `*.json` records are added (the `*.npz` level snapshots are gitignored and must
never be force-added: that is what produced the 13 GB pushes).

## Checking progress (second terminal)

```powershell
cd C:\Users\athawerani\Documents\Abraheem_work\paper2\Citradel-Rx
foreach ($e in "e3rel","e8","e9","e3","e2") { "$e : $((Get-ChildItem results\$e -Filter *.json -ErrorAction SilentlyContinue).Count)" }
```

Targets: e3rel 57, e8 84, e9 63, e3 (+66 over the current count), e2 (+12).

## Optional (only if time allows)

* Uniform relative-slack rerun of every Citadel cell, so that the paper reports one
  gate configuration throughout (≈ 450 runs, ~15 h):
  `python scripts\sweep.py e3 --seeds 0 1 2 --workers 8 --receivers citadel --extra citadel.g2_slack_mode=relative run.out_dir=results\e3_rel`
  and the same for `e3nl`, `e3cost`, `e3snr`, `e2`, `e2nl`, `e2cost`, `e4`, `e7`, `ablate`.
* Link-level simulation with LDPC coding (E6) needs Sionna on the GPU:
  `pip install -e .[sionna]` then `python scripts\run_experiment.py configs\e6_sionna_pusch.yaml`.
  The channel adapter is untested here; expect to debug it.
