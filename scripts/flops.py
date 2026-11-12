#!/usr/bin/env python
"""Machine-independent cost per coherence block (reviewer audit D9): multiply-accumulates (MACs) of
the operations the receivers perform per block, counted from the network dimensions of the code
(citadel_rx/receivers/deepsic.py), not measured. A backward pass is counted as twice the forward
MACs (the usual estimate for dense layers); elementwise operations, the CRC and LMMSE (an N x U
problem) are below 1% and left out.

  DeepSIC module (one user, one iteration): F_in = 2N + (M-1)(U-1) inputs, H = 64 M hidden, M outputs,
      forward MACs per symbol: F_in H + H M.
  Detection of N_d symbols: Q U N_d (F_in H + H M).
  One training step of one stage on N_p pilots: 3 U N_p (F_in H + H M) (forward and backward),
      plus the forward pass that builds the next stage's inputs.

    python scripts/flops.py          # prints the table and writes docs/flops.json
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def deepsic_macs(U: int, N: int, M: int, Q: int, N_p: int, N_d: int, steps: int, detections: int, hidden_base: int = 64):
    F_in, H = 2 * N + (M - 1) * (U - 1), hidden_base * M
    per_sym = F_in * H + H * M
    train = Q * steps * 3 * U * N_p * per_sym + (Q - 1) * U * N_p * per_sym
    detect = detections * Q * U * N_d * per_sym
    return {"params": Q * U * (F_in * H + H + H * M + M), "train": train, "detect": detect, "total": train + detect}


def table(U=4, N=4, M=4, Q=3, N_p=100, N_d=25000):
    rows = {
        # online DeepSIC with the tuned 30 steps per stage, one detection
        "online_deepsic": deepsic_macs(U, N, M, Q, N_p, N_d, steps=30, detections=1),
        # Citadel-Rx: 300 fast steps per stage, detections with the fast level and the anchor
        "citadel": deepsic_macs(U, N, M, Q, N_p, N_d, steps=300, detections=2),
        "citadel_steps30": deepsic_macs(U, N, M, Q, N_p, N_d, steps=30, detections=2),
        "crc_rollback": deepsic_macs(U, N, M, Q, N_p, N_d, steps=30, detections=1),
    }
    return rows


def main() -> None:
    out = {"4x4_qpsk": table(), "4x16_qpsk": table(N=16), "8x32_qpsk": table(U=8, N=32)}
    json.dump(out, open(os.path.join(ROOT, "docs", "flops.json"), "w"), indent=1)
    for sysname, rows in out.items():
        print(sysname)
        for rx, r in rows.items():
            print(f"  {rx:16s} params {r['params']:>9,d}  train {r['train'] / 1e9:7.2f} GMAC  detect {r['detect'] / 1e9:6.2f} GMAC"
                  f"  total {r['total'] / 1e9:7.2f} GMAC per block")


if __name__ == "__main__":
    main()
