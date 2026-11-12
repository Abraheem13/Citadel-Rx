#!/usr/bin/env python
"""3GPP TR 38.901 UMi channels with the attacker placed in the scene (reviewer audit D3).

For every seed and attacker distance, one drop of the UMi street-canyon model (Sionna PHY 2.2,
`sionna.phy.channel.tr38901.UMi`, path loss, LoS probability and shadow fading of 38.901) with
  * a base station at 10 m height with a 1 x N array (single polarisation, 38.901 element pattern);
  * U users at uniform distances in [20, 150] m and angles in [-60, 60] deg, 1.5 m high, moving at
    3 km/h in random directions; ideal slow power control: every user's channel is scaled to unit
    mean received power per antenna (the noise power then sets the SNR of the paper, 10 dB);
  * the attacker, a single-antenna transmitter at distance d at the maximum power of a user;
  * a power-control target fixed by the model, not by a random draw: the mean received power of 32
    cell-edge users (150 m, random angles, 3 km/h) at maximum power in NLoS without shadow fading
    (same model, LoS forced off, shadowing off). A user
    that cannot reach it at maximum power arrives weaker (its received power is min(g_u, g_target)).
The attacker's channel is scaled by the same factor, so its received power relative to the target is
g_att / g_target, and the geometric SIR, relative to the users' received signal power, is
SIR = 10 log10(sum_u min(g_u, g_target) / g_att): it follows from the geometry, not from a setting.

Each block is one narrowband channel (the frequency response at the carrier) sampled every
T_block = 1 ms: one NR slot at 15 kHz subcarrier spacing, whose 14 x 12 x 150 = 25,200 resource
elements match the block length of the paper (25,000 data symbols; about 27 MHz). At 3 km/h and
3.5 GHz the channel then changes by about 4% between blocks (relative Frobenius norm), as in the
paper's other channel models (3.5% synthetic, 1.3% COST2100); frequency selectivity within a block
is not modelled.

One drop per seed holds the users, one attacker at each distance and the reference, so the users'
channels (and the clean comparison run) are the same for every attacker position.

    python scripts/make_umi_channels.py --seeds 10 11 12 13 14 --dists 35 75 150
writes resources/umi/umi_N4_U4_s{seed}.npz (H: blocks x N x U; G_d{d}: blocks x N x 1 and sir_d{d}
for every distance; meta)
"""
from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "resources", "umi")


def drop(seed: int, dists, n_ant: int, n_user: int, n_blocks: int, t_block: float, fc: float, speed_kmh: float) -> dict:
    import sionna.phy
    from sionna.phy.channel.tr38901 import UMi, PanelArray
    sionna.phy.config.seed = seed
    rng = np.random.default_rng(seed + 38901)
    bs_array = PanelArray(num_rows_per_panel=1, num_cols_per_panel=n_ant, polarization="single", polarization_type="V",
                          antenna_pattern="38.901", carrier_frequency=fc)
    ut_array = PanelArray(num_rows_per_panel=1, num_cols_per_panel=1, polarization="single", polarization_type="V",
                          antenna_pattern="omni", carrier_frequency=fc)
    model = UMi(carrier_frequency=fc, o2i_model="low", ut_array=ut_array, bs_array=bs_array, direction="uplink",
                enable_pathloss=True, enable_shadow_fading=True)
    n_att = len(dists)
    # users, then one attacker per distance, then the cell-edge reference
    r = np.concatenate([rng.uniform(20.0, 150.0, n_user), np.asarray(dists, dtype=float), [150.0]])
    n_ut = n_user + n_att + 1
    phi = np.deg2rad(rng.uniform(-60.0, 60.0, n_ut))
    ut_loc = np.stack([r * np.cos(phi), r * np.sin(phi), np.full(n_ut, 1.5)], -1)[None]
    v = speed_kmh / 3.6
    head = rng.uniform(0, 2 * np.pi, n_ut)
    vel = np.stack([v * np.cos(head), v * np.sin(head), np.zeros(n_ut)], -1)
    vel[n_user:] = 0.0                                     # attackers and reference: static
    t = lambda x: torch.as_tensor(x, dtype=torch.float32)
    model.set_topology(ut_loc=t(ut_loc), bs_loc=t([[[0.0, 0.0, 10.0]]]), ut_orientations=t(np.zeros((1, n_ut, 3))),
                       bs_orientations=t(np.zeros((1, 1, 3))), ut_velocities=t(vel[None]),
                       in_state=torch.zeros((1, n_ut), dtype=torch.bool))
    a, tau = model(num_time_samples=n_blocks, sampling_frequency=1.0 / t_block)
    a = a.detach().cpu().numpy()                            # (1, 1, N, n_ut, 1, paths, T)
    Hf = a[0, 0, :, :, 0, :, :].sum(axis=2)                 # frequency response at the carrier: (N, n_ut, T)
    Hf = np.transpose(Hf, (2, 0, 1))                        # (T, N, n_ut)
    g = (np.abs(Hf) ** 2).mean(axis=(0, 1))                 # mean received power per antenna, per transmitter
    # deterministic power-control target: cell-edge user, NLoS, no shadow fading
    edge = UMi(carrier_frequency=fc, o2i_model="low", ut_array=ut_array, bs_array=bs_array, direction="uplink",
               enable_pathloss=True, enable_shadow_fading=False)
    ne = 32                                                  # 32 moving cell-edge users averaged: small-scale fading averages out
    pe = np.deg2rad(rng.uniform(-60.0, 60.0, ne))
    he = rng.uniform(0, 2 * np.pi, ne)
    edge.set_topology(ut_loc=t(np.stack([150 * np.cos(pe), 150 * np.sin(pe), np.full(ne, 1.5)], -1)[None]),
                      bs_loc=t([[[0.0, 0.0, 10.0]]]), ut_orientations=t(np.zeros((1, ne, 3))), bs_orientations=t(np.zeros((1, 1, 3))),
                      ut_velocities=t(np.stack([v * np.cos(he), v * np.sin(he), np.zeros(ne)], -1)[None]),
                      in_state=torch.zeros((1, ne), dtype=torch.bool), los=False)
    ae, _ = edge(num_time_samples=n_blocks, sampling_frequency=1.0 / t_block)
    g_target = float((np.abs(ae.detach().cpu().numpy()[0, 0, :, :, 0, :, :].sum(axis=2)) ** 2).mean())
    p_rx = np.minimum(g[:n_user], g_target) / g_target      # users' received power relative to the target
    H = Hf[:, :, :n_user] / np.sqrt(g[:n_user])[None, None, :] * np.sqrt(p_rx)[None, None, :]
    out = {"H": H.astype(np.complex64), "path_gain_db": (10 * np.log10(g)).tolist(), "target_db": 10 * math.log10(g_target),
           "user_rx_db": (10 * np.log10(p_rx)).tolist(), "dist": r.tolist(), "angle_deg": np.rad2deg(phi).tolist()}
    for i, d in enumerate(dists):
        out[f"G_d{d:g}"] = (Hf[:, :, n_user + i:n_user + i + 1] / np.sqrt(g_target)).astype(np.complex64)
        out[f"sir_d{d:g}"] = 10 * math.log10(p_rx.sum() / (g[n_user + i] / g_target))
    try:
        out["los"] = model._scenario.los.detach().cpu().numpy()[0].tolist()   # internal: LoS state per link
    except Exception:
        out["los"] = None
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=[10, 11, 12, 13, 14])
    ap.add_argument("--dists", type=float, nargs="+", default=[35.0, 75.0, 150.0])
    ap.add_argument("--n-ant", type=int, default=4)
    ap.add_argument("--n-user", type=int, default=4)
    ap.add_argument("--blocks", type=int, default=100)
    ap.add_argument("--t-block", type=float, default=0.001)
    ap.add_argument("--fc", type=float, default=3.5e9)
    ap.add_argument("--speed-kmh", type=float, default=3.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for s in args.seeds:
        out = drop(s, args.dists, args.n_ant, args.n_user, args.blocks, args.t_block, args.fc, args.speed_kmh)
        fn = os.path.join(OUT, f"umi_N{args.n_ant}_U{args.n_user}_s{s}.npz")
        arrays = {k: v for k, v in out.items() if k == "H" or k.startswith("G_d") or k.startswith("sir_d")}
        meta = {k: out[k] for k in ("path_gain_db", "target_db", "user_rx_db", "dist", "angle_deg", "los")}
        meta.update(t_block=args.t_block, fc=args.fc, speed_kmh=args.speed_kmh)
        np.savez(fn, **arrays, meta=json.dumps(meta))
        for d in args.dists:
            summary.append({"d_att": d, "seed": s, "sir_db": round(out[f"sir_d{d:g}"], 2)})
        print(f"seed {s}: " + ", ".join(f"d {d:g} m -> SIR {out[f'sir_d{d:g}']:+.1f} dB" for d in args.dists)
              + f" | target {out['target_db']:.0f} dB, users rx (dB rel. target) " + " ".join(f"{x:.0f}" for x in out["user_rx_db"]), flush=True)
    json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
