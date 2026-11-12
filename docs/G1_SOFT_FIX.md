# Soft G1 term of the adaptive attacker: scale fix and re-run

## What was wrong

The soft-gate surrogate replaces the receiver's hard gate verdicts with smooth ones, so that the
attacker's objective can follow the gates. Its G1 term is computed by `Attacker._g1_soft`
(`citadel_rx/attacks/pilot_poisoning.py`): the residual of the linear model with the posterior-mean
symbols of the victim's detector, divided by the LMMSE residual (`physics.model_residual`) and by the
receiver's clean running statistic.

`_g1_soft` averaged the squared residual over the 2N real coordinates of the stacked received vector
`[Re y, Im y]`. The receiver's G1 (`physics.model_residual`) averages |.|^2 over the N complex
antennas. For complex modulation (QPSK in every affected run) the attacker's statistic was therefore
half of the receiver's statistic at the same symbols. Its soft G1 verdict sat near one and the G1 term
hardly shaped the objective. These attacks were weaker on G1 than the paper described.

Found while tracing every equation of the ten-page version to the code (math trace, finding P1).

## Fix

`_g1_soft` now sums the squared residual over the real and imaginary parts and divides by N, the scale
of `physics.model_residual`. For real modulation the value is unchanged.
`tests/test_attack_g1_scale.py` checks that the two residuals agree for one-hot decisions (QPSK and
BPSK).

## Which records are affected

The soft-gate objective is used (`use_soft` in `Attacker.craft`) by every attack with
`attack.soft_gate=true` **and by every A4 and A3\* attack**, whenever the victim has gates. Records of
these attacks against Citadel-Rx, by folder:

| folder | experiment | records | re-run into |
|---|---|---|---|
| `rev_p3_adaptive` | soft gates at SIR 0 and 10 dB, combined attack at SIR 0 dB | 15 | `rev_p3_adaptive_g1fix` |
| `rev_p3_refdeg` | A4, alpha 0.25 and 0.75, with and without the first abstain state | 14 | `rev_p3_refdeg_g1fix` |
| `rev2_abstain_v3` | A4 against the abstain state, seeds 10-19 | 20 | `rev2_abstain_v3_g1fix` |
| `rev2_a4_pgd20` | A4 with 20 PGD steps | 5 | `rev2_a4_pgd20_g1fix` |
| `rev_p8_drift` | A3\*, 5, 20 and 50 % of the pilot norm, 400 blocks | 8 | `rev_p8_drift_g1fix` |
| `rev2_drift_guard` | A3\*, 5 %, with the drift guard | 2 | `rev2_drift_guard_g1fix` |
| `rev2_drift_long` | A3\*, 5 %, 1000 blocks | 2 | `rev2_drift_long_g1fix` |

Not affected: attacks without the soft-gate objective (A1, A2, unrolled and PGD variants, physical,
grey-box, query, denial), and soft-gate attacks on receivers without gates (`p3_online_strongest`:
`_soft_gamma` returns one there). `rev2_abstain` (`h3_a4_a0.25_ratio`, the abandoned first abstain
statistic) is affected but read by no script; it is not re-run.

## Re-run

`scripts/rerun_g1fix.py` finds the affected records itself and re-runs each one with the settings read
from its own record, so the fixed line is the only difference. The old records stay where they are.

Pairing with clean twins:

* `softgate` and `a3star`: the clean twin of every attacked run is run on the same machine
  (`results/rev_clean_<machine>`; the A3\* twins save level snapshots, and `scripts/paired_disp.py`
  writes the paired displacements into the attacked records on that machine).
* `a4`: the attacked run carries `pairs_as`, the machine that ran the record it replaces, and is paired
  with that machine's stored clean twin. Two checks support this:
  1. Every pair is checked on its own. Before the attack window starts, an attacked run follows its
     clean twin exactly (the attacker draws from its own random generators), so on machines that give
     identical runs the per-block SER and gate verdict before the window agree bit for bit. This holds
     for all 42 stored A4 and soft-gate pairs (13 to 42 blocks each, machines cloud, pool1-5, pool9,
     pool10, pool12, pool13). `revision_numbers.cell` keeps a `pairs_as` pair only if it holds
     (`same_before_window`).
  2. The machines agree in general. The clean twins of seeds 10-14 re-run on `pool12` and `pool13`
     equal those of `cloud` and `pool1`-`pool5` block for block, while the MacBook's differ; each
     machine that uses `pairs_as` also repeats a stored cloud clean run (`--probe-only`) and writes
     the comparison to `results/g1fix_probe/<machine>.json`. (The probe of the first script version
     compared raw settings and so found no stored record to compare with; it was fixed in 2a184c2 and
     repeated.)

`scripts/revision_numbers.py` (`with_g1fix`) switches an experiment to its re-runs only when every one
of its seeds has been re-run, so no table cell mixes the two attack versions.

| machine | job | command |
|---|---|---|
| pool13 | soft gates, seeds 10-12 | `rerun_g1fix.py --family softgate --seeds 10 11 12` |
| pool12 | soft gates, seeds 13-14 | `rerun_g1fix.py --family softgate --seeds 13 14` |
| pool14-pool17 | A4, four balanced shards | `rerun_g1fix.py --family a4 --shard k/4` |
| pool18 | A3\*, seed 10 | `rerun_g1fix.py --family a3star --seeds 10` |
| pool20 | A3\*, seed 11, 400-block runs | `rerun_g1fix.py --family a3star --seeds 11 --folders rev_p8_drift rev2_drift_guard` |
| pool19 | A3\*, seed 11, 1000-block run | `rerun_g1fix.py --family a3star --seeds 11 --folders rev2_drift_long` |

(The soft-gate runs of pool12 and pool13 were made with the first version of the script, which wrote
them to `results/rev_p3_g1fix`; the folder was renamed afterwards. pool19 first ran all ten seed-11 A3\*
jobs; its container restarted and the jobs were split between pool19 and pool20. Three records that
orphaned workers of the stopped run wrote on pool19 have no clean twin there and are not used; they
are kept with pool19's files on the `snapshots` branch.)

## What changed in the results

Same settings, seeds and clean twins; only the soft G1 term differs. Excess SER over the clean twin
(window mean, mean over seeds) and the fraction of attacked blocks the gates rejected. Values from
`paper/numbers.tex` before and after the switch (the paper reports the right-hand values).

| experiment | excess before | excess after | rejected before | rejected after |
|---|---|---|---|---|
| soft gates, SIR 0 dB | +0.0190 | +0.0193 | 200/200 | 200/200 |
| soft gates, SIR 10 dB | +0.0099 | +0.0103 | 200/200 | 200/200 |
| combined attack, SIR 0 dB | +0.0196 | +0.0197 | 200/200 | 200/200 |
| A4, alpha 0.25 | +0.0531 | +0.0337 | 110/200 | 152/200 |
| A4, alpha 0.25, 20 PGD steps | +0.0447 | +0.0478 | 165/200 | 155/200 |
| A4, alpha 0.75 | +0.0448 | +0.0276 | 195/200 | 197/200 |
| A4, alpha 0.25, first abstain state | +0.0233 | +0.0102 | | |
| A4, alpha 0.75, first abstain state | +0.0250 | +0.0126 | | |
| A4, alpha 0.25, abstain state (seeds 10-14) | +0.0479 | +0.0213 | 147/200 | 192/200 |
| A4, alpha 0.25, abstain state (seeds 15-19) | +0.0367 | +0.0214 | 188/200 | 191/200 |
| A4, alpha 0.75, abstain state (seeds 10-14) | +0.0384 | +0.0249 | | |
| A4, alpha 0.75, abstain state (seeds 15-19) | +0.0347 | +0.0242 | | |
| A3\*, 5 %, 400 blocks | +0.0019 | +0.0017 | 1/600 | 1/600 |
| A3\*, 20 % | +0.0117 | +0.0122 | 164/600 | 135/600 |
| A3\*, 50 % | +0.0097 | +0.0109 | 600/600 | 599/600 |
| A3\*, 50 %, drift guard | +0.0101 | +0.0110 | 600/600 | 599/600 |
| A3\*, 5 %, drift guard | +0.0019 | +0.0017 | 2/600 | 2/600 |
| A3\*, 5 %, 1000 blocks | +0.0019 | +0.0016 | 2/1800 | 1/1800 |

In these runs the A4 attacker with 6 PGD steps was rejected more often and did less damage than before
the fix; with 20 steps it was rejected about as often as with 6 and did more damage. Why the corrected
surrogate gives the weaker 6-step attack was not analysed. The soft-gate and combined attacks on the
pilots alone, which the gates reject in every block either way, are unchanged within their intervals.

Code versions. Between the code versions that wrote the replaced A4 and soft-gate records and the fix,
the attack code changed only for the physical attacker with CSI error and the 3GPP scene (commits
6dff477, efbce92), which these runs do not use. Receiver changes in that period are behind options
that default to the earlier behavior (for example `citadel.abstain_mode = legacy`, the first abstain
state); the clean twins re-run with the current code equal the stored ones block for block, and every
re-run equals its twin before the attack window.
