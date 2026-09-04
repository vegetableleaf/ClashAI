"""L48 arm D-6 (stacked on D-4+skel): GENERIC BODY. The regret oracle on D-4skel: 683 of the
high-regret decisions are on NON-empty boards and the top bucket is still HOLD -> knight (n=134)
/ HOLD -> skeletons (n=130): giant (13/24), archer_queen (11/20), inferno_dragon+skeleton_army
(14/18) -- boards the counter table has no entry for, so the doctrine holds while a push walks in.
Rule: a non-ignorable GROUND threat in our half with nothing nominated -> knight 2.5 (body-block;
the knight cell rule already places it on the threat's path), else skeletons 1.5 (distraction)."""
import os
import doctrine_v4 as v4
from clashrl.sim import doctrine as D

def _cards(env):
    w = dict(v4._cards(env) or {})
    if w or v4.v2._quiet(env):
        return w or None
    thr = D._deepest_ground_threat(env)
    if thr is None or thr.y <= 0.42:
        return None
    e = float(env.eng.elixir[0]); hand = set(env._hand_ids())
    for base, wt in (("knight", 2.5), ("skeletons", 1.5)):
        for i in D._deck_ids(env, base):
            if i in hand and e >= float(env.specs[i].elixir):
                w[i] = wt
                return w
    return None

def install():
    v4.install()
    D.doctrine_cards = _cards
    print("[doctrine_v6] installed: generic body")
