# Phase 0 report: workstation ws5080

Reviewed: commit `833ef72` (records in `results/v3/phase0/`, log `logs/v3/phase0_ws5080.log`).

## Machine

| Item | Value |
|---|---|
| CPU | Intel Core Ultra (family 6, model 198), 20 cores without hyper-threading |
| RAM / free disk | 63.5 GB / 727 GB |
| GPU | RTX 5080, 15.9 GB, compute capability 12.0; GPU kernels pass |
| Software | Windows 11, Python 3.12.10, PyTorch 2.9.1+cu128, numpy 2.5.4, scipy 1.18.1, Sionna 2.2.0 (lock: `logs/v3/env_ws5080.txt`) |

The first setup attempt failed: Sionna put its modules on the GPU, and the LDPC check gave them CPU
tensors. This was fixed in `7f46098` by pinning Sionna to the CPU in the framer, the UMi generator
and the check. The coded-link runs of later phases would have failed the same way.

## Unit tests

50 of 50 passed, the LDPC tests included (Sionna installed).

## Reproduction of stored records

| Record | Machine | Bit-identical | Identical blocks | max \|ΔSER\| | Mean SER (new / stored) |
|---|---|---|---|---|---|
| Clean twin, seed 10 | ws5080 | no | 2 / 100 | 0.0079 | 0.01516 / 0.01498 |
| White-box A1, seed 10 | ws5080 | no | 3 / 100 | 0.0083 | 0.02051 / 0.02069 |
| Clean twin, seed 10 | ccrcloud (Linux, same library versions) | **yes** | 100 / 100 | 0 | 0.01498 / 0.01498 |
| White-box A1, seed 10 | ccrcloud | **yes** | 100 / 100 | 0 | 0.02069 / 0.02069 |

**Why Windows differs.** The new library versions alone change nothing: the Linux container
reproduces both records bit for bit with them. The Windows build of PyTorch uses different
floating-point kernels, so the runs diverge from block 0 (the gate verdicts differ from the first
block). Test-time training amplifies rounding differences into a different trajectory, which is
the expected behavior of these learners, not a fault.

**What matters for the statistics holds.**
- **Within the machine, the pairing is exact.** On ws5080 the attacked run and its clean twin agree
  bit for bit on all 28 blocks before the attack window. That is the property the excess-SER
  pairing needs, and `scripts/v3/analyze.py` checks it for every pair.
- **Statistically, the results agree.** Seed 10, A1 at SIR 0 dB:

  | Machine | Window excess SER | Rejected | False rejections |
  |---|---|---|---|
  | ws5080 | +0.0134 | 40/40 | 0/95 |
  | Linux | +0.0143 | 39/40 | 0/95 |

**Consequence (already the protocol):**
- Every v3 result is paired only with clean twins from ws5080.
- v3 numbers are not mixed with second-campaign records in one cell.
- The paper states the software stack and machine of every table.

## Throughput

| Device | Parallel runs | Pre-training (s) | s per block | Full attacked run (min) | Runs per hour |
|---|---|---|---|---|---|
| CPU | 1 | 122 | 2.19 | 6.1 | 9.9 |
| CPU | 10 | 226 | 2.36 | 8.1 | 74.2 |
| **CPU** | **20** | 519 | 3.36 | 14.7 | **81.5** |
| GPU | 1 | 21 | 3.44 | 6.4 | 9.4 |
| GPU | 4 | 16 | 3.28 | 6.1 | 39.5 |
| GPU | 10 | 32 | 4.99 | 9.4 | 63.9 |

**Choice:** CPU with 20 parallel runs, about 80 full runs per hour, roughly 8× the old cloud
machines.
- The GPU pre-trains 6× faster, but the per-block work (small per-user networks, many small kernels)
  is slower there.
- With `--workers 16` the machine stays usable, at about 10% less throughput.

## Gate

Passed. Environment, tests, reproduction (within-machine determinism) and throughput are
established. Phase 1 runs on this machine with the settings above.
