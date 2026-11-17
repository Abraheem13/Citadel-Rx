"""v3 channel-conditioned DeepSIC (receivers/conditioning.py) and the attacker's path through it."""
import numpy as np
import torch

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment
from citadel_rx.receivers.conditioning import cond_features_np, cond_features_torch, ls_np, ls_torch


def test_numpy_and_torch_features_agree():
    rng = np.random.default_rng(0)
    N, U, n = 4, 4, 100
    S = (rng.choice([-1, 1], (n, U)) + 1j * rng.choice([-1, 1], (n, U))) / np.sqrt(2)
    H0 = (rng.standard_normal((N, U)) + 1j * rng.standard_normal((N, U))) / np.sqrt(2)
    Y = S @ H0.T + 0.1 * (rng.standard_normal((n, N)) + 1j * rng.standard_normal((n, N)))
    H, nv = ls_np(Y, S, 0.1)
    yf = torch.tensor(np.concatenate([Y.real, Y.imag], 1), dtype=torch.float64)
    Ht, nvt = ls_torch(yf, S, 0.1)
    np.testing.assert_allclose(Ht.numpy(), H, atol=1e-10)
    np.testing.assert_allclose(cond_features_torch(yf.float(), Ht, nvt).numpy(), cond_features_np(Y, H, nv), atol=1e-4)


def test_attack_gradient_reaches_the_conditioning():
    rng = np.random.default_rng(1)
    S = (rng.choice([-1, 1], (50, 4)) + 1j * rng.choice([-1, 1], (50, 4))) / np.sqrt(2)
    yf = torch.tensor(rng.standard_normal((50, 8)), dtype=torch.float32, requires_grad=True)
    Ht, nvt = ls_torch(yf, S, 0.1)
    q = torch.tensor(rng.standard_normal((20, 8)), dtype=torch.float32)       # clean query symbols
    out = cond_features_torch(q, Ht, nvt)[:, 8:].pow(2).sum()                  # only the conditioning part
    out.backward()
    assert yf.grad is not None and float(yf.grad.abs().sum()) > 0


def _cfg(rx, cond, extra=()):
    cfg = Config()
    for o in ["channel.fading=complex_gm", "channel.jakes_fd_tb=0.01", f"receiver.type={rx}", f"receiver.cond={cond}",
              "receiver.pretrain_draws=16", "receiver.pretrain_draw_bits=1000", "receiver.pretrain_epochs=150",
              "receiver.lr=0.005", "frame.n_blocks=3", "frame.data_bits=4000", "run.device=cpu", *extra]:
        cfg.set(o)
    return cfg


def test_conditioned_pretraining_works_on_an_unseen_channel():
    torch.set_num_threads(1)
    frozen = ["receiver.epochs=0"]
    plain = run_experiment(_cfg("online_deepsic", "none", frozen), seed=7, save=False, verbose=False)
    cond = run_experiment(_cfg("online_deepsic", "lmmse", frozen), seed=7, save=False, verbose=False)
    s_plain = np.mean([b["ser"] for b in plain["blocks"]])
    s_cond = np.mean([b["ser"] for b in cond["blocks"]])
    assert s_plain > 0.5 and s_cond < 0.25, (s_plain, s_cond)


def test_attacked_conditioned_citadel_runs_end_to_end():
    torch.set_num_threads(1)
    cfg = _cfg("citadel", "lmmse", ["citadel.fast_steps=10", "citadel.periods=[1,2,4]", "attack.type=a1",
                                    "attack.start_block=1", "attack.end_block=3", "attack.pgd_steps=2",
                                    "receiver.pretrain_epochs=20"])
    rec = run_experiment(cfg, seed=0, save=False, verbose=False)
    att = [b for b in rec["blocks"] if b.get("attacked")]
    assert len(att) == 2 and all(b["e_norm"] > 0 for b in att)
    # soft-gate path through the conditioning: it runs and evaluates its objective (it may keep E = 0, its best
    # iterate, when every perturbation it finds lowers the predicted acceptance more than it raises the loss)
    cfg.attack.soft_gate, cfg.attack.unroll_steps = True, 2
    rec = run_experiment(cfg, seed=0, save=False, verbose=False)
    att = [b for b in rec["blocks"] if b.get("attacked")]
    assert len(att) == 2 and all(np.isfinite(b["obj"]) and b["eps"] > 0 for b in att)
