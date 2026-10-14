import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import tempfile
import uuid

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2] / "drills")]


@pytest.fixture
def tmp_path():
    # Python 3.13's Windows mkdir(0700) excludes the sandbox's restricted token.
    # These uniquely named test artifacts use inherited ACLs, never shared temp dirs.
    path = Path(tempfile.gettempdir()) / ("cb_xl2_" + uuid.uuid4().hex)
    path.mkdir()
    return path


@pytest.fixture
def selectors(tmp_path, monkeypatch):
    # Minimal catalogue for selector unit tests; no engine, corpus or icebow/data.
    path = tmp_path / "research/ext/Royale/RoyaleSim/data/derived/cards.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"cards": [{"name": "Rocket", "damage": 1000, "projectile": {"aoe_to_air": True}},
                                          {"name": "Tesla", "attacks_air": True}, {"name": "IceWizard", "attacks_air": True}], "units": {}}))
    monkeypatch.setenv("CB_MAIN", str(tmp_path) + "/")
    sys.modules.pop("drills", None)
    return importlib.import_module("drills")


@pytest.fixture
def side():
    class Model:
        def cell_logits(self, enc, slot):
            # Strongest cell is deliberately unsuitable for most test boards.
            return torch.arange(2304, dtype=torch.float32)[None]
    s = NS(deck=NS(cards=["tornado", "tesla_evo", "ice_wizard", "x_bow", "rocket", "knight_evo", "the_log", "skeletons"]),
           model=Model(), costs=[3, 4, 3, 6, 6, 3, 2, 1], cfg={"grid": "floor"}, pending=None, side=0)
    bs = NS(units=[], towers=[NS(alive=True, hp_frac=1.0) for _ in range(6)], t_sec=150.0, my_elixir=10)
    ctx = dict(enc={}, heads={"card": torch.tensor([[0., 2., 3., 4., 5., 6., 7., 8.]])}, allowed=np.ones(8, bool),
               hand=np.ones(8, bool), tick=3000, bs=bs, d={"play": True, "slot": 7, "cell": 123, "why": "model", "follow_ups": ["kept"]})
    s._cur = (3000, bs)
    s.state = {"episode": {"crown_towers": [dict(side=1, type="princess", hp=1000, x=3500, y=25500),
                                             dict(side=1, type="princess", hp=2000, x=14500, y=25500)]}}
    return s, ctx


def body(name, x, y, side=1):
    from pipeline import vocab
    return NS(cls=vocab.unit_id(name), x=x / 18, y=1 - y / 32, side=side, hp_frac=1.)
