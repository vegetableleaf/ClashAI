"""Self-check for the trophy-road reward choice in ladder_nav (no device): Choose button -> "Choose your reward" ->
one random card -> stop + Discord alert on anything unrecognised. Positives = the owner's phone screenshots rescaled
to 900x1600 (scratchpad/gauntlet/L73/trophy_road/make_positives.py); negatives = the saved L70 ladder_nav captures.
The full ~500-frame negative sweep is scratchpad/gauntlet/L73/trophy_road/eval_trophy_road.py.
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/live_reader/test_trophy_road.py"""
import json
import random
import sys
import tempfile
import time
import types
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ladder_nav  # noqa: E402
from ladder_nav import ALERT, TARGETS, Classifier, LadderNav, command_for  # noqa: E402

cv2.setNumThreads(2)
TR = HERE.parents[1] / "L73" / "trophy_road"
sys.path.insert(0, str(TR))
import make_positives  # noqa: E402
POS = {f"{kind}_{n}": v for src, kind in (("owner_choose_reward.webp", "choice"), ("owner_path_choose.webp", "path"))
       for n, v in make_positives.variants(cv2.imread(str(TR / src))).items()}
RAW = HERE.parents[1] / "L70" / "ladder_nav" / "raw"
if not RAW.exists():                                      # raw captures are untracked: a worktree reads the main checkout's
    RAW = Path("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L70/ladder_nav/raw")
clf = Classifier()


def inside(pt, r):
    return r[0] <= pt[0] <= r[2] and r[1] <= pt[1] <= r[3]


# 1. positives. Expected misses (the feature is physically off-frame in that crop, so "unknown" is right):
#    choice_fitw_bot = the title is cropped off the top; path_fitw_mid / _top = the OK button is cut / cropped off.
MISS = {"choice_fitw_bot", "path_fitw_mid", "path_fitw_top"}
for stem, img in POS.items():
    s = clf.classify(img)
    if stem in MISS:
        assert s["screen"] not in ("choose_reward", "trophy_road"), (stem, s["screen"])
    elif stem.startswith("choice"):
        assert s["screen"] == "choose_reward", (stem, s["screen"])
        (lx, ly), (rx, ry) = s["cards"]
        assert lx < 450 < rx and abs(ly - ry) < 10 and all(inside(c, TARGETS["reward_card"]) for c in s["cards"])
        assert command_for("reward_card", s["cards"][0]).startswith("input tap")
    else:
        assert s["screen"] == "trophy_road" and s["choose"] and s["collect"] is None, (stem, s)
        assert 550 < s["choose"][0] < 750 and command_for("choose", s["choose"]).startswith("input tap"), s["choose"]
print("positives ok")

# 2. negatives: no saved live capture is a reward choice or carries a Choose button; Collect stays Collect
for p in sorted(RAW.glob("*.png")):
    img = cv2.imread(str(p))
    if img.shape[:2] != (1600, 900):
        continue
    s = clf.classify(img)
    assert s["screen"] != "choose_reward" and not s.get("choose"), (p.name, s["screen"], s.get("choose"))
tr = clf.classify(cv2.imread(str(RAW / "trophy_road.png")))
assert tr["screen"] == "trophy_road" and tr["collect"] and tr["choose"] is None
print("negatives ok")

# 3. planner
PATH = {"screen": "trophy_road", "collect": None, "choose": (658, 928), "ok": (450, 1543), "scores": {}, "sig": None}
CHOICE = {"screen": "choose_reward", "cards": [(295, 420), (603, 421)], "scores": {}}
UNK = {"screen": "unknown", "scores": {}}
nav = LadderNav(0, {}, random.Random(1))
assert nav.plan(PATH, 1) == ("act", "choose", (658, 928))
nav.acted("choose", 1.5)
assert all(nav.plan(UNK, t)[0] == "wait" for t in (2, 5, 8, 11.9))      # never a blind tap-through (TAP_WAIT_S = 2.5)
p = nav.plan(UNK, 12.1)
assert p[0] == "stop" and p[1].startswith(ALERT), p
# choice screen: one seeded random card, the same one on every frame until tapped, tapped once
picks = set()
for seed in range(20):
    nav = LadderNav(0, {}, random.Random(seed))
    a, b = nav.plan(CHOICE, 1), nav.plan(CHOICE, 1.5)
    assert a == b and a[:2] == ("act", "reward_card") and a[2] in CHOICE["cards"]
    picks.add(nav.pick)
assert picks == {0, 1}                                    # both sides occur across seeds
nav = LadderNav(0, {}, random.Random(3))
first = nav.plan(CHOICE, 1)
nav.acted("reward_card", 2)
assert nav.plan(CHOICE, 5)[0] == "wait" and nav.choose_flow
p = nav.plan(CHOICE, 10.5)                                # still on the choice 8 s after the tap: stop + alert
assert p[0] == "stop" and p[1].startswith(ALERT) and ("left", "right")[nav.pick] in p[1]
assert all(nav.plan(UNK, t)[0] == "wait" for t in (11, 15)) and nav.plan(UNK, 21.5)[0] == "stop"
# back on the path after the pick: the flow is over, the normal Trophy Road scan / OK continues
nav = LadderNav(0, {}, random.Random(3))
nav.acted("choose", 1)
nav.plan(CHOICE, 2)
nav.acted("reward_card", 3)
assert nav.plan(dict(PATH, choose=None), 5)[1] == "tr_scroll" and not nav.choose_flow
# a Choose that never leaves the path screen: CHOOSE_MAX taps, then stop + alert
nav = LadderNav(0, {})
for k in range(nav.CHOOSE_MAX):
    assert nav.plan(PATH, k)[1] == "choose"
    nav.acted("choose", k + 0.5)
p = nav.plan(PATH, 9)
assert p[0] == "stop" and p[1].startswith(ALERT)
# Collect keeps priority; outside the reward choice an unknown screen is still tapped through (default flow unchanged)
assert LadderNav(0, {}).plan(dict(PATH, collect=(350, 1320)), 1)[1] == "collect"
nav = LadderNav(0, {})
assert nav.plan(UNK, 1)[0] == "wait" and nav.plan(UNK, 3.6)[1] == "tap_through"
print("planner ok")

# 4. runner end to end on real frames, fake device: path -> Choose -> choice -> card -> unrecognised -> stop + alert
frames = {"path": POS["path_fith_s100"], "choice": POS["choice_fith_s100"],
          "unknown": cv2.imread(str(RAW / "s_c.png"))}
screen, taps, alerts, clock = ["path"], [], [], [1000.0]


def fake_run(cmd, **k):
    taps.append(cmd[-1])
    screen[0] = {"path": "choice", "choice": "unknown"}[screen[0]]
    return types.SimpleNamespace(stdout=b"", returncode=0)


saved = ladder_nav.grab, ladder_nav.subprocess, ladder_nav.time
ladder_nav.grab = lambda adb: frames[screen[0]]
ladder_nav.subprocess = types.SimpleNamespace(run=fake_run)
ladder_nav.time = types.SimpleNamespace(time=lambda: clock[0], sleep=lambda s: clock.__setitem__(0, clock[0] + s),
                                        strftime=time.strftime, perf_counter=time.perf_counter)
d = Path(tempfile.mkdtemp())
try:
    r = ladder_nav.LadderNavRunner(["adb"], log_dir=d, state_path=d / "s.json", trophy_log=False, seed=11,
                                   alert=lambda text, png: alerts.append((text, png)) or True)
    ok, why = r.run()
finally:
    ladder_nav.grab, ladder_nav.subprocess, ladder_nav.time = saved
log = [json.loads(x) for x in next(d.glob("ladder_nav_*.jsonl")).read_text().splitlines()]
pick = next(e for e in log if e["event"] == "reward_pick")
card = clf.classify(frames["choice"])["cards"][("left", "right").index(pick["side"])]
assert not ok and why.startswith(ALERT), why
assert len(taps) == 2 and taps[0].startswith("input tap") and taps[1] == "input tap {} {}".format(*map(round, card)), taps
assert len(alerts) == 1 and alerts[0][1] is not None and alerts[0][1].exists() and ALERT in alerts[0][0]
assert any(e["event"] == "alert" and e["sent"] for e in log)
assert sorted(x.name[:-len("_000000.png")].split("_", 3)[-1] for x in (d / "ladder_unknown").glob("*.png")) == ["choose", "reward_card"]
print(f"runner ok: seed 11 picked the {pick['side']} card at {pick['point']}; taps {taps}; stop: {why}")

# 5. the alert poster never raises and never prints the webhook (missing secret -> False)
ladder_nav.WEBHOOK, w0 = Path("/nonexistent/discord_webhook.txt"), ladder_nav.WEBHOOK
assert ladder_nav.discord_alert("x", None) is False
ladder_nav.WEBHOOK = w0
print("trophy-road reward-choice checks passed")

# verifier 2026-10-07 F1: the path still shown one frame after the Choose tap must NOT end the flow
nav = LadderNav(0, {}, random.Random(1))
assert nav.plan(PATH, 1)[1] == "choose"
nav.acted("choose", 1.5)
nav.plan(PATH, 3.0)                                       # tap latency: the path is still on screen
assert nav.choose_flow
assert all(nav.plan(UNK, t)[0] == "wait" for t in (3.5, 6.5, 12.0)) and nav.plan(UNK, 13.6)[0] == "stop"
# F4: after a completed pick, a second Choose reward gets the full budget again
nav = LadderNav(0, {}, random.Random(1))
nav.plan(PATH, 1); nav.acted("choose", 1.5); nav.plan(CHOICE, 3); nav.acted("reward_card", 3.5)
nav.plan(PATH, 5)
assert nav.chooses == 0 and not nav.choose_flow
print("verifier F1/F4 regressions ok")
