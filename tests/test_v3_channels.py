"""v3 channel family (complex_gm), receiver front-end impairments and ensemble pre-training."""
import numpy as np
import torch

from citadel_rx.channels import make_channel
from citadel_rx.config import Config
from citadel_rx.eval import run_experiment
from citadel_rx.eval.runner import pretraining_blocks
from citadel_rx.frames import FrameGenerator


def _ch(**kw):
    cfg = Config()
    cfg.channel.fading = "complex_gm"
    for k, v in kw.items():
        setattr(cfg.channel, k, v)
    return cfg, make_channel(cfg.channel, True)


def test_complex_gm_power_correlation_and_seed_dependence():
    # mean power per entry equals the SED profile squared (fast fading, so 4000 blocks are ~independent)
    _, chf = _ch(jakes_fd_tb=0.3, seed=3, rician_k=0.0)
    Hf = np.stack([chf.state(b).H for b in range(4000)])
    np.testing.assert_allclose(np.mean(np.abs(Hf) ** 2, axis=0), chf.H_mean ** 2, rtol=0.1, atol=1e-3)
    cfg, ch = _ch(jakes_fd_tb=0.05, seed=3)
    Hs = np.stack([ch.state(b).H for b in range(4000)])
    assert np.iscomplexobj(Hs)
    # line-of-sight part: |H_los| is the SED profile, its phases are random per seed
    np.testing.assert_allclose(np.abs(ch._los), ch.H_mean)
    # block-to-block correlation of the scattered part is rho = J0(2 pi f_D T_b)
    G = Hs - Hs.mean(axis=0)
    rho_hat = np.real(np.sum(G[1:] * G[:-1].conj()) / np.sum(np.abs(G[:-1]) ** 2))
    assert abs(rho_hat - ch.rho) < 0.02
    _, ch2 = _ch(jakes_fd_tb=0.05, seed=4)
    assert not np.allclose(ch2.state(0).H, make_channel(cfg.channel, True).state(0).H)


def test_frontend_identity_by_default_and_adc_levels():
    cfg, ch = _ch()
    st = ch.state(0)
    y = ch.transmit(np.ones((50, 4), dtype=complex), st)
    assert ch.frontend(y, st) is y
    cfg, ch = _ch(adc_bits=2)
    st = ch.state(0)
    yq = ch.frontend(ch.transmit(np.exp(1j * np.pi / 4) * np.ones((500, 4)), st), st)
    assert len(np.unique(np.round(yq.real, 9))) <= 4 and len(np.unique(np.round(yq.imag, 9))) <= 4


def test_frontend_saturation_and_iq():
    cfg, ch = _ch(pa_sat=0.5)
    st = ch.state(0)
    y = ch.transmit(np.ones((200, 4), dtype=complex) * 3, st)
    rms = np.sqrt(np.mean(np.sum(np.abs(st.H) ** 2, axis=1)) + st.noise_var / 2)
    assert np.abs(ch.frontend(y, st)).max() <= 0.5 * rms + 1e-9
    cfg, ch = _ch(iq_eps=0.1, iq_phi_deg=10.0)
    st = ch.state(0)
    y = ch.transmit(np.ones((10, 4), dtype=complex), st)
    assert not np.allclose(ch.frontend(y, st), y)


def test_ensemble_pretraining_draws_are_disjoint_from_the_test_channel():
    cfg = Config()
    for o in ["channel.fading=complex_gm", "receiver.pretrain_draws=6", "receiver.pretrain_draw_bits=200"]:
        cfg.set(o)
    fr = FrameGenerator(cfg)
    blocks = pretraining_blocks(cfg, fr)
    assert len(blocks) == 6 and blocks[0][0].shape == (100, 4)
    test_H = make_channel(cfg.channel, True).state(0).H
    for d in range(6):
        c = cfg.channel.__class__(**{**cfg.channel.__dict__, "seed": 1_000_000 + d})
        assert not np.allclose(make_channel(c, True).state(0).H, test_H)


def test_impaired_complex_run_end_to_end():
    torch.set_num_threads(1)
    cfg = Config()
    for o in ["channel.fading=complex_gm", "channel.jakes_fd_tb=0.01", "channel.adc_bits=3", "frame.n_blocks=5",
              "frame.data_bits=2048", "receiver.type=citadel", "receiver.pretrain_draws=4", "receiver.pretrain_draw_bits=200",
              "receiver.pretrain_epochs=10", "citadel.fast_steps=10", "citadel.periods=[1,2,4]", "attack.type=a1",
              "attack.start_block=2", "attack.end_block=4", "attack.pgd_steps=2", "run.device=cpu"]:
        cfg.set(o)
    rec = run_experiment(cfg, seed=0, save=False, verbose=False)
    assert len(rec["blocks"]) == 5 and all(0 <= b["ser"] <= 1 for b in rec["blocks"])
    for rx in ("model", "online_deepsic"):
        cfg.receiver.type = rx
        assert 0 <= run_experiment(cfg, seed=0, save=False, verbose=False)["summary"]["ser_mean"] <= 1
