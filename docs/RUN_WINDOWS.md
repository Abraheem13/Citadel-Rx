# Second revision campaign on the Windows laptop

One command runs the Windows share of the second campaign (`scripts/revision_fast.py --campaign 2
--shard windows`): seeds 12–14 for the attacks built against the defence, the physical, grey-box,
query and budget attacks and the denial runs; the full-rank physical attacker; denial of adaptation
by strong poisoning during a channel redraw (streak recovery); per-user gating against a
single-user attack; seeds 12–14 for the ablations, block lengths, arrays, 16-QAM and the cheaper
variants; and the sensitivity at x0.75 / x1.5 with a two-setting grid. The cloud machine runs the
rest. The two machines never run the same job.

## First time (cmd)

```
winget install -e --id Git.Git
winget install -e --id Python.Python.3.12
```

Close the terminal and open a new one (so that `git` and `py` are found), then:

```
cd %USERPROFILE%\Documents
git clone https://github.com/abraheemrashid99-sys/Citradel-Rx.git
cd Citradel-Rx
git checkout claude/fervent-cray-ah5drn
py -3.12 scripts\run_windows.py
```

When the script checks push access, a browser window asks you to sign in to GitHub: use the
account `abraheemrashid99-sys`. The first start installs PyTorch (CPU) into `.venv` (about
3 GB of disk, a few minutes) and runs the tests.

## Every later start (also after any interruption)

```
cd %USERPROFILE%\Documents\Citradel-Rx
py -3.12 scripts\run_windows.py
```

Finished runs are skipped; results are pushed to GitHub every 45 minutes and at the end.

## While it runs

* Keep the laptop plugged in. The script stops Windows from sleeping; if you close the lid, set
  Control Panel > Power Options > "Choose what closing the lid does" > Plugged in: Do nothing.
* The number of parallel runs is chosen from the free memory (at most 4). Close the browser and
  other programs before starting to get more. To set it yourself: `py -3.12 scripts\run_windows.py --workers 3`.
* To run only the most important part: `--tier 1` (tier 2 adds ablations and scenarios, tier 3 the
  sensitivity grid).
