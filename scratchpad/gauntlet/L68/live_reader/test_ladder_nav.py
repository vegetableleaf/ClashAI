"""Self-check for ladder_nav (no device): classifier on the saved 2026-10-02 captures + the planner's policy.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/test_ladder_nav.py"""
import sys
from pathlib import Path
import cv2
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ladder_nav import Classifier, LadderNav, NavViolation, command_for  # noqa: E402

RAW = Path(__file__).resolve().parents[2] / "L70" / "ladder_nav" / "raw"
if not RAW.exists():                                      # raw captures are untracked: a worktree reads the main checkout's
    RAW = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/ladder_nav/raw")
clf = Classifier()
want = {"res_1": "results", "res_8": "results", "main2": "main", "main4": "main", "promo_pass_x": "popup_x",
        "trophy_btn": "modes", "queue1": "loading", "queue2": "unknown", "tab_left": "unknown", "s_c": "unknown"}
assert clf.classify(None)["screen"] == "nograb"
tr = clf.classify(cv2.imread(str(RAW / "trophy_road.png")))
assert tr["screen"] == "trophy_road" and tr["collect"] is not None, tr["scores"]
assert LadderNav(0, {}).plan(tr, 1)[1] == "collect" and command_for("collect", tr["collect"]).startswith("input tap")
cl = clf.classify(cv2.imread(str(RAW / "conn_lost.png")))
assert cl["screen"] == "conn_lost" and cl["other_device"] and cl["reload"] is not None, cl["scores"]
p = LadderNav(0, {}).plan(cl, 1)
assert p[0] == "stop" and p[1].startswith("ANOTHER_DEVICE")                 # never kick the owner's other device
assert LadderNav(0, {}).plan(dict(cl, other_device=False), 1)[1] == "reload"
assert command_for("reload", cl["reload"]).startswith("input tap")
nav = LadderNav(0, {})                                    # no Collect visible: scan down, then OK when unmoved/at cap
assert nav.plan(dict(tr, collect=None), 1)[1] == "tr_scroll"
nav.acted("tr_scroll", 2)
assert nav.plan(dict(tr, collect=None), 3)[1] == "bottom_ok"          # same signature = the list did not move
assert command_for("tr_scroll", None).startswith("input swipe 450 1150 450 550")
nav = LadderNav(0, {})
nav.tr_swipes = nav.TR_SWIPES
assert nav.plan(dict(tr, collect=None), 1)[1] == "bottom_ok"
assert command_for("bottom_ok", tr["ok"]).startswith("input tap")
for n, s in want.items():
    got = clf.classify(cv2.imread(str(RAW / f"{n}.png")))
    assert got["screen"] == s, (n, got["screen"], got["scores"])
r = clf.classify(cv2.imread(str(RAW / "res_8.png")))
assert r["won"] is False                                  # the 20:21 match was a loss (WINNER over the opponent)
assert clf.classify(cv2.imread(str(RAW / "main4.png")))["bonus"] is True

def res(won):
    return {"screen": "results", "play_again": (310, 1452), "ok": (590, 1452), "won": won, "scores": {}}
def main(bonus, v=0):
    return {"screen": "main", "battle": (455, 1220), "bonus": bonus, "sig": np.full((80, 45), v, np.uint8), "scores": {}}
UNK = {"screen": "unknown", "scores": {}}

# loss: Play Again, counted once
st = {"wins_today": 0}
nav = LadderNav(0.0, st)
assert nav.plan(res(False), 1)[:2] == ("act", "play_again") and nav.plan(res(False), 2)[:2] == ("act", "play_again")
assert st["L"] == 1 and st["wins_today"] == 0
nav.acted("play_again", 3)
assert nav.plan(UNK, 4)[0] == "wait" and nav.plan(UNK, 7.5)[0] == "handoff"
# wins 1-3: Play Again; the 4th: OK, then tap-through on unknown chest screens, then a stable main -> Battle
for w in (1, 2, 3):
    nav = LadderNav(0.0, st)
    assert nav.plan(res(True), 1)[1] == "play_again" and st["wins_today"] == w
nav = LadderNav(0.0, st)
assert nav.plan(res(True), 1)[1] == "results_ok" and st["wins_today"] == 4
nav.acted("results_ok", 2)
assert nav.plan(UNK, 3)[0] == "wait" and nav.plan(UNK, 5.6)[1] == "tap_through"
nav.acted("tap_through", 5.7)
assert nav.plan(UNK, 6)[0] == "wait"                       # waits TAP_WAIT_S again
assert nav.plan(main(False, 0), 9)[0] == "wait" and nav.plan(main(False, 0), 10)[0] == "wait"
assert nav.plan(main(False, 0), 11)[1] == "battle" and st["wins_today"] == 4 and st["last_main_t"] == 11
# a 5th win the same day: Play Again (bonus used up, probe not due); after PROBE_S: OK -> main shows the bonus -> reset
nav = LadderNav(100.0, st)
assert nav.plan(res(True), 101)[1] == "play_again" and st["wins_today"] == 5
nav = LadderNav(2000.0, st)
assert nav.plan(res(False), 2001)[1] == "results_ok"
for t in (2003, 2004, 2005):
    p = nav.plan(main(True, 7), t)
assert p[1] == "battle" and st["wins_today"] == 0
# an unread banner waits 3 s, then counts a draw
st2 = {}
nav = LadderNav(0.0, st2)
assert nav.plan(res(None), 1)[0] == "wait" and nav.plan(res(None), 4.5)[0] == "wait" and nav.plan(res(None), 9.5)[1] == "play_again" and st2["D"] == 1
# popups / sheets close; stop after TAP_MAX tap-throughs
assert LadderNav(0, {}).plan({"screen": "popup_x", "x": (807, 222), "scores": {}}, 1)[1] == "close_x"
assert LadderNav(0, {}).plan({"screen": "modes", "scores": {}}, 1)[1] == "modes_close"
nav = LadderNav(0.0, {})
nav.taps = nav.TAP_MAX
assert nav.plan(UNK, 1)[0] == "wait" and nav.plan(UNK, 4)[0] == "stop"
# allowlist: the Shop tab and off-target points are refused
for tgt, pt in (("tap_through", (60, 1500)), ("battle", (450, 1500)), ("results_ok", (310, 1452)), ("nope", (1, 1))):
    try:
        command_for(tgt, pt)
        raise AssertionError(f"{tgt} {pt} was allowed")
    except NavViolation:
        pass
assert command_for("play_again", (310, 1452)) == "input tap 310 1452"
print("ladder_nav self-checks passed")
nav = LadderNav(0.0, {})
nav.acted("battle", 0.5)
NG = {"screen": "nograb", "scores": {}}
assert all(nav.plan(NG, t)[0] == "wait" for t in (1, 5, 30)) and nav.plan(NG, 62)[0] == "stop"   # never handoff/tap
print("nograb checks passed")


def _reward_reveal_check():
    """Synthetic frames: a card on a plain background is a reveal; a top bar or busy sides is not."""
    from ladder_nav import is_reward_reveal
    rng = np.random.default_rng(0)
    bg = np.full((1600, 900, 3), 90, np.uint8)
    card = bg.copy(); card[600:880, 330:570] = rng.integers(0, 255, (280, 240, 3), dtype=np.uint8)
    chest = card.copy()                                            # no title above the item = the unopened chest
    assert not is_reward_reveal(chest)
    card[340:460, 260:640] = (rng.integers(0, 2, (120, 380, 1)) * 255).astype(np.uint8)   # the item title: white text
    assert is_reward_reveal(card)
    bar = card.copy(); bar[:120] = rng.integers(0, 255, (120, 900, 3), dtype=np.uint8)
    assert not is_reward_reveal(bar)
    busy = card.copy(); busy[320:1100, :200] = rng.integers(0, 255, (780, 200, 3), dtype=np.uint8)
    assert not is_reward_reveal(busy)
    assert not is_reward_reveal(bg)
    print("reward reveal checks passed")


_reward_reveal_check()
