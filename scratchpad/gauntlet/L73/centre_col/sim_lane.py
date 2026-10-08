"""``pipeline.search_s0`` unchanged, plus a per-play log of the LEARNER's placements and the enemy bodies it saw, for
the centre-column lane-consistency metric in the SIM (same definition as spell_audit/h2_cmp.py: defensive Knight /
IceWizard / Skeletons / Tesla plays in the own half (Y < 15) on X 8.5 / 9.5 while the nearest enemy body is in a lane,
|eX - 9| >= 1; share on the enemy's side of centre). Model frame, tiles: X = cell % 36 / 2, Y = 32 - cell // 36 / 2.
    CENTRE_LOG_DIR=DIR python sim_lane.py <search_s0 args>        (writes DIR/lane_<pid>.jsonl)
    python sim_lane.py --summarise DIR [DIR ...]
The patch is module-level so spawn workers (which re-import this file as __mp_main__) carry it too. The learner is
the first GenPolicy a process loads (search_s0._init_worker loads --gen before --opp-gen)."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from pipeline import e1_eval as E

_orig_load, _orig_fwd, _orig_dec = E.load_policy, E.GenPolicy.forward_batch, E.live_decide_batch
_S = {"learner": None, "row": None, "fh": None}
H2 = {"knight", "ice-wizard", "skeletons", "tesla"}


def _load(*a, **k):
    m, info = _orig_load(*a, **k)
    if _S["learner"] is None and isinstance(m, E.GenPolicy):
        _S["learner"] = m
        m._vocab = {v: k for k, v in m.gid.items()}
    return m, info


def _fwd(self, rows, device="cpu"):
    if self is _S["learner"]:
        _S["row"] = rows[0]
    return _orig_fwd(self, rows, device)


def _dec(model, enc, *a, **k):
    out = _orig_dec(model, enc, *a, **k)
    if model is _S["learner"] and _S["row"] is not None and out and out[0]["play"]:
        r = _S["row"]
        tok = r["tok"][r["mask"].astype(bool)]
        en = tok[(tok[:, 2] == 1) & (tok[:, 13] == 0)]
        if _S["fh"] is None:
            d = Path(os.environ.get("CENTRE_LOG_DIR", "."))
            d.mkdir(parents=True, exist_ok=True)
            _S["fh"] = open(d / f"lane_{os.getpid()}.jsonl", "a")
        _S["fh"].write(json.dumps({"card": model._vocab[int(r["slot_card"][out[0]["slot"]])], "cell": out[0]["cell"],
                                   "enemy": [[round(float(t[4]) * 18, 3), round((1 - float(t[5])) * 32, 3)] for t in en]}) + "\n")
        _S["fh"].flush()
        _S["row"] = None
    return out


E.load_policy, E.GenPolicy.forward_batch, E.live_decide_batch = _load, _fwd, _dec


def summarise(dirs):
    for d in dirs:
        c = {"plays": 0, "h2_def": 0, "centre": 0, "enemy_side": 0}
        for fn in Path(d).glob("lane_*.jsonl"):
            for l in open(fn):
                e = json.loads(l)
                c["plays"] += 1
                X, Y = e["cell"] % 36 / 2, 32 - e["cell"] // 36 / 2
                if e["card"] not in H2 or Y >= 15 or not e["enemy"]:
                    continue
                c["h2_def"] += 1
                ex, ey = min(e["enemy"], key=lambda b: (b[0] - X) ** 2 + (b[1] - Y) ** 2)
                if X in (8.5, 9.5) and abs(ex - 9) >= 1:
                    c["centre"] += 1
                    c["enemy_side"] += (X - 9) * (ex - 9) > 0
        print(d, json.dumps(c), f"lane consistency {100 * c['enemy_side'] / max(c['centre'], 1):.1f}%")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--summarise"]:
        summarise(sys.argv[2:])
    else:
        from pipeline import search_s0
        raise SystemExit(search_s0.main(sys.argv[1:]))
