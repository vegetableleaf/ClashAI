"""Verifier probe: candidate run_screen with --predict-drops; logs observed SB/skeleton bodies, pending drops, and
the enemy unit classes of every decision board (from_engine output), one JSON line per decision."""
import json, os, sys
ROOT = os.path.abspath(sys.argv[1]); LOG = sys.argv[2]; rest = sys.argv[3:]
sys.path.insert(0, ROOT)
try:
    import ctypes; assert ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import pipeline.extrapolate as X, pipeline.e1_eval as E
from pipeline import vocab
fh = open(LOG, "w")
cur = {}
_obs = X.DropTracker.observe
def observe(self, obs, my_side):
    sk = [dict(n=e.get("name"), c=e.get("card_id"), mh=e.get("max_hp"), hp=e.get("hp"), s=e.get("side"), k=e.get("kind"),
               id=e.get("entity_id"), x=round(e["x"]), y=round(e["y"]))
          for e in obs.get("entities", ()) if "keleton" in str(e.get("name")) or int(e.get("card_id", -1)) in X.SB_CARDS]
    _obs(self, obs, my_side)
    cur.clear(); cur.update(tick=int(obs.get("tick", obs.get("game_tick"))), my=my_side, sb=sk,
                            pending=[(d["t0"], round(d["x"]), round(d["y"]), d["parent"].get("max_hp")) for d in self.pending])
X.DropTracker.observe = observe
_fe = E.from_engine
def from_engine(raw, side, *a, **k):
    bs = _fe(raw, side, *a, **k)
    if cur:
        en = {}
        for u in bs.units:
            if u.side != 0:
                nm = vocab.UNIT_VOCAB[u.cls] if isinstance(vocab.UNIT_VOCAB, (list, tuple)) else u.cls
                en[str(nm)] = en.get(str(nm), 0) + 1
        fh.write(json.dumps(dict(cur, view_tick=raw.get("tick"), enemy=en,
                                 pred=sum(str(e.get("entity_id")).startswith("predicted") for e in raw.get("entities", ())))) + "\n")
        fh.flush(); cur.clear()
    return bs
E.from_engine = from_engine
import importlib.util
spec = importlib.util.spec_from_file_location("rs", os.path.join(ROOT, "scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py"))
rs = importlib.util.module_from_spec(spec); spec.loader.exec_module(rs)
rs.main(rest)
