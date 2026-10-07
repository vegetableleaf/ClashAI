"""pipeline.branch_score: score kinds, labels, the phi mapping (fake model), and that no elixir term exists."""
import inspect
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from pipeline import branch_score as B
from pipeline import e1_eval as E


def test_outcome_wins_over_every_kind():
    snap = {"towers": -0.4, "phi": 0.7}
    for kind in B.KINDS:
        assert B.score(snap, 1, kind=kind) == 1.0
        assert B.score(snap, -1, kind=kind) == -1.0
        assert B.score(snap, 0, kind=kind) == 0.0


def test_horizon_scores_read_the_snapshot():
    snap = {"towers": -0.4, "phi": 0.7}
    assert B.score(snap, None, kind="towers") == -0.4
    assert B.score(snap, None, kind="phi") == 0.7
    with pytest.raises(ValueError):
        B.score(snap, None, kind="outcome")          # horizon reached: no outcome to score
    with pytest.raises(ValueError):
        B.score({"towers": 0.1, "phi": None}, None, kind="phi")
    with pytest.raises(ValueError):
        B.score(snap, None, kind="elixir")
    with pytest.raises(ValueError):
        B.score(snap, 2, kind="outcome")
    with pytest.raises(TypeError):
        B.score(object(), None, kind="towers")


def test_no_elixir_charge():
    # S0's scorer subtracted spent elixir; this one has no such input and ignores any extra snapshot field
    for f in (B.score, B.branch_label, B.label_from_scores):
        assert not any("spent" in p or "elixir" in p for p in inspect.signature(f).parameters)
    assert B.score({"towers": 0.2, "phi": 0.1, "spent": 9.0}, None, kind="towers") == 0.2


def test_label_math():
    assert B.label_from_scores([1, 1, 1, 1], [-1, -1, -1, -1]) == (2.0, 1.0)      # se 0 -> full weight
    assert B.label_from_scores([1, -1], [1, -1]) == (0.0, 0.0)
    assert B.label_from_scores([0.5], [0.25]) == (0.25, 1.0)                     # k 1
    d, w = B.label_from_scores([1, -1, 1, 1], [-1, -1, -1, 1])                    # diffs 2, 0, 2, 0
    se2 = np.var([2, 0, 2, 0], ddof=1) / 4
    assert d == 1.0 and w == pytest.approx(1.0 / (1.0 + se2))


def test_branch_label_pairs_and_mixes_ended_and_horizon():
    r = SimpleNamespace(play_end=[{"towers": 0.3, "phi": 0.2}, {"towers": 0.0, "phi": 0.0}],
                        hold_end=[{"towers": 0.1, "phi": -0.2}, {"towers": 0.0, "phi": 0.0}],
                        play_outcome=[None, 1], hold_outcome=[None, -1])
    d, _ = B.branch_label(r, "phi")
    assert d == pytest.approx(((0.2 + 0.2) + 2.0) / 2)
    d, _ = B.branch_label(r, "towers")
    assert d == pytest.approx((0.2 + 2.0) / 2)
    with pytest.raises(ValueError):
        B.branch_label(r, "outcome")
    r.hold_outcome = [None]
    with pytest.raises(ValueError):
        B.branch_label(r, "phi")


class _FakeGen(torch.nn.Module):
    feature_version = 1

    def __init__(self, logits):
        super().__init__()
        self.w = torch.nn.Parameter(torch.zeros(1))
        self.logits = torch.tensor(logits, dtype=torch.float32)

    def encode_gen(self, b):
        return {"g": torch.zeros(b["tok"].shape[0], 1)}

    def value_head(self, g):
        return self.logits.expand(g.shape[0], 7)


def test_phi_is_pwin_minus_ploss():
    # classes = clip(crowns mine - theirs, -3, 3) + 3: 0..2 loss, 3 draw, 4..6 win
    logits = np.log([0.05, 0.05, 0.1, 0.2, 0.3, 0.2, 0.1])
    phi = SimpleNamespace(model=_FakeGen(logits))
    rows = [{k: np.zeros(2, np.float32) for k in E.gen_row_keys(phi.model)} for _ in range(3)]
    v = B.phi_values(phi, rows)
    assert v.shape == (3,) and np.allclose(v, 0.6 - 0.2)
    assert B.phi_values(phi, []).shape == (0,)


def test_outcome_value():
    assert [B.outcome_value(w) for w in ("win", "loss", "draw")] == [1, -1, 0]


def test_branchrunner_snapshot_format(monkeypatch):
    # T1's end snapshot: {"tick", "side", "terminated", "state", "raw", "learner" (prepared side, env None)}
    logits = np.log([0.05, 0.05, 0.1, 0.2, 0.3, 0.2, 0.1])
    phi = SimpleNamespace(model=_FakeGen(logits))
    row = {k: np.zeros(2, np.float32) for k in E.gen_row_keys(phi.model)}
    learner = SimpleNamespace(gen_row=lambda pol: row)
    monkeypatch.setattr(B, "tower_frac_diff", lambda st, us: 0.25 if (st, us) == ("ST", 1) else None)
    snap = {"tick": 900, "side": 1, "terminated": False, "state": "ST", "raw": {}, "learner": learner}
    assert B.score(snap, None, kind="phi", phi=phi) == pytest.approx(0.4)
    assert B.score(snap, None, kind="towers") == 0.25
    assert B.score(snap, -1, kind="phi", phi=phi) == -1.0
