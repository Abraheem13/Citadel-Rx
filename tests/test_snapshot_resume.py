"""A run that saves level snapshots writes them before its record, and a damaged snapshot file
(e.g. written while the disk was full) makes the run count as unfinished, so it is redone."""
import copy
import json
import os
import sys

import numpy as np

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
from run_experiment import find_existing  # noqa: E402

TINY = ["frame.n_blocks=4", "frame.data_bits=2000", "frame.pilot_bits=64", "receiver.pretrain_epochs=10",
        "receiver.pretrain_bits=400", "citadel.fast_steps=5", "citadel.periods=[1,2,4]", "attack.type=none",
        "run.device=cpu", "run.save_params=true", "run.name=snap"]


def test_snapshots_saved_with_record_and_damage_detected(tmp_path, monkeypatch):
    monkeypatch.delenv("CITADEL_PRETRAIN_CACHE", raising=False)
    cfg = Config()
    for o in TINY + [f"run.out_dir={tmp_path}"]:
        cfg.set(o)
    probe = copy.deepcopy(cfg)   # as scripts/run_experiment.py identifies a run: settings + seed
    probe.channel.seed = 1
    rec = run_experiment(cfg, seed=1, save=True, verbose=False)
    path = rec["path"]
    npz = path.replace(".json", ".levels.npz")
    assert os.path.exists(path) and os.path.exists(npz)
    assert not [f for f in os.listdir(tmp_path) if f.endswith(".part")]
    with np.load(npz) as z:
        assert z["level1"].shape[0] == 4
    assert json.load(open(path))["seed"] == 1
    # an intact pair counts as finished
    assert find_existing(str(tmp_path), "snap", 1, probe) == path
    # a damaged snapshot file: the run is unfinished and the useless file is removed
    with open(npz, "r+b") as fh:
        fh.seek(200)
        fh.write(b"\0" * 64)
    assert find_existing(str(tmp_path), "snap", 1, probe) == ""
    assert not os.path.exists(npz)


def test_snapshot_file_missing_a_level_is_unfinished(tmp_path, monkeypatch):
    """A write cut short at close can leave a readable file with only some of the levels."""
    monkeypatch.delenv("CITADEL_PRETRAIN_CACHE", raising=False)
    cfg = Config()
    for o in TINY + [f"run.out_dir={tmp_path}"]:
        cfg.set(o)
    probe = copy.deepcopy(cfg)
    probe.channel.seed = 2
    rec = run_experiment(cfg, seed=2, save=True, verbose=False)
    npz = rec["path"].replace(".json", ".levels.npz")
    with np.load(npz) as z:
        first = z["level1"]
    np.savez_compressed(npz, level1=first)   # level2 and level3 lost
    assert find_existing(str(tmp_path), "snap", 2, probe) == ""
    assert not os.path.exists(npz)

