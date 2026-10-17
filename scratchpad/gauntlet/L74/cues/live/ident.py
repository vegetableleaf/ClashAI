"""Byte-identity proof: the deployed live model (u250, no cue layer) + the deployed LIVE_OPTIONS on recorded merged-reader
frames (WITH cue blocks): HEAD's live_gen / live_gen_v2 vs the working tree with the flag off (no builder) and with the
builder attached (what --cue-inputs on would do if it attached to a model without the layer, which load_pilot does not).
Every decision dict (repr, incl. the BoardState and the public audit snapshot) must be equal.

    python ident.py LOG.jsonl [LOG ...]
"""
import copy
import ctypes
import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path

ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO), str(HERE)]
import torch                                                 # noqa: E402
torch.set_num_threads(1)
from logframes import full_frames                            # noqa: E402
from pipeline import live_gen_v2                             # noqa: E402
from pipeline.live_unit_state import LiveCues                # noqa: E402
from pipeline.tests.test_posture_live import _deployed_options   # noqa: E402

CK = REPO / "icebow/data/bench/rl_royale/rlarm_gae/rlarm_gae_u0250_grafted.pt"


def head(rel, name, sub=None):
    src = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout
    for a, b in (sub or {}).items():
        assert src.count(a) == 1, a
        src = src.replace(a, b)
    p = HERE / f"_{name}.py"
    p.write_text(src, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"pipeline.{name}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[f"pipeline.{name}"] = m
    spec.loader.exec_module(m)
    return m


head("pipeline/live_gen.py", "_live_gen_head")
H = head("pipeline/live_gen_v2.py", "_live_gen_v2_head",
         {"from .live_gen import GenPilot as LegacyGenPilot, FORM_PAD": "from ._live_gen_head import GenPilot as LegacyGenPilot, FORM_PAD"})
kw = dict(device="cpu", gate_tau=.35, extrapolate_ticks=24, own_effects=True, hero_ability_spec="supplement",
          decision_options=_deployed_options(), decision_seed=0, public_audit=True)
pilots = dict(head=H.GenPilot(str(CK), **kw), off=live_gen_v2.GenPilot(str(CK), **kw), on=live_gen_v2.GenPilot(str(CK), **kw))
pilots["on"].cues = LiveCues()
for q in pilots.values():
    q.legal_guard, q.identity_ext, q.afford_ticks = True, True, 23
n, digest, plays = 0, hashlib.sha256(), 0
for log in sys.argv[1:]:
    for q in pilots.values():
        q.reset_match()
    for i, f in enumerate(full_frames(log)):
        for q in pilots.values():
            q.observe(copy.deepcopy(f))
        if f["game_tick"] < 150 or i % 4:
            continue
        out = {k: repr(q.decide(copy.deepcopy(f))) for k, q in pilots.items()}
        assert out["head"] == out["off"] == out["on"], (log, f["game_tick"])
        digest.update(out["head"].encode())
        n += 1
        plays += "'play': True" in out["head"]
    print(Path(log).name, n, flush=True)
for leftover in HERE.glob("_live_gen*_head.py"):
    leftover.unlink()
print("IDENTICAL decisions:", n, "(plays %d)" % plays, "digest", digest.hexdigest())
