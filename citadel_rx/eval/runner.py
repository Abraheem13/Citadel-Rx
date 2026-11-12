"""Sequential block runner: channel → (attacker) → receiver → metrics."""
from __future__ import annotations

import copy
import random
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch

from ..attacks import make_attacker
from ..channels import make_channel
from ..config import Config
from ..frames import FrameGenerator
from ..receivers import make_receiver
from .metrics import block_metrics, summarise
from .records import save_record


def pick_device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _code_digest() -> str:
    """Hash of the package source, so cached pre-training never outlives a code change."""
    import hashlib
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = hashlib.sha256()
    for d, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            if f.endswith(".py"):
                h.update(f.encode())
                h.update(open(os.path.join(d, f), "rb").read())
    return h.hexdigest()


def _rng_state():
    return {"torch": torch.get_rng_state(), "numpy": np.random.get_state(), "python": random.getstate()}


def _pretrain(cfg: Config, receiver, frames: FrameGenerator):
    """Pre-train, or load an earlier identical pre-training when CITADEL_PRETRAIN_CACHE is set.

    The cache key holds every setting except attack.* and run.* (the attacker and the logging do
    not enter pre-training), the source code and the exact random-number state before
    pre-training. A hit restores the pre-trained receiver and the random-number state after
    pre-training, so the run continues exactly as an uncached run (checked in tests)."""
    import hashlib
    import json
    import os
    cache = os.environ.get("CITADEL_PRETRAIN_CACHE", "")
    if not cache:
        receiver.pretrain(pretraining_blocks(cfg, frames))
        return receiver, False
    d = cfg.to_dict()
    d.pop("attack", None)
    d.pop("run", None)
    st = _rng_state()
    h = hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode())
    h.update(_code_digest().encode())
    h.update(st["torch"].numpy().tobytes())
    h.update(repr(st["numpy"][0]).encode() + np.asarray(st["numpy"][1]).tobytes() + repr(st["numpy"][2:]).encode())
    h.update(repr(st["python"]).encode())
    path = os.path.join(cache, f"{cfg.receiver.type}_{h.hexdigest()[:24]}.pt")
    if os.path.exists(path):
        try:
            blob = torch.load(path, weights_only=False)
            rx = blob["receiver"]
            if hasattr(rx, "cfg"):   # keep the receiver's own (possibly specialised) settings; refresh the
                rx.cfg.attack = copy.deepcopy(cfg.attack)   # sections outside the key, which receivers do not read
                rx.cfg.run = copy.deepcopy(cfg.run)
            torch.set_rng_state(blob["rng"]["torch"])
            np.random.set_state(blob["rng"]["numpy"])
            random.setstate(blob["rng"]["python"])
            return rx, True
        except Exception:
            pass
    receiver.pretrain(pretraining_blocks(cfg, frames))
    try:
        os.makedirs(cache, exist_ok=True)
        cap = float(os.environ.get("CITADEL_PRETRAIN_CACHE_GB", "1.0")) * 1e9
        used = sum(os.path.getsize(os.path.join(cache, f)) for f in os.listdir(cache))
        if used < cap:
            tmp = f"{path}.{os.getpid()}.part"
            torch.save({"receiver": receiver, "rng": _rng_state()}, tmp)
            os.replace(tmp, path)
    except Exception:
        pass
    return receiver, False


def pretraining_blocks(cfg: Config, frames: FrameGenerator) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Reference joint pre-training data: one static-channel block of `pretrain_bits` pilot
    bits per SNR in `pretrain_snrs` (fading disabled)."""
    rc = cfg.receiver
    out = []
    pcfg = copy.deepcopy(cfg.channel)
    pcfg.fading = "static"
    rng = np.random.default_rng(cfg.channel.seed + 77)
    for snr in rc.pretrain_snrs:
        pcfg.snr_db = float(snr)
        ch = make_channel(pcfg, frames.mod.is_complex)
        for blk in range(rc.pretrain_blocks):
            st = ch.state(blk)
            bits = rng.integers(0, 2, size=(cfg.channel.n_user, rc.pretrain_bits))
            idx = frames.mod.bits_to_indices(bits).T
            y = ch.transmit(frames.mod.modulate_indices(idx), st, rng)
            out.append((y, idx))
    return out


def run_experiment(cfg: Config, seed: Optional[int] = None, save: bool = True, verbose: bool = True,
                   progress_cb=None) -> Dict[str, Any]:
    seed = cfg.channel.seed if seed is None else seed
    cfg = copy.deepcopy(cfg)
    cfg.channel.seed = seed
    set_seed(seed)
    device = pick_device(cfg.run.device)

    frames = FrameGenerator(cfg)
    channel = make_channel(cfg.channel, frames.mod.is_complex)
    receiver = make_receiver(cfg, device)
    attacker = make_attacker(cfg, device, seed)
    if hasattr(receiver, "set_channel_rho"):
        receiver.set_channel_rho(channel.rho if cfg.channel.fading == "jakes" else 1.0)

    t0 = time.time()
    pretrain_cached = False
    if cfg.receiver.pretrain and cfg.receiver.type != "lmmse":
        receiver, pretrain_cached = _pretrain(cfg, receiver, frames)
    pretrain_time = time.time() - t0

    blocks: List[Dict[str, Any]] = []
    level_snaps: List[Dict[str, Any]] = []
    noise_var = 10 ** (-0.1 * cfg.channel.snr_db)
    for b in range(cfg.frame.n_blocks):
        st = channel.state(b)
        blk = frames.make(b)
        y_p = channel.transmit(blk.s_pilot, st)
        y_d = channel.transmit(blk.s_data, st)
        if cfg.channel.model == "umi" and cfg.attack.type != "none":   # UMi scene: the attacker's channel and SIR
            G_all, sir_geo, g_rms = channel.umi_attacker(cfg.attack.att_dist)
            st.G = G_all[b]
            if cfg.attack.sir_from_geometry:
                attacker.sir_override, attacker.g_rms = sir_geo, g_rms
        attacker.block_state = st
        attacker.observe_clean(b, y_p, blk.idx_pilot, y_d, frames)
        tb = time.time()
        y_p_adv, y_d_adv, astats = attacker.craft(b, y_p, blk.idx_pilot, y_d, receiver, noise_var,
                                                  idx_d=blk.idx_data, H_true=st.H, framer=frames)
        t_attack = time.time() - tb
        tb = time.time()
        out = receiver.process_block(b, y_p_adv, blk.idx_pilot, y_d_adv, aux={"framer": frames, "state": st})
        t_rx = time.time() - tb
        crc_pass = None
        if frames.framer.enabled:
            crc_pass = frames.framer.check(frames.decided_bits_to_subblocks(out.idx_hat))
        if hasattr(attacker, "feedback"):   # HARQ query attacker (audit B6)
            attacker.feedback(b, crc_pass, astats.get("attacked", False))
        m = block_metrics(out.idx_hat, blk.idx_data, frames.mod, crc_pass)
        m.update({"block": b, "t_rx": t_rx, "t_attack": t_attack, "snr_db": cfg.channel.snr_db,
                  "h_norm": float(np.linalg.norm(st.H))})
        m.update({k: v for k, v in astats.items()})
        m.update({k: v for k, v in out.stats.items() if not isinstance(v, (np.ndarray,))})
        blocks.append(m)
        if cfg.run.save_params and hasattr(receiver, "level_snapshot"):
            # float16 arrays (the precision of the saved file): Python lists took ~8x the memory and,
            # over hundreds of blocks and several parallel runs, pushed the machine into swap
            level_snaps.append({"block": b, "levels": [{k: np.asarray(v, dtype=np.float16) for k, v in receiver.level_snapshot(k).items()}
                                                      for k in range(receiver.K)]})
        if verbose and (b % cfg.run.log_every == 0 or b == cfg.frame.n_blocks - 1):
            extra = ""
            if "gamma" in m:
                extra = f" gamma={m['gamma']:.2f} r={m.get('surprise_ratio', 0):.2f}"
            print(f"[{cfg.run.name} seed={seed}] block {b:4d} ser={m['ser']:.4f} ber={m['ber']:.4f}"
                  f"{' ATT' if m.get('attacked') else '    '}{extra} t_rx={t_rx:.2f}s", flush=True)
        if progress_cb:
            progress_cb(b, m)

    # the attacker owns the window (it is randomised per seed when attack.start_mode=random, audit E3)
    window = tuple(getattr(attacker, "window", (cfg.attack.start_block, cfg.attack.end_block))) \
        if cfg.attack.type != "none" else None
    summary = summarise(blocks, window)
    if window is not None:
        summary["attack_window"] = [int(window[0]), int(window[1])]
    if getattr(attacker, "sir_override", None) is not None:
        summary["sir_geometry_db"] = attacker.sir_override
    if cfg.channel.model == "umi":
        summary["umi_drop"] = getattr(channel, "umi_meta", {})   # t_block of the 38.901 drop file used
    if getattr(cfg.frame, "coding", "crc") == "ldpc":
        summary["ldpc_scrambled"] = bool(getattr(frames.framer, "scrambled", False))
    summary["pretrain_time_s"] = pretrain_time
    summary["pretrain_cached"] = pretrain_cached
    summary["mean_t_rx_s"] = float(np.mean([b["t_rx"] for b in blocks]))
    summary["total_time_s"] = time.time() - t0
    record = {"name": cfg.run.name, "seed": seed, "config": cfg.to_dict(), "config_hash": cfg.hash(),
              "receiver": getattr(receiver, "name", cfg.receiver.type), "summary": summary, "blocks": blocks,
              "device": str(device)}
    if os.environ.get("CITADEL_MACHINE"):   # which machine ran it: a run and its clean twin pair on one machine
        record["machine"] = os.environ["CITADEL_MACHINE"]
    if level_snaps:
        # displacement curves go into the JSON; the raw snapshots into a compressed side file
        K = len(level_snaps[0]["levels"])
        stacks = []
        for k in range(K):
            keys = sorted(level_snaps[0]["levels"][k].keys())
            stacks.append(np.stack([np.concatenate([np.asarray(s["levels"][k][key], dtype=np.float32).ravel()
                                                    for key in keys]) for s in level_snaps]))
        record["self_disp"] = [np.linalg.norm(lv - lv[0], axis=1).tolist() for lv in stacks]
    if save:
        stem = f"{cfg.run.name}_s{seed}_{cfg.hash()}"
        if level_snaps:
            # the snapshots first and atomically, then the record: a record on disk always has complete
            # snapshots (a full disk or a stop while writing them leaves no record, so the run is redone)
            os.makedirs(cfg.run.out_dir, exist_ok=True)
            npz = os.path.join(cfg.run.out_dir, stem + ".levels.npz")
            tmp = npz + ".part"
            try:
                with open(tmp, "wb") as fh:
                    np.savez_compressed(fh, **{f"level{k + 1}": lv.astype(np.float16) for k, lv in enumerate(stacks)})
                os.replace(tmp, npz)
            except BaseException:
                if os.path.exists(tmp):
                    os.remove(tmp)
                raise
        path = save_record(record, cfg.run.out_dir, stem)
        record["path"] = path
        if verbose:
            print(f"saved {path}")
    return record
