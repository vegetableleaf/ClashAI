"""Tests for tv_nav.py / harvest.py with synthetic screens, frames and fakes. No device. L74 replay_rec.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/test_harvest.py
"""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harvest as hv  # noqa: E402
import test_replay_rec as syn  # noqa: E402
import tv_nav  # noqa: E402

MAN = {n: {"region": (0, 0, 900, 1400)} for n in tv_nav.TAP_TEMPLATES}
hv.MIN_PLAYS = 3                                    # the synthetic battle has 3-4 plays a side
SCREENS = Path("C:/Users/benpe/ClashBot/icebow/data/replay_rec/screens")


def tmp() -> Path:
    return Path(tempfile.mkdtemp())


def test_process_accept_dedupe_reject():
    out = tmp()
    rec, _ = syn.record(syn.battle())
    row = hv.process(rec, out, "ultimate_champion", 0)
    assert row["verdict"] == "accepted", row["reasons"]
    assert (out / "crawl" / "battles.csv").exists() and (out / "corpus" / f"replay_{row['tag']}.json").exists()
    rec2, _ = syn.record(syn.battle())                         # the same replay recorded again
    row2 = hv.process(rec2, out, "ultimate_champion", 0)
    assert row2["verdict"] == "rejected" and row2["reasons"] == [f"duplicate_of:{row['tag']}"], row2["reasons"]
    late, _ = syn.record([f for f in syn.battle() if f["game_tick"] >= 330])
    assert any(r.startswith("started_late") for r in hv.process(late, out, None)["reasons"])
    mine, _ = syn.record(syn.battle(visible=(1,)))
    assert "PLAYED" in hv.process(mine, out, None)["reasons"][0]
    rows = [json.loads(line) for line in open(out / "manifest.jsonl", encoding="utf-8")]
    assert [r["verdict"] for r in rows] == ["accepted", "rejected", "rejected", "rejected"]
    assert sum(1 for _ in open(out / "crawl" / "battles.csv", encoding="utf-8")) == 2      # header + 1 replay


def test_same_replay_tolerates_sample_jitter():
    a = {"decks": [["a"], ["b"]], "plays": [["red", "x", 100], ["blue", "y", 200], ["red", "z", 300]]}
    b = {"decks": [["a"], ["b"]], "plays": [["red", "x", 108], ["blue", "y", 192], ["red", "z", 316]]}
    assert hv.same_replay(a, b)
    assert not hv.same_replay(a, {**b, "plays": [["red", "x", 500], ["blue", "q", 200], ["red", "z", 900]]})
    assert not hv.same_replay(a, {**b, "decks": [["a"], ["c"]]})


def scr(screen, **k):
    return {"screen": screen, **k}


def test_decide_full_cycle_and_allowlist():
    st, t = {}, 0.0
    R = dict(in_replay=False, ended=None, ticks_per_s=None, recording=False)
    steps = [
        (scr("main", hits={"tv_entry": (450, 300)}), R, ("tap", "tv_entry")),
        (scr("tv_list", hits={"tv_channel_btn": (450, 200)}, rows=[]), R, ("tap", "tv_channel_btn")),
        (scr("tv_channels", hits={"tvch_ultimate_champion": (450, 400)}), R, ("tap", "tvch_ultimate_champion")),
        (scr("tv_list", hits={}, rows=[(800, 500), (800, 700)]), R, ("start_record",)),
        (scr("tv_list", hits={}, rows=[(800, 500)]), {**R, "recording": True}, ("tap", "tv_row_play")),
        (scr("unknown"), {**R, "recording": True}, ("wait", "replay_loading")),
        (scr("unknown"), {**R, "recording": True, "in_replay": True, "ticks_per_s": 20}, ("tap", "rp_show")),
        (scr("replay_controls", speed="x1"), {**R, "recording": True, "in_replay": True, "ticks_per_s": 20},
         ("tap", "rp_speed")),
        (scr("replay_controls", speed="x4"), {**R, "recording": True, "in_replay": True, "ticks_per_s": 25},
         ("wait", "speed_x4_label")),
        (scr("unknown"), {**R, "recording": True, "in_replay": True, "ticks_per_s": 75}, ("wait", "speed_confirmed")),
        (scr("unknown"), {**R, "recording": True, "in_replay": True, "ticks_per_s": 75}, ("wait", "recording")),
        (scr("unknown"), {**R, "ended": "tick_stalled"}, ("wait", "replay_ended")),
        (scr("replay_controls", speed="x4"), R, ("tap", "rp_close")),
        (scr("tv_list", hits={}, rows=[(800, 700)]), R, ("wait", "back_on_list")),
        (scr("tv_list", hits={}, rows=[]), R, ("next_channel",)),
    ]
    for i, (s, r, want) in enumerate(steps):
        t += 1
        act = tv_nav.decide(st, s, r, t)
        assert act[:len(want)] == want, (i, act, want)
        if act[0] == "tap":
            assert tv_nav.allowed(act[1], act[2], MAN), (i, act)
    assert st["channel"] == 1
    assert not tv_nav.allowed("rp_speed", (55, 1500), MAN) and not tv_nav.allowed("tv_row_play", (50, 1500), MAN)
    assert not tv_nav.allowed("anything_else", (450, 500), MAN)


def test_decide_stops():
    assert tv_nav.decide({}, scr("conn_lost"), {}, 0) == ("stop", "conn_lost")
    st = {}
    tv_nav.decide(st, scr("main", hits={"tv_entry": (1, 1)}), {}, 0)
    assert tv_nav.decide(st, scr("unknown"), {}, 10)[0] == "wait"
    assert tv_nav.decide(st, scr("unknown"), {}, 25) == ("stop", "unknown_screen")
    assert tv_nav.decide({}, scr("main", hits={}), {}, 0) == ("stop", "no_tv_entry_template")
    assert tv_nav.decide({"phase": "pick_replay"}, scr("tv_channels", hits={}), {}, 0)[0] == "stop"
    assert tv_nav.decide({}, scr("popup_x"), {}, 0) == ("wait", "popup")      # never closed blind


class FakeClassifier:
    man = MAN

    def __init__(self, seq):
        self.seq = iter(seq)

    def classify(self, img):
        return next(self.seq)


def test_run_dry_run_never_taps():
    taps, clock = [], iter(range(10 ** 6))
    seq = [scr("main", hits={"tv_entry": (450, 300)}), scr("tv_list", hits={"tv_channel_btn": (450, 200)}),
           scr("conn_lost")]
    why = hv.run(lambda: None, lambda x, y: taps.append((x, y)), None, FakeClassifier(seq), tmp(), 10, 99, True,
                 clock=lambda: next(clock), sleep=lambda s: None, log=lambda s: None)
    assert why == "conn_lost" and taps == []
    taps2, clock2 = [], iter(range(10 ** 6))
    hv.run(lambda: None, lambda x, y: taps2.append((x, y)), None, FakeClassifier(seq), tmp(), 10, 99, False,
           clock=lambda: next(clock2), sleep=lambda s: None, log=lambda s: None)
    assert taps2 == [(450, 300), (450, 200)]


def test_reader_pump_records_one_replay():
    frames = syn.battle()
    lines = iter([json.dumps(f) for f in frames] + [json.dumps(dict(battle_active=False, coherent=True,
                                                                     game_tick=0, players=[], entities=[]))] * 40)
    clock = iter(i * 0.1 for i in range(10 ** 6))
    gate = []                                      # hold the reader until the recording is open (as harvest does)

    def held():
        while not gate:
            time.sleep(0.01)
        yield from lines
    pump = hv.ReaderPump(held(), clock=lambda: next(clock))
    path = tmp() / "rec_20261008_130000.jsonl"
    pump.open(path)
    gate.append(1)
    pump.thread.join(timeout=30)
    done = pump.take()
    assert done == (path, "battle_inactive"), done
    assert pump.take() is None
    assert hv.process(path, tmp(), "x")["verdict"] == "accepted"


def test_classifier_on_device_captures():
    if not (SCREENS / "unknown_210535.png").exists() or not (tv_nav.TEMPLATES / "manifest.json").exists():
        print("SKIP captures / templates not present")
        return
    import cv2
    c = tv_nav.Classifier()
    want = {"210528": ("replay_controls", "x1"), "210531": ("replay_controls", "x05"),
            "210535": ("replay_controls", "x4"), "210836": ("replay_controls", "x4"),
            "210211": ("unknown", None), "210538": ("unknown", None)}     # live battle / replay, controls hidden
    for stem, (screen, speed) in want.items():
        r = c.classify(cv2.imread(str(SCREENS / f"unknown_{stem}.png")))
        assert (r["screen"], r.get("speed")) == (screen, speed), (stem, r["screen"], r.get("speed"))


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
