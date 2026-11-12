"""The pre-training cache must not change any result: an uncached run, a cache miss and a cache
hit of the same configuration give identical block records."""
import os

import pytest

from citadel_rx.config import Config
from citadel_rx.eval import run_experiment

TINY = ["frame.n_blocks=5", "frame.data_bits=2000", "frame.pilot_bits=64", "receiver.pretrain_epochs=15",
        "receiver.pretrain_bits=400", "receiver.epochs=10", "receiver.meta_epochs=5", "citadel.fast_steps=10",
        "citadel.periods=[1,2,4]", "attack.type=a1", "attack.start_block=2", "attack.end_block=4", "attack.pgd_steps=2",
        "run.device=cpu"]
KEYS = ("ser", "ber", "bler", "gamma", "eta", "attacked")


def _run(rx, extra, monkeypatch, cache):
    if cache:
        monkeypatch.setenv("CITADEL_PRETRAIN_CACHE", cache)
    else:
        monkeypatch.delenv("CITADEL_PRETRAIN_CACHE", raising=False)
    cfg = Config()
    for o in TINY + [f"receiver.type={rx}"] + extra:
        cfg.set(o)
    rec = run_experiment(cfg, seed=3, save=False, verbose=False)
    return [{k: b.get(k) for k in KEYS} for b in rec["blocks"]], rec["summary"]["pretrain_cached"]


@pytest.mark.parametrize("rx,extra", [("citadel", ["citadel.crc_select=true", "citadel.consol_clip=[8.5,4.5]"]),
                                      ("online_deepsic", []), ("meta_deepsic", []), ("crc_rollback", []),
                                      ("online_select", []), ("ewc_deepsic", [])])
def test_cache_is_exact(rx, extra, monkeypatch, tmp_path):
    ref, c0 = _run(rx, extra, monkeypatch, "")
    miss, c1 = _run(rx, extra, monkeypatch, str(tmp_path))
    hit, c2 = _run(rx, extra, monkeypatch, str(tmp_path))
    assert (c0, c1, c2) == (False, False, True)
    assert os.listdir(tmp_path)
    assert ref == miss == hit
    # the attacked run and its clean twin share the pre-training (attack.* is not in the key)
    clean, c3 = _run(rx, extra + ["attack.type=none"], monkeypatch, str(tmp_path))
    assert c3 is True
    assert clean[:2] == ref[:2]   # blocks before the attack window are identical
