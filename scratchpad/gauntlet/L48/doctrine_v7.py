"""L48 arm D-7 (stacked on D-6 / D-4 / D-1): TESLA FOR THE TANK AND FOR THEIR BOW. The regret oracle under
d6body (regret_d6body.txt) puts its next buckets on HOLD -> tesla(_evo) at 4-6 elixir with a pekka (+bomber)
or an enemy x_bow on the board. Measured causes: pekka is profiled `tank` but not `win_condition`, so the
"tesla for their wincon" rule (doctrine.py ~981) never fires on it; an enemy x_bow IS a wincon but the tesla
cell rule (~470) only accepts troop / building-targeting `movers`, so the nomination has no cell -> HOLD.
D7_TANK=1: an approaching TANK (profile.tank, not already a wincon, y > 0.30) nominates tesla 5.0 + skeletons 3.0.
D7_XBOW=1: an enemy x_bow alive at y > 0.30 nominates tesla 5.0 with a pull cell: centre column, y 0.585
(the standard pull depth), pulled toward the bow's lane."""
import os
import doctrine_v6 as v6
from clashrl.sim import doctrine as D
from clashrl import card_threat
TANK = os.environ.get("D7_TANK", "0") == "1"; XBOW = os.environ.get("D7_XBOW", "0") == "1"


def _tank_threat(env):
    for u in D._enemies(env):
        if u.spec.kind != "troop" or u.y <= 0.30:
            continue
        p = card_threat.profile(env.db, u.spec.base)
        if p.tank and not p.win_condition:
            return u
    return None


def _enemy_bow(env):
    for u in D._enemies(env):
        if u.spec.base == "x_bow" and u.y > 0.30:
            return u
    return None


def _holdable(env, base):
    e = float(env.eng.elixir[0]); hand = set(env._hand_ids())
    for i in D._deck_ids(env, base):
        if i in hand and env.specs[i].elixir <= e:
            return i
    return None


def _cards(env):
    w = dict(v6._cards(env) or {})
    tank = _tank_threat(env) if TANK else None
    bow = _enemy_bow(env) if XBOW else None
    if tank is not None or bow is not None:
        t = _holdable(env, "tesla")
        if t is not None:
            w[t] = max(w.get(t, 0.0), 5.0)
        if tank is not None:
            s = _holdable(env, "skeletons")
            if s is not None:
                w[s] = max(w.get(s, 0.0), 3.0)
    return w or None


def _rules(env, card_id):
    w = v6.v4._rules(env, card_id)
    if w:
        return w
    if XBOW and env.specs[card_id].base == "tesla":
        bow = _enemy_bow(env)
        if bow is not None:
            w = {}
            x = 0.5 + (0.06 if bow.x < 0.5 else -0.06)
            D._add_spot(w, env, x, 0.585, 5.0, 1.0)
            return w or None
    return None


def install():
    v6.install()
    D._doctrine_cells_rules = _rules
    D.doctrine_cards = _cards
    print(f"[doctrine_v7] installed: tesla for tank={TANK} xbow={XBOW}", flush=True)
