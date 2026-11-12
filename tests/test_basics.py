import numpy as np
import torch

from citadel_rx.coding import CRC, CRCFramer
from citadel_rx.config import Config
from citadel_rx.channels import make_channel
from citadel_rx.frames import FrameGenerator
from citadel_rx.modulation import Modulation
from citadel_rx.receivers.deepsic import DeepSICCore
from citadel_rx.receivers.lmmse import ls_channel_estimate, lmmse_soft_symbols


def test_crc_roundtrip_and_detects_errors():
    crc = CRC(8)
    rng = np.random.default_rng(0)
    payload = rng.integers(0, 2, size=(50, 56))
    framed = np.concatenate([payload, crc.compute(payload)], axis=-1)
    assert crc.check(framed).all()
    corrupted = framed.copy()
    corrupted[:, 3] ^= 1
    assert not crc.check(corrupted).any()


def test_crc_pass_rate_theory_matches_simulation():
    framer = CRCFramer(8, 32, 2)
    rng = np.random.default_rng(1)
    payload = rng.integers(0, 2, size=(2000, 1, framer.payload_bits))
    framed = framer.frame(payload)
    p = 0.02
    flips = rng.random(framed.shape) < (1 - (1 - p) ** 0.5)  # ~ symbol error p for 2-bit symbols
    noisy = framed ^ flips.astype(np.int64)
    emp = framer.check(noisy).mean()
    th = CRCFramer.theoretical_pass_rate(p, 32, 8)
    assert abs(emp - th) < 0.05


def test_modulation_roundtrip():
    for name in ("BPSK", "QPSK"):
        m = Modulation(name)
        bits = np.random.default_rng(2).integers(0, 2, size=(3, 40))
        idx = m.bits_to_indices(bits)
        assert (m.indices_to_bits(idx) == bits).all()
        s = m.modulate_indices(idx)
        assert np.allclose(np.abs(s), 1.0)


def test_channel_shapes_and_lmmse_perfect_at_high_snr():
    cfg = Config()
    cfg.channel.snr_db = 40
    ch = make_channel(cfg.channel, True)
    fr = FrameGenerator(cfg)
    st = ch.state(0)
    blk = fr.make(0)
    y_p = ch.transmit(blk.s_pilot, st)
    assert y_p.shape == (fr.n_pilot_symbols, cfg.channel.n_ant)
    H = ls_channel_estimate(y_p, blk.s_pilot, st.noise_var)
    assert np.allclose(H, st.H, atol=0.05)
    y_d = ch.transmit(blk.s_data, st)
    probs = lmmse_soft_symbols(y_d, H, st.noise_var, fr.mod)
    assert (probs.argmax(-1) == blk.idx_data).mean() > 0.999


def test_cost2100_loads():
    cfg = Config()
    cfg.channel.model = "cost2100"
    ch = make_channel(cfg.channel, True)
    H = ch.state(0).H
    assert H.shape == (4, 4)
    assert np.allclose(np.diag(H), 1.0)


def test_deepsic_functional_adapt_reduces_loss():
    cfg = Config()
    core = DeepSICCore(4, 4, 4, True, 3, 64, torch.device("cpu"))
    p = core.init_params(torch.Generator().manual_seed(0))
    ch = make_channel(cfg.channel, True)
    fr = FrameGenerator(cfg)
    st = ch.state(0)
    blk = fr.make(0)
    y = ch.transmit(blk.s_pilot, st)
    yf = torch.tensor(np.concatenate([y.real, y.imag], 1), dtype=torch.float32)
    idx = torch.tensor(blk.idx_pilot)
    l0 = core.detect_loss(p, yf, idx).item()
    p2 = core.functional_adapt(p, yf, idx, lr=0.05, steps=20, create_graph=False)
    l1 = core.detect_loss(p2, yf, idx).item()
    assert l1 < l0


def test_config_yaml_loads_nested_sections():
    import glob
    import os
    from citadel_rx.config import CitadelConfig
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for path in glob.glob(os.path.join(root, "configs", "*.yaml")):
        cfg = Config.from_yaml(path, ["receiver.type=citadel", "attack.sir_db=3"])
        assert isinstance(cfg.citadel, CitadelConfig)
        assert cfg.receiver.type == "citadel" and cfg.attack.sir_db == 3.0


def test_config_override_and_hash():
    cfg = Config()
    h0 = cfg.hash()
    cfg.set("attack.sir_db=5")
    cfg.set("citadel.periods=[1,4,16]")
    assert cfg.attack.sir_db == 5.0 and cfg.citadel.periods == [1, 4, 16]
    assert cfg.hash() != h0
