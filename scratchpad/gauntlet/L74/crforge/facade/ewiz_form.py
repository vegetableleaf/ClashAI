"""F1c-1b: does the engine load ElectroWizard in its hero form (2)? A reset with only that entry marked, as
royale_env._form_loads probes it; prints the engine's refusal when it refuses. Census decks: how often EWiz is decked
in each form. usage: [ROYALE_ENGINE=crforge] ROYALE_RUNTIME=fin16-linux /workspace/venvf16/bin/python -I ewiz_form.py
"""
import collections
import os
import sys

os.environ.setdefault("ROYALE_RUNTIME", "fin16-linux")
sys.path[:0] = ["/workspace/cfspeed/pylib", os.environ.get("CB_TREE", "/workspace/f1/rl")]
from pipeline.royale_env import RoyaleSelfPlayEnv  # noqa: E402
from royalegym.protocol import MatchSetup, ShuffleMode  # noqa: E402

env = RoyaleSelfPlayEnv(decision_ticks=10, forms_mode="deck", feature_version=6)
ids = env.ids
d0 = [ids[n] for n in ("Knight", "IceWizard", "Tesla", "Log", "Xbow", "Rocket", "Tornado", "Skeletons")]
for card in ("ElectroWizard", "Valkyrie", "Wizard", "Bowler"):
    d1 = [ids[n] for n in (card, "Knight", "Log", "Skeletons", "Tesla", "Rocket", "Tornado", "Xbow")]
    try:
        env.core.reset(1, MatchSetup(decks=[d0, d1], shuffle=ShuffleMode.NONE, forms=[[0] * 8, [2] + [0] * 7]))
        print(card, "form 2 loads; buttons", env.core.state().players[1].abilities)
    except ValueError as exc:
        print(card, "form 2 REFUSED:", str(exc)[:300])
forms = collections.Counter()
for ln in open("/workspace/cfspeed/decks.tsv").read().splitlines():
    f = ln.split("\t")
    for names, fs in ((f[1], f[2]), (f[3], f[4])):
        for n, v in zip(names.split(","), fs.split(",")):
            if n == "ElectroWizard":
                forms[v] += 1
print("census ElectroWizard decked forms", dict(forms))
