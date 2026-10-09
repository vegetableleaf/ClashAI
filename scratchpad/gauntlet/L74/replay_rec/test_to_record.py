"""Dataset bridge tests: recording -> to_record -> pipeline.dataset_gen.replay_rows (feature_version 4). L74.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/test_to_record.py

Runs on the synthetic battle of test_replay_rec.py and, when present, the 2026-10-08 device recording
(icebow/data/replay_rec/rec_20261008_210824.jsonl, git-ignored).
Public-only check: scramble ONE side's private fields (its hand / next / elixir in play_frames, log hand_before,
frame elixir) and require the OTHER side's rows to be byte-identical.
"""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import test_replay_rec as syn  # noqa: E402
import to_record as tr  # noqa: E402
from pipeline.dataset_gen import replay_rows  # noqa: E402

DEVICE_REC = Path("C:/Users/benpe/ClashBot/icebow/data/replay_rec/rec_20261008_210824.jsonl")
FV = 4


def rows(rec: dict) -> dict:
    p = Path(tempfile.mkdtemp()) / f"replay_{rec['tag']}.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    r = replay_rows(str(p), feature_version=FV)
    assert "error" not in r, r.get("error")
    return r


def scramble(rec: dict, side: int) -> dict:
    out = copy.deepcopy(rec)
    names = [n.split("@")[0] for n in rec["final_decks"][str(side)]]
    for e in out["log"]:
        if e["side"] == side:
            e["hand_before"] = list(reversed(e["hand_before"]))
    for pf in out["play_frames"]:
        for p in pf["players"]:
            if p["side"] == side:
                p.update(hand=[names[0]] * 4, next=0, elixir=0.0, hand_pos=[0] * 4)
    for f in out["frames"] + out["play_frames"]:
        f["elixir"][side] = 9.99
    return out


def check(rec: dict) -> dict:
    r = rows(rec)
    side, gate = r["side"], r["y_gate"]
    n_play = {s: int(((side == s) & (gate == 1)).sum()) for s in (0, 1)}
    accepted = {s: sum(e["accepted"] for e in rec["log"] if e["side"] == s) for s in (0, 1)}
    assert n_play == accepted, (n_play, accepted)                  # every positioned play became a PLAY row
    assert all(((side == s) & (gate == 0)).sum() > 0 for s in (0, 1))
    play = gate == 1
    assert (r["y_hand_pos"][play] >= 0).all()                      # the played card was in that side's own hand
    assert (r["y_card"][play] >= 0).all() and ((r["y_xy"][play] >= 0) & (r["y_xy"][play] <= 1)).all()
    for s in (0, 1):                                               # public-only: the other side cannot move my rows
        a, b = r, rows(scramble(rec, 1 - s))
        m = a["side"] == s
        assert (b["side"] == s).sum() == m.sum()
        for k, v in a.items():
            if isinstance(v, np.ndarray) and len(v) == len(side) and k != "n_tok":
                assert np.array_equal(v[m], b[k][b["side"] == s]), (s, k)
        o = b["side"] == 1 - s                                     # ...while the scramble did reach its own rows
        assert not np.array_equal(a["hand_card"][a["side"] == 1 - s], b["hand_card"][o])
    return dict(rows=len(side), play=n_play, wait={s: int(((side == s) & (gate == 0)).sum()) for s in (0, 1)})


def test_synthetic_bridge():
    out, _ = syn.record(syn.battle())
    check(tr.to_record(out, tag="SYNTH2"))


def test_device_recording_bridge():
    if not DEVICE_REC.exists():
        print("SKIP device recording not present")
        return
    print(check(tr.to_record(DEVICE_REC)))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
