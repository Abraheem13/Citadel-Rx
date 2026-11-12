# Phase 0: Setup, reproduction and benchmark (RTX 5080 workstation, Windows 11)

The plan is in `docs/ROADMAP_9of10.md`. This phase answers three questions before any new experiment:

1. Does the code run correctly on this machine (unit tests, GPU kernels, Sionna LDPC)?
2. Does it reproduce stored records of the earlier campaign, and if not, how close is it?
3. How many runs per hour can the machine sustain, and on which device (CPU or GPU) and with how many
   parallel runs?

Expected time: 20 minutes of setup, then about 1–1.5 hours unattended.

## Before you start (once)

Run these in **PowerShell**; each must print a version:

```powershell
nvidia-smi
```
The driver must be **570 or newer** (CUDA 12.8 support for the RTX 50 series). If it is older, update
it from nvidia.com and restart.

```powershell
py -3.12 --version
```
If this fails, install Python 3.12 (64-bit) from python.org. Tick "Add python.exe to PATH" and keep
the "py launcher" option.

```powershell
git --version
```
If this fails, install Git for Windows (git-scm.com), then:

```powershell
git config --global core.longpaths true
```

```powershell
git config --global user.name "Abraheem Rashid"
```

```powershell
git config --global user.email "<the email of your GitHub account>"
```

Keep the PC on mains power, and stop it sleeping while it computes:

```powershell
powercfg /change standby-timeout-ac 0
```

## 1. Get the code

```powershell
cd $HOME
```

```powershell
git clone https://github.com/Abraheem13/Citadel-Rx.git
```

```powershell
cd Citadel-Rx
```

## 2. Create the environment (about 10–15 minutes, downloads about 3 GB)

```powershell
py -3.12 scripts\v3\setup_env.py
```

It must end with `== environment ready`, and its checks must show `cuda_available True`,
`capability [12, 0]`, `gpu_kernel_ok True` and `ldpc_roundtrip_ok True`. If it stops with an error,
send the full output.

## 3. Run Phase 0 (about 1–1.5 hours, unattended)

```powershell
.venv\Scripts\python.exe scripts\v3\phase0.py
```

The script runs four steps:

1. **Machine:** cores, memory, GPU and library versions.
2. **Unit tests:** the full suite.
3. **Reproduction:** re-runs two stored records (a clean run and a white-box A1 run, seed 10) and
   compares them block by block.
4. **Benchmark:** short attacked runs on the CPU and on the GPU, with 1 up to all cores in parallel.

It ends with a line such as `== summary: tests OK, repro OK, bench OK`. You can use the PC lightly
in the meantime, but heavy use distorts the benchmark.

## 4. Push the results

```powershell
git add results/v3/phase0 logs/v3
```

```powershell
git commit -m "Phase 0 results (ws5080)"
```

```powershell
git pull --rebase origin main
```

```powershell
git push origin main
```

The first push opens a browser window to log in to GitHub. Then tell me "Phase 0 pushed". I check
every file and write `docs/v3/PHASE0_REPORT.md`, and Phase 1 follows.

## What is checked in the review

| Check | Pass criterion |
|---|---|
| Environment | PyTorch with CUDA 12.8 sees the RTX 5080 (capability 12.0); the LDPC round trip works |
| Unit tests | all pass (the LDPC tests now run as well, since Sionna is installed) |
| Reproduction | identical to the stored x86 Linux records, or the size of the difference is measured and explained (Windows / newer numpy may differ in the last bits). New results are paired only with twins from this machine either way. |
| Benchmark | at least one device/parallelism setting with no failed runs; the choice sets the number of workers for Phase 1 |
