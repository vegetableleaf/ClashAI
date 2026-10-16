"""The three bait patches change the learner deck / worker script and nothing else.  python test_bait.py  (pod, repo root)"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bait_eval  # noqa: E402
import bait_rl  # noqa: E402
import bait_s0  # noqa: E402

# rl: only learner_deck / name / bucket change; the rng-drawn fields (opponent, opp deck, side, seed) are the original's
orig = [{"tag": "sp0001_00", "opp": {"id": "x"}, "learner_deck": ["Log"], "learner_deck_name": "icebow", "learner_bucket": "icebow",
         "opp_deck": ["Hog"], "opp_deck_name": "r1", "learner_side": 1, "seed": 7}]
bait_rl._orig = lambda *a, **k: [dict(m) for m in orig]
got = bait_rl.R.sample_matchups()
assert bait_rl.R.sample_matchups is bait_rl.sample_matchups
assert got[0]["learner_deck"] == bait_s0.DECK and got[0]["learner_deck_name"] == "bait_friend"
assert {k: v for k, v in got[0].items() if not k.startswith("learner_deck")} == \
       {k: v for k, v in orig[0].items() if not k.startswith("learner_deck")}

# s0: the learner plays DECK, opponent deck / side / seed as search_s0's own setup
seen = {}
bait_s0.E.SelfPlayMatch = lambda env, spec, *a: seen.update(spec)
r = type("R", (), {"opps": {"gen": (None, {})}, "lcfg": {}, "learner": None, "make_env": lambda self: None})()
bait_s0.S.Runner.setup(r, "gen", 741201, ["Hog"])
assert seen == {"tag": "s0:gen:741201", "opp": {"id": "gen"}, "learner_deck": bait_s0.DECK, "opp_deck": ["Hog"],
                "learner_side": 1, "seed": 741201}

# eval: gap's D3 command with every live key dropped = livecal's worker command through bait_s0.py + --own-effects only
job = {"seeds": [1], "checkpoint": "ck.pt", "opponent": {"path": "e4.pt", "temperature": .1}, "fast": False}
cmd = bait_eval.gap.command("D3", job, "c.json", "out", "py", drop=tuple(bait_eval.gap.livecal.LIVE))
assert cmd[1] == str(HERE/"bait_s0.py") and cmd[2] == "--worker" and cmd[-1] == "--own-effects"
assert not any(f"--{k.replace('_', '-')}" in cmd for k in bait_eval.gap.livecal.LIVE)
assert cmd[cmd.index("--tau-plain") + 1] == ".35" and "--learner-policy" not in cmd
assert bait_s0.DECK == ["Valkyrie@hero", "SkeletonArmy@evolution", "GoblinBarrel@evolution", "Princess", "BlowdartGoblin",
                        "Wallbreakers", "IceSpirits", "Cannon"]
print("BAIT TEST PASS")
