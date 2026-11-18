"""Phase 4: NaN-safe consolidation, CRC-8 scrambling, verified conditioning, two-sided noise test."""
import numpy as np
import torch

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment
from citadel_rx.frames import FrameGenerator
from citadel_rx.receivers import make_receiver


def _citadel(**ov):
    cfg = Config()
    for o in ["receiver.type=citadel", "citadel.consol_mean=normalized", "run.device=cpu", *[f"{k}={v}" for k, v in ov.items()]]:
        cfg.set(o)
    return make_receiver(cfg, torch.device("cpu"))


def test_consolidation_never_writes_nan_into_the_memory():
    for floor in (0.0, 1e-6):
        rx = _citadel(**{"citadel.gamma_floor": floor})
        full = lambda v: {k: torch.full_like(rx.params[k], v) for k in rx.A}
        rx.levels = [full(0.0), full(1.0), full(1.0)]
        rx.buf = [[(1e-300, full(3.0)), (1e-290, full(3.0))], [], []]   # underflowing verdicts (Phase 3 bug 1)
        rx._consolidate(b=rx.C[1] - 1)
        assert all(bool(torch.isfinite(v).all()) for v in rx.levels[1].values()), floor
        assert all(abs(float(v.flatten()[0]) - 1.0) < 1e-6 for v in rx.levels[1].values()), floor   # unchanged


def test_scrambled_crc_rejects_a_constant_output_and_passes_the_truth():
    plain, scr = Config(), Config()
    for c in (plain, scr):
        c.set("frame.data_bits=4096")
    scr.set("frame.crc_scramble=true")
    fp, fs = FrameGenerator(plain), FrameGenerator(scr)
    const = np.zeros((fp.n_data_symbols, 4), dtype=np.int64)
    assert fp.framer.check(fp.decided_bits_to_subblocks(const)).all()           # the flaw
    # fixed: the descrambled constant output is random-looking, passing at about the CRC-8 false-pass rate 2^-8
    assert fs.framer.check(fs.decided_bits_to_subblocks(const)).mean() < 0.02
    blk = fs.make(0)
    assert fs.framer.check(fs.decided_bits_to_subblocks(blk.idx_data)).all()
    # off: the legacy framing, bit for bit
    a, b = FrameGenerator(plain).make(0), Config()
    b.set("frame.data_bits=4096")
    assert np.array_equal(a.data_bits, FrameGenerator(b).make(0).data_bits)


def _cc(src, extra=()):
    cfg = Config()
    for o in ["channel.fading=complex_gm", "channel.jakes_fd_tb=0.01", "receiver.type=citadel", "receiver.cond=lmmse",
              f"receiver.cond_source={src}", "receiver.pretrain_draws=8", "receiver.pretrain_draw_bits=1000",
              "receiver.pretrain_epochs=60", "citadel.fast_steps=20", "citadel.periods=[1,2,4]", "citadel.gamma_floor=1e-6",
              "citadel.consol_mean=normalized", "citadel.crc_select=true", "frame.crc_scramble=true", "frame.n_blocks=12",
              "frame.data_bits=4096", "attack.type=deny", "attack.sir_db=0", "attack.start_block=6", "attack.end_block=12",
              "run.device=cpu", *extra]:
        cfg.set(o)
    return cfg


def test_verified_conditioning_protects_the_deep_receiver_from_a_spoof():
    torch.set_num_threads(1)
    raw = run_experiment(_cc("raw"), seed=3, save=False, verbose=False)
    ver = run_experiment(_cc("verified"), seed=3, save=False, verbose=False)
    win = lambda r: np.mean([b["ser"] for b in r["blocks"] if b.get("attacked")])
    assert all(b.get("verifier_skip") for b in ver["blocks"] if b.get("attacked"))
    assert win(ver) < 0.5 * win(raw), (win(ver), win(raw))


def test_two_sided_noise_test_rejects_pilots_that_fit_too_well():
    cfg = Config()
    for o in ["receiver.type=model", "receiver.detector=lmmse", "receiver.guard=true", "receiver.guard_two_sided=true",
              "run.device=cpu"]:
        cfg.set(o)
    rx = make_receiver(cfg, torch.device("cpu"))
    assert rx._noise_ok(1.0, 100) and not rx._noise_ok(0.5, 100) and not rx._noise_ok(2.0, 100)
    cfg.receiver.guard_two_sided = False
    assert make_receiver(cfg, torch.device("cpu"))._noise_ok(0.5, 100)
