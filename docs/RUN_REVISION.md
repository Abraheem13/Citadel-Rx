# Revision campaign on the GPU workstation (PowerShell)

One command runs everything the reviewer audit asks for, in priority order, and resumes after a
reboot (finished runs are skipped). Total: about 1,580 runs, roughly one day at 8 workers.

## 1. Update and test (5 minutes)

```powershell
cd C:\Users\athawerani\Documents\Abraheem_work\paper2\Citradel-Rx
.\.venv\Scripts\Activate.ps1
git stash
git pull origin claude/fervent-cray-ah5drn
python -m pytest tests -q
```

## 2. Run the campaign (terminal 1, about one day)

```powershell
python scripts\revision_campaign.py --workers 8
```

What it does, in order:

1. **Phase A, calibration (seeds 0-2, ~1 h).** Tunes online DeepSIC and Meta-DeepSIC
   (epochs x learning rate x weight decay) and runs the Citadel-Rx candidate configurations.
   It then writes `configs\revision_frozen.json` with a rule fixed in advance: lowest clean SER
   for the baselines; for Citadel-Rx, lowest mean SER over clean, A1 and COST2100 among the
   candidates with at most 2% clean false rejections. Nothing is chosen by hand.
2. **Phase B, test (fresh seeds 10-19).** P1 headline (10 seeds), P2 baselines, P3 attacks
   built against the defence, P4 paired displacement, P5 ablations, P6 block length / arrays /
   16-QAM / deployable variants, P7 sensitivity, P8 1000-block drift attack and 2000-block horizon.

## 3. Lipschitz constants (terminal 2, after Phase A has finished, ~5 h, runs alongside)

```powershell
cd C:\Users\athawerani\Documents\Abraheem_work\paper2\Citradel-Rx
.\.venv\Scripts\Activate.ps1
python scripts\lipschitz_strong.py --frozen --blocks 20 --probes 20 --ascent 5 --families cosine jakes cost2100
```

## 4. Check progress (any terminal)

```powershell
cd C:\Users\athawerani\Documents\Abraheem_work\paper2\Citradel-Rx
foreach ($d in "rev_cal_tune","rev_cal_citadel","rev_p1","rev_p2","rev_p3_adaptive","rev_p3_refdeg","rev_p3_deny","rev_p3_phys","rev_p3_know","rev_p4_paired","rev_p5_ablate","rev_p6_blocklen","rev_p6_arrays","rev_p6_qam16","rev_p6_deploy","rev_p7_sens","rev_p7_heat","rev_p8_drift","rev_p8_horizon","rev_clean") { "$d : $((Get-ChildItem results\$d -Filter *.json -ErrorAction SilentlyContinue).Count)" }
```

The campaign terminal also prints `[done/total]` on every finished run.

## 5. Analyse and push (after the campaign)

The report step must run on this machine (it reads the level snapshots, which are not pushed).

```powershell
python scripts\revision_report.py
git add configs\revision_frozen.json docs\ results\rev_cal_tune\*.json results\rev_cal_citadel\*.json results\rev_clean\*.json
foreach ($d in Get-ChildItem results -Directory -Filter "rev_p*") { git add "results\$($d.Name)\*.json" }
git commit -m "Revision campaign results"
git push origin claude/fervent-cray-ah5drn
```

Only `*.json` records are added; never `git add -f results\` (the `.npz` snapshots are large).

## If something goes wrong

* Machine rebooted: re-run step 2. Finished runs are skipped.
* `FAIL` lines: copy the first one here; the campaign continues with the other runs.
* To run only some groups after Phase A: `python scripts\revision_campaign.py --phase B --only P1 P3 --workers 8`.
