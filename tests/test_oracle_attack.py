"""The exact-gate attacker predicts, on its copy of the receiver, exactly what the receiver then does."""
import glob
import json
import os

import pytest
import torch

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("mode", ["max_ser", "accepted"])
def test_oracle_prediction_is_exact(mode):
    fs = sorted(glob.glob(os.path.join(ROOT, "results", "rev_p3_adaptive_g1fix", "p3_citadel_softgate__sir0_s10_*.json")))
    if not fs:
        pytest.skip("no record to take the settings from")
    torch.set_num_threads(1)
    cfg = Config.from_dict(json.load(open(fs[0]))["config"])
    cfg.frame.n_blocks, cfg.frame.data_bits = 9, 8000
    cfg.attack.start_mode, cfg.attack.start_block, cfg.attack.end_block = "fixed", 6, 8
    cfg.receiver.pretrain_epochs, cfg.receiver.pretrain_bits = 20, 2000
    cfg.citadel.fast_steps, cfg.attack.pgd_steps, cfg.attack.unroll_steps = 30, 3, 2
    cfg.attack.oracle_scales, cfg.attack.oracle_mode = [1.0, 0.25, 0.05], mode
    rec = run_experiment(cfg, seed=10, save=False, verbose=False)
    att = [b for b in rec["blocks"] if b.get("attacked")]
    assert att
    for b in att:
        assert b["oracle_gamma"] == b["gamma"] and abs(b["oracle_ser"] - b["ser"]) < 1e-12
        if mode == "accepted" and b["oracle_n_accepted"] > 0:
            assert b["gamma"] >= 0.5
