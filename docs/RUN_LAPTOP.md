# Revision campaign on the MacBook (one command)

The GPU workstation is down, so the revision experiments run on two machines at once:
this MacBook (the larger part) and the 4-core cloud machine of the Claude session (Citadel-Rx
calibration, paired displacement, the joint pilot + data attack and the 400-block drift attack).
The two never run the same job, and both push to the branch `claude/fervent-cray-ah5drn`.

## 1. Free disk space (needs about 1.5 GB)

The Python environment is about 0.7 GB, the pre-training cache at most 0.6 GB, the repository
about 0.25 GB. In the VS Code terminal:

```bash
conda clean -a -y
pip cache purge
```

and empty the Bin. Check with `df -h ~` (column "Avail").

## 2. Get the code

If the repository is not on the laptop yet (VS Code: sign in to GitHub first, or use a personal
access token as the password):

```bash
cd ~/Documents
git clone -b claude/fervent-cray-ah5drn https://github.com/abraheemrashid99-sys/Citradel-Rx.git
cd Citradel-Rx
```

If it is already there: `cd` into it; the script below switches to the branch and pulls.
Then in VS Code: File > Open Folder > `Citradel-Rx`, and Terminal > New Terminal.

## 3. Run everything

```bash
bash scripts/run_laptop.sh
```

(`make laptop` does the same.) It creates `.venv` with Python 3.10+ (your conda base is not
changed), installs the requirements, runs the tests (a few minutes), then runs the laptop part of
the campaign with 8 parallel runs while keeping the Mac awake (`caffeinate`). Keep the Mac on
power with the lid open, and leave the terminal open.

Every finished run prints one line, for example

```
[37 done, ~299 left | 1.2 h, ~4.6 h to go at this pace] t1 P1 p1_citadel__wb_sir0 s13 OK 11 min  == ...
```

The time estimate is too high during the first ten or so runs (it divides by the finished runs
while 8 run in parallel) and settles after that. Results are committed and pushed to GitHub every
45 minutes and at the end, so the cloud session
can analyse them while the rest runs. A log is written to `logs/laptop_<date>.log`.

## 4. Interruptions

* Anything stops (crash, Ctrl-C, reboot, VS Code closed): run `bash scripts/run_laptop.sh` again.
  Finished runs are skipped; at most the runs that were in progress are repeated.
* To stop early and push what is done: Ctrl-C, then
  `.venv/bin/python scripts/revision_fast.py --shard laptop --push-only`.
* Fewer parallel runs (if the Mac is too hot or slow to use): `WORKERS=6 bash scripts/run_laptop.sh`.
* Only the runs the revised claims need: `TIER=1 bash scripts/run_laptop.sh`.
* `FAIL` lines: the campaign continues; send the first one to the Claude session.
* `git push` asks for a password: use a GitHub personal access token (Settings > Developer settings
  > Personal access tokens), or sign in to GitHub in VS Code. The results stay committed locally
  until a push works.

## 5. What runs where, and how long

Durations below are estimates from timings on the cloud machine; the script prints the real pace.

| tier | laptop runs | content | estimate |
|---|---|---|---|
| 0 | 72 | baseline tuning on calibration seeds 0-2: epochs x learning rate x weight decay (C5) | ~1 h |
| 1 | 264 | headline grid with 10 test seeds at SIR 0 dB and 3 elsewhere (E2, E3, C1, H6); attacks built against the defence (B4); ablations (P5); physical, grey-box, query and signal-budget attackers (B1, B6, B8); denial of adaptation and abrupt change (B3, D6) | ~4 h |
| 2 | 124 | remaining and new baselines (C2-C4, C6, C7); block length, 4x16 array, 16-QAM, 30-step and last-layer variants (D1, D4, D5, D9) | ~2 h |
| 3 | 32 | one-at-a-time sensitivity at x0.5 and x2 (E5) | ~0.5 h |

Cloud machine: Citadel-Rx calibration (seeds 0-2; its frozen choice is fetched automatically by the
laptop from GitHub before the first Citadel-Rx run), paired displacement (E7, A2), joint pilot +
data reference degradation with and without the abstain state (B2), and the optimised slow drift
over 400 blocks with and without the drift guard (B5).

Every number in the revised paper is computed from the pushed records by `make report`
(`scripts/revision_report.py`), which also states the number of seeds of every cell.

## Reproducibility notes

* Settings chosen on calibration seeds (0-2) by fixed rules: `configs/revision_frozen_baselines.json`
  (laptop) and `configs/revision_frozen_citadel.json` (cloud). Test seeds are 10-19.
* Pre-training is cached (`cache/pretrain`, not pushed): an identical configuration, seed and
  random-number state reuse the pre-trained weights and the random-number state that followed, so
  results are identical to an uncached run (`tests/test_pretrain_cache.py`). `rm -rf cache` is safe.
* Each record stores its full configuration, seed, code version and timings. Records of the two
  machines differ only in floating-point rounding; every attacked run is compared with a clean run
  of the same configuration and seed on the same machine.
