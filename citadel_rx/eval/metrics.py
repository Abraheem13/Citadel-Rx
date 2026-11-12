"""Per-block and summary metrics."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np


def block_metrics(idx_hat: np.ndarray, idx_true: np.ndarray, mod, crc_pass: Optional[np.ndarray]) -> Dict[str, Any]:
    wrong = idx_hat != idx_true                                       # (n, U)
    ser_vec = float(wrong.any(axis=1).mean())                         # reference SER (any user wrong)
    ser_user = wrong.mean(axis=0)                                     # (U,)
    bits_hat = mod.indices_to_bits(idx_hat.T)
    bits_true = mod.indices_to_bits(idx_true.T)
    ber = float((bits_hat != bits_true).mean())
    out = {"ser": ser_vec, "ser_sym": float(wrong.mean()), "ser_user": ser_user.tolist(), "ber": ber}
    if crc_pass is not None:
        out["bler"] = float(1.0 - crc_pass.mean())
    return out


def summarise(blocks: List[Dict[str, Any]], attack_window: Optional[tuple]) -> Dict[str, Any]:
    ser = np.array([b["ser"] for b in blocks])
    n = len(ser)
    s: Dict[str, Any] = {"ser_mean": float(ser.mean()), "ser_median": float(np.median(ser)),
                         "ber_mean": float(np.mean([b["ber"] for b in blocks]))}
    if "bler" in blocks[0]:
        s["bler_mean"] = float(np.mean([b["bler"] for b in blocks]))
    if attack_window is not None:
        a0, a1 = attack_window
        a0, a1 = max(0, min(a0, n)), max(0, min(a1, n))
        pre = ser[:a0]
        dur = ser[a0:a1]
        post = ser[a1:]
        s["ser_pre"] = float(pre.mean()) if pre.size else None
        s["ser_attack"] = float(dur.mean()) if dur.size else None
        s["ser_post"] = float(post.mean()) if post.size else None
        # recovery time: blocks after the attack until SER returns within 10% (relative) of the
        # pre-attack mean, measured on a 3-block moving average
        if pre.size and post.size:
            ref = pre.mean() * 1.1 + 1e-6
            rec = None
            for i in range(post.size):
                win = post[i: i + 3]
                if win.mean() <= ref:
                    rec = i
                    break
            s["recovery_blocks"] = rec if rec is not None else int(post.size)  # censored at window end
            s["recovery_censored"] = rec is None
    # gate statistics if present
    for key in ("gamma", "surprise_ratio", "eta"):
        if key in blocks[0]:
            s[f"{key}_mean"] = float(np.mean([b[key] for b in blocks]))
    if "gamma" in blocks[0] and attack_window is not None:
        a0, a1 = attack_window
        g = np.array([b["gamma"] for b in blocks])
        att = np.array([b.get("attacked", False) for b in blocks])
        if att.any():
            s["gate_reject_rate_attacked"] = float((g[att] < 0.5).mean())
        if (~att).any():
            s["gate_false_reject_rate_clean"] = float((g[~att] < 0.5).mean())
    return s


def degradation_db(snr_grid: np.ndarray, ser_clean: np.ndarray, ser_attacked: np.ndarray) -> np.ndarray:
    """SNR shift (dB) needed under attack to reach the clean SER at each grid SNR.
    Both curves must be monotone decreasing in SNR; interpolation in log-SER."""
    ls_c = np.log10(np.clip(ser_clean, 1e-6, 1))
    ls_a = np.log10(np.clip(ser_attacked, 1e-6, 1))
    out = np.full_like(snr_grid, np.nan, dtype=float)
    order = np.argsort(ls_a)
    for i, target in enumerate(ls_c):
        if target < ls_a.min():
            # the attacked curve never reaches the clean SER within the grid: lower-bound the shift
            out[i] = snr_grid.max() - snr_grid[i] + 1e-9 if ls_a.min() > target else np.nan
            out[i] = np.inf if snr_grid.max() == snr_grid[i] else out[i]
            continue
        if target > ls_a.max():
            out[i] = 0.0  # attacked SER is below the clean SER everywhere: no degradation
            continue
        snr_needed = np.interp(target, ls_a[order], snr_grid[order])
        out[i] = snr_needed - snr_grid[i]
    return out
