"""Effect of judging follow-ups on the reader's frame grid (the SIM's "outstanding" = decided, not landed; live's = tapped, not
confirmed): the SIM before this change (follow-ups judged at due, due+2, ... off the 2-tick frame grid for odd after_ticks,
and from the decision tick itself) vs now (the first frame tick at or after due AND after the first tap returned).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/latency2/outstanding_effect.py [BASE_REV]   (default: the rev
    BEFORE the change = main when run on the branch)

Drives pipeline/tests/test_e1_action_delay's fake match (action delay 26) with a first play + follow-up(s), over
after_ticks 0..9 x within 0/6/20 x elixir levels x one or two follow-ups; both versions run on identical inputs.
Prints how many scenarios differ in WHAT is played (fired/cancelled + reasons) and by how many ticks the landing moves.
"""
from __future__ import annotations

import importlib.util
import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
rev = sys.argv[1] if len(sys.argv) > 1 else "main"
src = subprocess.run(["git", "show", f"{rev}:pipeline/e1_eval.py"], cwd=REPO, capture_output=True, text=True, check=True).stdout
tmp = tempfile.TemporaryDirectory()
path = Path(tmp.name) / "e1_base.py"
path.write_text(src, encoding="utf-8")
spec = importlib.util.spec_from_file_location("e1_base", path)
base = importlib.util.module_from_spec(spec)
sys.modules["e1_base"] = base
spec.loader.exec_module(base)

from pipeline import e1_eval as new  # noqa: E402
import pipeline.tests.test_e1_action_delay as AD  # noqa: E402
import pipeline.tests.test_e1_follow_up as TF  # noqa: E402
from pipeline.tests.test_e1_opp_counter import T  # noqa: E402


def run(mod, follow, el, frame=2):
    AD.E = mod
    new.FOLLOW_FRAME_TICKS = frame
    env = TF._Env(el)
    m, env, _ = AD._scripted([dict(AD.PLAY, follow_ups=follow)], 26, env=env)
    new.FOLLOW_FRAME_TICKS = 2
    r = m.result()
    return dict(r.get("follow_ups", {})), [p["land_tick"] for p in r["plays"]], [c[0] for c in env.eng.calls]


norm = lambda c: {k.replace("first_refused", "first_unconfirmed"): v for k, v in c.items()}      # noqa: E731
levels = {"rich": lambda t: 9.0, "tight": lambda t: 6.1, "short": lambda t: 5.0,
          "rising": lambda t: 5.0 + max(0, t - T) * 0.05}


def sweep(label, ref, cand):
    """ref / cand = callables (follow, el) -> run result, both fed identical scenarios."""
    rows = diff_what = diff_when = 0
    moves = []
    for after, within, (name, el), two in itertools.product(range(10), (0, 6, 20), levels.items(), (False, True)):
        mk = lambda mod: ([mod.follow_up_spec(5, TF.CELL + 3, after, within_ticks=within)]       # noqa: E731
                          + ([mod.follow_up_spec(1, TF.CELL + 3, after + 2, within_ticks=within)] if two else []))
        a, b = ref(mk, el), cand(mk, el)
        rows += 1
        if norm(a[0]) != norm(b[0]):
            diff_what += 1
        elif a[1] != b[1]:
            diff_when += 1
            moves += [y - x for x, y in zip(a[1], b[1])]
    print(f"{label}: {rows} scenarios; WHAT is played differs in {diff_what}; same plays, landing ticks move in {diff_when}"
          + (f" (shift min {min(moves)} max {max(moves)} mean {sum(moves) / len(moves):.2f} ticks)" if moves else ""))


# (1) the frame grid: exact-tick judging (an idealised SIM) vs the 2-tick reader-frame grid this module now uses = live
sweep("frame grid vs exact ticks (same code)", lambda mk, el: run(new, mk(new), el, frame=1), lambda mk, el: run(new, mk(new), el, frame=2))
# (2) the whole change vs the rev before it (grid + each follow-up reaching the engine at its own landing tick)
sweep(f"this change vs {rev}", lambda mk, el: run(base, mk(base), el), lambda mk, el: run(new, mk(new), el))
tmp.cleanup()
