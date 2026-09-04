"""L48 arm D-4 (stacked on D-1): TEMPO ON A QUIET BOARD. The search oracle (doctrine_regret.py) puts
its largest regret on the doctrine HOLDING an empty board at 3-7 elixir where it would play the
knight (n=385, mean regret 0.45) or skeletons (n=215). Test whether that is real sim value or the
scorer's board-value term paying for an idle body: quiet board and >= D4_MIN elixir -> nominate the
knight (centre-back) at 2.0; D4_SKEL=1 also cycles skeletons at the corners from >= 3."""
import os
import doctrine_v2 as v2
from clashrl.sim import doctrine as D
MIN = float(os.environ.get("D4_MIN", "4.0")); SKEL = os.environ.get("D4_SKEL", "0") == "1"
SKELMIN = float(os.environ.get("D4_SKELMIN", "3.0")); IW = float(os.environ.get("D4_IW", "99"))

def _rules(env, card_id):
    got = v2._rules(env, card_id)
    if got:
        return got
    keys = env.deck_keys
    base = keys[card_id][:-4] if keys[card_id].endswith("_evo") else keys[card_id]
    e = float(env.eng.elixir[0])
    w = {}
    if v2._quiet(env):
        if base == "knight" and e >= MIN:
            D._add_spot(w, env, 0.50, 0.83, 1.0, 0.3)
        elif SKEL and base == "skeletons" and e >= SKELMIN:
            D._add_spot(w, env, 0.10, 0.86, 1.0, 0.3); D._add_spot(w, env, 0.86, 0.86, 1.0, 0.3)
        elif base == "ice_wizard" and e >= IW:
            D._add_spot(w, env, 0.10, 0.86, 1.0, 0.3); D._add_spot(w, env, 0.86, 0.86, 1.0, 0.3)
    return list(w.items()) if w else None

def _cards(env):
    w = dict(v2._cards(env) or {})
    e = float(env.eng.elixir[0])
    if v2._quiet(env):
        hand = set(env._hand_ids())
        for i in D._deck_ids(env, "knight"):
            if i in hand and e >= max(MIN, float(env.specs[i].elixir)):
                w[i] = max(w.get(i, 0.0), 2.0)
        if SKEL:
            for i in D._deck_ids(env, "skeletons"):
                if i in hand and e >= SKELMIN:
                    w[i] = max(w.get(i, 0.0), 1.2)
        for i in D._deck_ids(env, "ice_wizard"):
            if i in hand and e >= IW:
                w[i] = max(w.get(i, 0.0), 1.1)
    return w or None

def install():
    v2.install()
    D._doctrine_cells_rules = _rules
    D.doctrine_cards = _cards
    print(f"[doctrine_v4] installed: quiet-board tempo MIN={MIN} SKEL={SKEL} SKELMIN={SKELMIN} IW={IW}")
