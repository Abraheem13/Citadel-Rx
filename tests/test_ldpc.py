"""NR LDPC framing (second revision campaign, D2): round trip, scrambling, and that a constant
detector output fails the check once the coded bits are scrambled."""
import numpy as np
import pytest

pytest.importorskip("sionna.phy")

from citadel_rx.config import Config  # noqa: E402
from citadel_rx.frames import FrameGenerator  # noqa: E402


def _frames(scramble: bool) -> FrameGenerator:
    cfg = Config.from_yaml("configs/e3_a1_defence.yaml", ["frame.coding=ldpc", f"frame.ldpc_scramble={scramble}", "frame.data_bits=4000"])
    return FrameGenerator(cfg)


@pytest.mark.parametrize("scramble", [False, True])
def test_true_decisions_pass(scramble):
    fr = _frames(scramble)
    blk = fr.make(0)
    assert fr.framer.check(fr.decided_bits_to_subblocks(blk.idx_data)).all()


def test_constant_output_fails_only_with_scrambling():
    const = np.zeros((_frames(False).n_data_symbols, 4), dtype=np.int64)
    plain, scr = _frames(False), _frames(True)
    assert plain.framer.check(plain.decided_bits_to_subblocks(const)).all()        # the flaw
    assert not scr.framer.check(scr.decided_bits_to_subblocks(const)).any()        # fixed


def test_reencoded_codewords_are_the_sent_symbols():
    fr = _frames(True)
    blk = fr.make(0)
    ok, cw = fr.framer.decode(fr.decided_bits_to_subblocks(blk.idx_data))
    bits = fr.framer.scramble(cw.transpose(1, 0, 2).reshape(4, -1))
    assert ok.all() and np.array_equal(fr.mod.bits_to_indices(bits).T, blk.idx_data)


def test_crc_framing_unchanged():
    cfg = Config.from_yaml("configs/e3_a1_defence.yaml", ["frame.data_bits=4000"])
    fr = FrameGenerator(cfg)
    assert not hasattr(fr.framer, "scramble")
