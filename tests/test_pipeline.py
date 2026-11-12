"""End-to-end smoke tests on tiny settings (seconds on CPU)."""
import pytest

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment


def tiny(receiver: str, attack: str = "none", **kw) -> Config:
    cfg = Config()
    cfg.run.name = f"test_{receiver}_{attack}"
    cfg.run.out_dir = "/tmp/citadel_test_results"
    cfg.frame.n_blocks = 6
    cfg.frame.data_bits = 2048
    cfg.receiver.type = receiver
    cfg.receiver.epochs = 10
    cfg.receiver.pretrain_epochs = 10
    cfg.receiver.meta_epochs = 5
    cfg.receiver.meta_every = 2
    cfg.citadel.fast_steps = 10
    cfg.citadel.periods = [1, 2, 4]
    cfg.attack.type = attack
    cfg.attack.pgd_steps = 2
    cfg.attack.start_block = 2
    cfg.attack.end_block = 4
    for k, v in kw.items():
        cfg.set(f"{k}={v}")
    return cfg


@pytest.mark.parametrize("rx", ["lmmse", "online_deepsic", "meta_deepsic", "drift_deepsic",
                                "medbn_deepsic", "titans_single", "citadel"])
def test_receivers_run(rx):
    rec = run_experiment(tiny(rx), save=False, verbose=False)
    assert len(rec["blocks"]) == 6
    assert 0 <= rec["summary"]["ser_mean"] <= 1


@pytest.mark.parametrize("atk", ["a1", "a2", "a3", "adaptive", "data_jam"])
def test_attacks_run_against_citadel(atk):
    rec = run_experiment(tiny("citadel", atk), save=False, verbose=False)
    attacked = [b for b in rec["blocks"] if b.get("attacked")]
    assert len(attacked) == 2


def test_transfer_attack():
    rec = run_experiment(tiny("online_deepsic", "a1", **{"attack.knowledge": "transfer"}), save=False, verbose=False)
    assert any(b.get("attacked") for b in rec["blocks"])


def test_nonlinear_and_cost2100_and_jakes():
    cfg = tiny("citadel")
    cfg.channel.linear = False
    cfg.channel.model = "cost2100"
    run_experiment(cfg, save=False, verbose=False)
    cfg = tiny("citadel")
    cfg.channel.fading = "jakes"
    run_experiment(cfg, save=False, verbose=False)
