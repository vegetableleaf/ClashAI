"""L48 arm D-1: CYCLE WITH A CELL. Measured (doctrine_diag.py, 12 matches): 591 of 959 doctrine
nominations had NO cell and became HOLD; 374 of those were the_log nominated by the quiet-board
">=8 -> cheapest card" rule, and the hand froze at (ice_wizard, knight, the_log, tornado) for 360 of
391 rich holds -- the bow never came back into hand. Fix, in-process (c2r imports doctrine.py, so
the module is not edited while it runs): (1) the cycle rule nominates the cheapest affordable card
THAT HAS A CELL; (2) quiet-board cycle cells for knight (centre-back, walks up as the next bow's
tank), ice_wizard (back corners, like skeletons), the_log (top of our half, the weaker enemy
princess column -- rolls forward for tower chip). Only fires on a QUIET board at >=8 elixir."""
from clashrl.sim import doctrine as D
from clashrl import threat_value

_orig_rules = D._doctrine_cells_rules
_orig_cards = D.doctrine_cards

def _quiet(env):
    committed = [u for u in D._enemies(env) if u.y > 0.42 and u.spec.kind != "spell"]
    if not committed:
        return True
    cost = threat_value.bodies_ignore_frac(env.db, [u.spec.base for u in committed],
                                           tower_level=D._tower_level(env), enemy_level=D._enemy_level(env))
    return cost < threat_value.IGNORE_FRAC

def _rules(env, card_id):
    got = _orig_rules(env, card_id)
    if got:
        return got
    if float(env.eng.elixir[0]) < 8.0 or not _quiet(env):
        return got
    keys = env.deck_keys
    base = keys[card_id][:-4] if keys[card_id].endswith("_evo") else keys[card_id]
    w = {}
    if base == "knight":
        D._add_spot(w, env, 0.50, 0.83, 1.0, 0.3)
    elif base == "ice_wizard":
        D._add_spot(w, env, 0.10, 0.86, 1.0, 0.3); D._add_spot(w, env, 0.86, 0.86, 1.0, 0.3)
    elif base == "the_log":
        alive = [t for t in env.eng.towers[1][:2] if t.hp > 0]
        if alive:
            t = min(alive, key=lambda t: t.hp)
            D._add_spot(w, env, t.x, 0.5625, 1.0, 0.3)
    return list(w.items()) if w else None

def _cards(env):
    w = dict(_orig_cards(env) or {})
    e = float(env.eng.elixir[0])
    if e >= 8.0 and _quiet(env):
        hand = [i for i in env._hand_ids() if e >= float(env.specs[i].elixir)]
        cost = lambda i: float(env.specs[i].elixir)
        cheap = min(hand, key=cost, default=None)
        if cheap is not None and abs(w.get(cheap, 0.0) - 1.5) < 1e-9 and not D.doctrine_cells(env, cheap):
            del w[cheap]
        for i in sorted(hand, key=cost):
            if D.doctrine_cells(env, i):
                w[i] = max(w.get(i, 0.0), 1.5); break
    return w or None

def install():
    D._doctrine_cells_rules = _rules
    D.doctrine_cards = _cards
    print("[doctrine_v2] installed: cycle-with-a-cell")
