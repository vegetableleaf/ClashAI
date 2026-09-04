"""L48 arm D-2: LET THE ANSWER WORK (stacked on D-1). Measured (doctrine_diag2.py, 12 matches):
the doctrine is at 0-2 elixir in 1695 of 2068 decisions where a non-ignorable push is on our side and
it has nothing to say -- it has spent everything answering the previous push, one nominated card per
decision (the wincon rule alone nominates tesla + skeletons + ice_wizard, and the policy plays them on
consecutive decisions). Fix: after a play against a push, HOLD for HOLD_S seconds unless the committed
enemy elixir on our side grows by GROW or more. Detects the play from the elixir drop, so it needs no
hook into doctrine_policy."""
import os
import doctrine_v2 as v2
from clashrl.sim import doctrine as D
HOLD_S = float(os.environ.get("D2_HOLD_S", "4.0"))
GROW = float(os.environ.get("D2_GROW", "3.0"))

def _commit(env):
    return sum(float(u.spec.elixir) for u in D._enemies(env) if u.y > 0.42 and u.spec.kind != "spell")

def _cards(env):
    st = env.__dict__.setdefault("_d2", {"e": None, "t_play": -1e9, "c_play": 0.0})
    e = float(env.eng.elixir[0]); t = float(env.eng.t)
    if st["e"] is not None and e < st["e"] - 0.9:            # a play happened at the previous decision
        st["t_play"] = t; st["c_play"] = _commit(env)
    st["e"] = e
    w = v2._cards(env)
    if not w or v2._quiet(env):
        return w
    if t - st["t_play"] < HOLD_S and _commit(env) < st["c_play"] + GROW:
        return None
    return w

def install():
    v2.install()
    D.doctrine_cards = _cards
    print(f"[doctrine_v3] installed: let-the-answer-work HOLD_S={HOLD_S} GROW={GROW}")
