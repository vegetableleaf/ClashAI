"""Every ladder match writes exactly ONE '[ladder] result:' line (critic 10-17: 4 matches at 13k had none or 'n/a').
Signal order: results screen > in-match towers > trophy-total change > UNKNOWN. Real frames: the saved L70 ladder_nav
captures (trophy_road.png, res_1.png, s_c.png), a labelled L73 main-menu frame (11031 trophies), and the towers of the
last logged frame of live_play_20261017_200646 (the match a trophy-road screen replaced the results screen of: +32).
    icebow/.venv/Scripts/python.exe -m pytest scratchpad/gauntlet/L68/live_reader/test_ladder_result.py"""
import contextlib
import io
import json
import re
import sys
import tempfile
import time
import types
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ladder_nav  # noqa: E402
from live_play import tower_verdict  # noqa: E402

RAW = HERE.parents[1] / "L70" / "ladder_nav" / "raw"
if not RAW.exists():
    RAW = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/ladder_nav/raw")
IMG = HERE.parents[1] / "L73" / "trophies" / "img"
TR, RES, UNK = (cv2.imread(str(RAW / f"{n}.png")) for n in ("trophy_road", "res_1", "s_c"))
MAIN = cv2.imread(str(IMG / "main_05.png"))              # labels.json: main menu, 11031 trophies
MONITOR = re.compile(r"\[ladder\] result: (WIN|LOSS|DRAW).*?trophies ([+-]\d+)")   # card_use / analyze.py
# live_play_20261017_200646.jsonl, last frame (tick 4969, my_side 1): side 0 lost its right princess -> WIN 1-0
TOWERS_200646 = [[0, 9000, 3000, -1, 7728, 7728], [0, 3500, 6500, -1, 1053, 4858], [1, 9000, 29000, -1, 7032, 7032],
                 [1, 3500, 25500, -1, 171, 4424], [1, 14500, 25500, -1, 4004, 4424]]


def frame(rows, tick=4969):
    return {"game_tick": tick, "entities": [dict(side=s, x=x, y=y, card_id=c, hp=h, max_hp=m) for s, x, y, c, h, m in rows]}


def test_tower_verdict_on_the_logged_200646_towers():
    v = tower_verdict(frame(TOWERS_200646), 1)
    assert v == {"crowns_me": 1, "crowns_opp": 0, "won": True, "tick": 4969}, v
    assert tower_verdict(frame(TOWERS_200646), 0)["won"] is False
    assert tower_verdict(frame([]), 1)["won"] is None                    # a frame with no towers: no verdict
    assert tower_verdict(None, 1) is None and tower_verdict(frame(TOWERS_200646), None) is None
    king = [r for r in TOWERS_200646 if not (r[0] == 0 and r[1] == 9000)]  # opponent king gone = 3 crowns
    assert tower_verdict(frame(king), 1)["crowns_me"] == 3


MAIN_SCR = {"screen": "main", "battle": (460.0, 1245.0), "bonus": False, "scores": {}, "mode": "trophy_road",
            "sig": np.zeros((80, 45), np.uint8)}


def run_nav(first, after, state, towers=None, note=True, d=None, trophy=None):
    """One LadderNavRunner.run() on real frames with a fake device: `first` = the screen after the match, `after` =
    {screen: next screen after a tap}. -> (stdout lines, nav log events, runner)."""
    d = d or Path(tempfile.mkdtemp())
    frames = {"trophy_road": TR, "results": RES, "unknown": UNK, "main": MAIN}
    screen, clock = [first], [1000.0]

    def fake_run(cmd, **k):
        screen[0] = after.get(screen[0], screen[0])
        return types.SimpleNamespace(stdout=b"", returncode=0)

    saved = ladder_nav.grab, ladder_nav.subprocess, ladder_nav.time
    ladder_nav.grab = lambda adb: frames[screen[0]]
    ladder_nav.subprocess = types.SimpleNamespace(run=fake_run)
    ladder_nav.time = types.SimpleNamespace(time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                            strftime=time.strftime, perf_counter=time.perf_counter)
    out = io.StringIO()
    try:
        (d / "s.json").write_text(json.dumps(state))
        r = ladder_nav.LadderNavRunner(["adb"], log_dir=d, state_path=d / "s.json", seed=1)
        if trophy is not None:
            r.trophy = trophy
        real = r.clf.classify
        r.clf.classify = lambda img: dict(MAIN_SCR) if img is MAIN else real(img)   # the L73 frame is a crop-era capture
        with contextlib.redirect_stdout(out):
            if note:
                r.note_match("live_play_X.jsonl", towers)
            r.run()
    finally:
        ladder_nav.grab, ladder_nav.subprocess, ladder_nav.time = saved
    log = [json.loads(x) for p in sorted(d.glob("ladder_nav_*.jsonl")) for x in p.read_text().splitlines()]
    return out.getvalue().splitlines(), log, r


def results_lines(lines):
    return [s for s in lines if s.startswith("[ladder] result:")]


TR_PATH = {"trophy_road": "main", "main": "unknown"}     # Collect -> home -> Battle -> queue (the 200646 sequence)
WIN_TOWERS = tower_verdict(frame(TOWERS_200646), 1)


def test_trophy_road_replaces_results_towers_decide_total_gives_the_number():
    lines, log, r = run_nav("trophy_road", TR_PATH, {"trophies_total": 11000, "trophies_since": 0}, WIN_TOWERS)
    res = results_lines(lines)
    assert len(res) == 1, lines
    m = MONITOR.search(res[0])
    assert m and m[1] == "WIN" and m[2] == "+31" and "src=towers" in res[0], res
    # the result line comes BEFORE the trophy anchor it is part of (drift/ladder.py segments on that line)
    assert lines.index(res[0]) < lines.index("[ladder] trophies: 11031 total"), lines
    o = [e for e in log if e["event"] == "outcome"]
    assert len(o) == 1 and o[0]["won"] is True and o[0]["src"] == "towers" and o[0]["trophies_delta"] == 31, o
    assert r.st["trophies_total"] == 11031 and r.st["trophies_since"] == 0 and "pending_match" not in r.st
    assert r.st["W"] == 1                                 # an inferred result is counted in the session line too


def test_no_tower_verdict_falls_back_to_the_trophy_total():
    lines, log, _ = run_nav("trophy_road", TR_PATH, {"trophies_total": 11063, "trophies_since": -30},
                            dict(WIN_TOWERS, won=None))
    res = results_lines(lines)
    assert len(res) == 1 and MONITOR.search(res[0]).groups() == ("LOSS", "-2") and "src=trophy_total" in res[0], res


def test_an_unknown_total_baseline_still_writes_one_line():
    lines, log, _ = run_nav("trophy_road", TR_PATH, {}, dict(WIN_TOWERS, won=None))
    res = results_lines(lines)
    assert len(res) == 1 and res[0].startswith("[ladder] result: UNKNOWN") and "trophies n/a" in res[0], res
    lines, _, _ = run_nav("trophy_road", TR_PATH, {}, WIN_TOWERS)                 # towers alone: WIN, number n/a
    res = results_lines(lines)
    assert len(res) == 1 and res[0].startswith("[ladder] result: WIN") and "trophies n/a" in res[0], res


def test_results_screen_wins_over_towers_and_one_line_when_the_number_reads_late():
    class Late:                                           # 191748: the first results frame read n/a, a retry read 30
        n = 0

        def delta(self, img):
            self.n += 1
            return None if self.n == 1 else 30

        def total(self, img):
            return None
    lines, log, _ = run_nav("results", {"results": "unknown"}, {}, dict(WIN_TOWERS, won=True), trophy=Late())
    res = results_lines(lines)
    assert len(res) == 1, lines                           # res_1.png: WINNER over the opponent = a loss
    assert MONITOR.search(res[0]).groups() == ("LOSS", "-30") and "src=results" in res[0], res
    assert not any(s.startswith("[ladder] trophies: ") and "total" not in s for s in lines), lines


def test_the_last_match_of_a_run_is_reported_by_the_next_run():
    d = Path(tempfile.mkdtemp())                          # 164525: STOP file after the match -> no nav in that run
    st = d / "s.json"
    st.write_text("{}")
    r1 = ladder_nav.LadderNavRunner(["adb"], log_dir=d, state_path=st, trophy_log=False)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r1.note_match("live_play_164525.jsonl", WIN_TOWERS)   # persisted at once; nothing printed yet
    assert not results_lines(out.getvalue().splitlines())
    assert json.loads(st.read_text())["pending_match"]["log"] == "live_play_164525.jsonl"
    lines, log, r2 = run_nav("trophy_road", TR_PATH, json.loads(st.read_text()), note=False)
    res = results_lines(lines)
    assert len(res) == 1 and res[0].startswith("[ladder] result: WIN") and "src=towers" in res[0], res
    assert [e["log"] for e in log if e["event"] == "outcome"] == ["live_play_164525.jsonl"]


def test_a_match_without_any_nav_is_reported_when_the_next_one_is_noted():
    d = Path(tempfile.mkdtemp())
    r = ladder_nav.LadderNavRunner(["adb"], log_dir=d, state_path=d / "s.json", trophy_log=False)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        r.note_match("live_play_1.jsonl", WIN_TOWERS)
        r.note_match("live_play_2.jsonl", None)           # launched mid-battle: no nav between the two matches
    res = results_lines(out.getvalue().splitlines())
    assert len(res) == 1 and res[0].startswith("[ladder] result: WIN") and r.st["pending_match"]["log"] == "live_play_2.jsonl"


def test_no_pending_match_and_no_results_screen_writes_nothing():
    lines, _, _ = run_nav("trophy_road", TR_PATH, {}, note=False)   # e.g. the first nav of a fresh run on the home screen
    assert not results_lines(lines), lines


if __name__ == "__main__":
    for k, v in list(globals().items()):
        if k.startswith("test_"):
            v()
    print("ladder result tests passed")
