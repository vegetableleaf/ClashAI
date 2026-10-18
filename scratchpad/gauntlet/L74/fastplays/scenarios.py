"""L74 fastplays (10-17): DESIGNED tight-timing scenarios for Rocket + Tornado, built from the engine's own reset.

A scenario = RoyaleSelfPlayEnv.reset (the eval's decks / deal machinery) re-entered with MatchSetup(start_tick, elixir_milli,
spawns): our hand Rocket, Tornado, Knight, Skeletons (next Ice Wizard), 10 elixir; the enemy at 0 elixir and PASSIVE (it never
decides); an enemy COLUMN of four medium-speed troops (Wizard, Musketeer, Valkyrie, Knight; 2.2 tiles apart along its walking
direction, so it stays a column) that a lone Rocket covers two of and one Tornado pull all four, centred at a distance from the
enemy king / princess / mid / bank / our half. Every engine tick is logged (my spells, enemy bodies, enemy towers) so the Rocket's
launch / impact, the Tornado's life and the damage at impact are measured, not modelled. Engine levels = the default (11).

  sweep   engine only (no model): Rocket deploys at T0 + 26 (the SIM's tap -> deploy delay, = live's ~25), Tornado GAP ticks
          later (deploy to deploy = tap to tap), BOTH aimed at the cell of the group's centroid at the Tornado's deploy tick (an
          oracle aim from a spell-free dry run of the same seed: isolates timing from aiming); a lone Rocket aimed at the centroid
          at its own impact -> Rocket damage / kills vs GAP = the measured hit window per distance.
  model   (scenario_model.py) the live decision stack decides from the scenario state, fast plays OFF / ON.

Board frame = tiles, me at the bottom (my king (9, 28.65), enemy king (9, 3), enemy princesses (3.5, 6.5) / (14.5, 6.5)).
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

HAND = ('Rocket', 'Tornado', 'Knight', 'Skeletons', 'IceWizard')       # first four = the hand, fifth = next
LEARNER_DECK = None                                                     # the eval's own (E.ICEBOW_ENGINE_DECK), set lazily
OPP_DECK = ['Knight', 'Musketeer', 'Wizard', 'ElectroWizard', 'BabyDragon', 'Valkyrie', 'MiniPekka', 'Fireball']
DELAY = 26                                                              # live_cfg action_delay_ticks (SIM's tap -> deploy)
ROCKET_R = 2.0                                                          # catalog Rocket radius, tiles (decision_options)

COLUMN = ('Wizard', 'Musketeer', 'Valkyrie', 'Knight')                 # medium speed (60) each: the column keeps its shape
OFFSETS = (-3.3, -1.1, 1.1, 3.3)                                        # along board y (the walking direction), tiles
# name -> group centre (board tiles); the column runs along y at x = centre x (off tower footprints and water)
CENTRES = {
    'king':         (6.5, 4.0),     # beside / in front of the enemy king (rows 0.7 .. 7.3)
    'princess':     (6.5, 9.0),     # in front of the enemy left princess
    'enemy_mid':    (6.0, 11.0),
    'enemy_bank':   (3.5, 13.5),    # walking onto the left bridge
    'bridge_mine':  (3.5, 19.5),    # just over the bridge on my half
    'my_princess':  (6.5, 23.0),    # at my left princess
    'my_king':      (9.0, 21.0),    # centre lane, in front of my king
}
SCEN = {k: ((cx, cy), [(c, cx, cy + o) for c, o in zip(COLUMN, OFFSETS)]) for k, (cx, cy) in CENTRES.items()}
# mixed speeds (Giant 45, Musketeer / Wizard 60, Mini P.E.K.K.A 90): does a pulled clump STAY a clump? (sweep / lead only)
MIXED = ('Giant', 'Musketeer', 'MiniPekka', 'Wizard')
for k in ('king', 'princess'):
    (cx, cy), _ = SCEN[k]
    SCEN[k + '_mixed'] = ((cx, cy), [(c, cx, cy + o) for c, o in zip(MIXED, OFFSETS)])
NAMES = list(SCEN)                                                     # appended last: scenario_model seeds unchanged
T0S = (1800, 3000)                                                     # 1:30 single elixir, 2:30 double elixir


def rocket_flight_ticks(cx, cy):
    """decision_options.rocket_flight_ticks (the rule's model of the flight, deploy -> impact)."""
    from pipeline.decision_options import rocket_flight_ticks as f
    return f(cx, cy)


def to_engine(bx, by, L):
    """Board tiles (side L's frame) -> pool/engine units (1000 per tile)."""
    from pipeline import engine_play as ep
    return ep.board_to_engine(bx / 18.0, by / 32.0, L == 1)


def to_board(X, Y, L):
    """Engine units -> board tiles in side L's frame (the inverse of to_engine)."""
    if L == 1:
        X, Y = 18000 - X, 32000 - Y
    return X / 1000.0, 32.0 - Y / 1000.0


def nearest_cell(bx, by, grid):
    from pipeline.decision_options import cell_centres_tiles
    import numpy as np
    xs, ys = cell_centres_tiles(grid)
    return int(np.argmin((xs - bx) ** 2 + (ys - by) ** 2))


def scenario_reset(env, deck_items, L, name, T0, elixir=(10000, 0)):
    """Re-enter ``env`` (already reset by the eval's machinery) at ``T0`` with the scenario: side L's deal starts with HAND, the
    enemy group spawned (full hp), elixir (mine, enemy). -> the spawn list (card, board x, y)."""
    import msgspec
    from royalegym.protocol import SpawnSpec
    from pipeline.royale_env import FORM_OF, SCALE
    orders = {}
    for s in (0, 1):
        o = list(range(8))
        random.Random(f"deal:{env.seed}:{s}").shuffle(o)          # = RoyaleSelfPlayEnv.reset's deal
        if s == L:
            first = [env.decks[s].index(h) for h in HAND]
            o = first + [i for i in o if i not in first]
        orders[s] = o
    wanted = None
    if env.forms_mode == "deck":
        wanted = {s: [FORM_OF[str(it["name"] if isinstance(it, dict) else it).partition("@")[2]] for it in deck_items[s]]
                  for s in (0, 1)}
    env.deal = {s: [env.decks[s][i] for i in orders[s]] for s in (0, 1)}
    setup = env._setup({s: [env.deck_ids[s][i] for i in orders[s]] for s in (0, 1)}, orders, wanted)
    el = [0, 0]
    el[L], el[1 - L] = int(elixir[0]), int(elixir[1])
    spawns = []
    for card, bx, by in SCEN[name][1]:
        X, Y = to_engine(bx, by, L)
        spawns.append(SpawnSpec(team=1 - L, card_id=env.card_id(card), x=int(round(X)) * SCALE, y=int(round(Y)) * SCALE, hp=-1))
    setup = msgspec.structs.replace(setup, start_tick=int(T0), elixir_milli=el, spawns=spawns)
    env.core.reset(env.seed, setup)
    env.public_plays = []
    env._ghosts, env._gi, env._pending = [], 0, []
    env.terminated, env.episode, env.eng.last_episode = False, {}, None
    env._reset_abilities()
    env.tick = int(env.core.state().tick)
    hand = [env.names[c] for c in env.core.state().players[L].hand]
    if hand[:4] != list(HAND[:4]):
        raise RuntimeError(f"scenario hand {hand} != {HAND[:4]}")
    return SCEN[name][1]


def snap(env, L):
    """One tick: my spells (card, x, y, aim, delay, motion), enemy non-tower bodies (uid, card, x, y, hp, flying, radius), enemy
    tower hp (sum). Engine units -> board tiles in my frame."""
    from royalegym.protocol import EntityKind
    from pipeline.royale_env import SCALE
    st = env.core.state()
    sp = []
    for s in st.spells:
        if s.team != L:
            continue
        x, y = to_board(s.x / SCALE, s.y / SCALE, L)
        ax, ay = to_board(s.aim_x / SCALE, s.aim_y / SCALE, L)
        sp.append((env.names.get(s.card_id, str(s.card_id)), round(x, 2), round(y, 2), round(ax, 2), round(ay, 2),
                   int(s.delay_ticks), int(s.motion)))
    en, tw = [], 0
    for e in st.entities:
        if e.team == L:
            continue
        if e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER):
            tw += max(0, int(e.hp))
            continue
        x, y = to_board(e.x / SCALE, e.y / SCALE, L)
        en.append((int(e.uid), env.names.get(e.card_id, str(e.card_id)), round(x, 2), round(y, 2), int(e.hp),
                   bool(e.flying), round(e.radius / SCALE / 1000.0, 2)))
    return {"t": int(st.tick), "spells": sp, "enemy": en, "etowers": tw}


def track(env, L):
    """Wrap env._advance_to so every engine tick is logged (snap) -> the log list (grows as the env advances)."""
    log = [snap(env, L)]
    orig = env._advance_to

    def adv(target):
        while env.tick < target and not env.terminated:
            orig(env.tick + 1)
            log.append(snap(env, L))
    env._advance_to = adv
    return log


def spell_life(log, card):
    """[(first tick seen, last tick seen, aim (x, y))] of my spells of ``card`` (a gap between sightings = another one)."""
    out, cur = [], None
    for s in log:
        hit = [x for x in s["spells"] if x[0] == card]
        if hit and cur is None:
            cur = [s["t"], s["t"], (hit[0][3], hit[0][4])]
        elif hit:
            cur[1] = s["t"]
        elif cur is not None:
            out.append(tuple(cur))
            cur = None
    if cur is not None:
        out.append(tuple(cur))
    return out


def impact(log, rocket, spawned):
    """Rocket ``rocket`` = (first, last, aim): damage at impact (the tick after its last sighting) to enemy bodies near the aim,
    bodies hit / killed (of the scenario group too), enemy tower damage; and how many group bodies stood within the blast."""
    by_t = {s["t"]: s for s in log}
    ti = rocket[1] + 1
    before, after = by_t.get(ti - 1), by_t.get(ti)
    if before is None or after is None:
        return {"impact_tick": None}
    ax, ay = rocket[2]
    after2 = by_t.get(ti + 1, after)
    hp_after = {e[0]: e[4] for e in after2["enemy"]}
    dmg = hit = killed = 0
    inside = []
    for uid, card, x, y, hp, fly, rad in before["enemy"]:
        d = math.hypot(x - ax, y - ay)
        if d > ROCKET_R + rad + 0.25:
            continue
        inside.append(card)
        left = hp_after.get(uid, 0)
        if left < hp:
            hit += 1
            dmg += hp - max(left, 0)
            killed += left <= 0
    group = {c for c, _, _ in spawned}
    return {"impact_tick": ti, "damage": dmg, "hit": hit, "killed": killed,
            "group_in_blast": sum(c in group for c in inside), "tower_damage": before["etowers"] - after2["etowers"]}





def dist_to(log, t, point):
    """Enemy bodies' distances (tiles) to ``point`` at tick t."""
    s = next((x for x in log if x["t"] == t), None)
    return [] if s is None else [round(math.hypot(e[2] - point[0], e[3] - point[1]), 2) for e in s["enemy"]]

def centroid(log, t, uids):
    """Mean board position of the group's ALIVE bodies (``uids``) at tick t; None when none is alive / no such tick."""
    s = next((x for x in log if x["t"] == t), None)
    pts = [(e[2], e[3]) for e in (s or {"enemy": []})["enemy"] if e[0] in uids and e[4] > 0]
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)) if pts else None


def group_hp(log, t, uids):
    s = next((x for x in log if x["t"] == t), None)
    return sum(e[4] for e in (s or {"enemy": []})["enemy"] if e[0] in uids and e[4] > 0)


# ---------------------------------------------------------------------------------------------------------------- sweep
def make_env():
    from pipeline.royale_env import RoyaleSelfPlayEnv
    return RoyaleSelfPlayEnv(decision_ticks=10, tail_cap=7200, forms_mode="deck", hero_abilities=True, ability_policy="v2")


def enter(env, name, T0, L, seed):
    """The scenario on a fresh env reset -> (log, spawned, group uids)."""
    from pipeline import search_s0 as S
    global LEARNER_DECK
    if LEARNER_DECK is None:
        LEARNER_DECK = list(S.E.ICEBOW_ENGINE_DECK)
    decks = {L: LEARNER_DECK, 1 - L: OPP_DECK}
    env.reset(decks[0], decks[1], seed)
    spawned = scenario_reset(env, decks, L, name, T0)
    log = track(env, L)
    return log, spawned, {e[0] for e in log[0]["enemy"]}


def dry_run(env, name, T0, L, seed, horizon=260):
    log, _, uids = enter(env, name, T0, L, seed)
    env._advance_to(T0 + horizon)
    return log, uids


def sweep_one(env, name, T0, L, gap, grid, dry, seed=741200, tornado=True, lead=False):
    """Forced combo: Rocket deploys at T0 + DELAY, Tornado ``gap`` ticks later (negative = first), both at the cell of the
    group's dry-run centroid at the Tornado's deploy tick; ``tornado`` False = a lone Rocket aimed at the dry-run centroid at
    its own impact (two fixed-point passes over the flight). ``lead``: the Tornado as before, the Rocket instead aimed at the
    group centroid AT ITS IMPACT on a Tornado-only run (the pull included; three fixed-point passes over the flight) = a
    perfectly leading Rocket. -> dict."""
    from pipeline import engine_play as ep
    dlog, duids = dry
    t_r = T0 + DELAY
    if tornado:
        aim = centroid(dlog, t_r + gap, duids)
    else:
        aim = centroid(dlog, t_r, duids)
        for _ in range(2):
            aim = centroid(dlog, t_r + rocket_flight_ticks(*aim), duids) or aim
    cell = tcell = nearest_cell(*aim, grid)
    if lead and tornado:                                   # the pulled trajectory without the Rocket
        tlog, _, tuids = enter(env, name, T0, L, seed)
        env._advance_to(t_r + gap)
        env.act(L, env.decks[L].index("Tornado"), *ep.cell_to_engine(tcell, L == 1, grid))
        env._advance_to(t_r + max(gap, 0) + 140)
        a = tuple(v * k for v, k in zip(ep.cell_center(tcell, grid), (18, 32)))
        for _ in range(3):
            a = centroid(tlog, t_r + rocket_flight_ticks(*a), tuids) or a
        cell = nearest_cell(*a, grid)
    X, Y = ep.cell_to_engine(cell, L == 1, grid)
    cx, cy = ep.cell_center(cell, grid)
    log, spawned, uids = enter(env, name, T0, L, seed)
    sched = sorted([(t_r, "Rocket")] + ([(t_r + gap, "Tornado")] if tornado else []))
    acc = {}
    for t, card in sched:
        env._advance_to(t)
        xy = (X, Y) if card == "Rocket" else ep.cell_to_engine(tcell, L == 1, grid)
        acc[card] = env.act(L, env.decks[L].index(card), *xy)["accepted"]
    env._advance_to(t_r + max(gap, 0) + 140)
    rockets, torn = spell_life(log, "Rocket"), spell_life(log, "Tornado")
    out = {"scenario": name, "T0": T0, "L": L, "gap": gap if tornado else None, "cell": cell, "tornado_cell": tcell, "lead": lead,
           "cell_xy": (round(cx * 18, 2), round(cy * 32, 2)), "accepted": acc, "group_hp0": group_hp(log, T0, uids),
           "rocket": rockets[0][:2] if rockets else None, "tornado": torn[0][:2] if torn else None,
           "flight_rule": rocket_flight_ticks(cx * 18, cy * 32)}
    if rockets:
        imp = impact(log, rockets[0], spawned)
        out.update(imp)
        ti = imp.get("impact_tick")
        if ti:
            out["impact_minus_tornado_deploy"] = (ti - torn[0][0]) if torn else None
            out["dist_at_impact"] = sorted(dist_to(log, ti - 1, rockets[0][2]))
            out["group_hp_drop_at_impact"] = group_hp(log, ti - 1, uids) - group_hp(log, ti + 1, uids)
    return out


def main_sweep(out_path, gaps, sides=(0, 1), t0s=(1800,), seed=741200, lead=False, only=None):
    grid = "lattice"
    env = make_env()
    with open(out_path, "w", encoding="utf-8") as f:
        for name in (only or NAMES):
            for T0 in t0s:
                for L in sides:
                    dry = dry_run(env, name, T0, L, seed)
                    f.write(json.dumps(sweep_one(env, name, T0, L, 0, grid, dry, seed, tornado=False)) + "\n")
                    for g in gaps:
                        f.write(json.dumps(sweep_one(env, name, T0, L, g, grid, dry, seed, lead=lead)) + "\n")
                    f.flush()
            print("swept", name, flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("probe", "sweep", "lead"))
    ap.add_argument("--out", default="/workspace/results/fastplays/sweep.jsonl")
    ap.add_argument("--only", default="", help="comma list of scenario names (default: all)")
    a = ap.parse_args()
    if a.mode == "probe":
        env = make_env()
        for name in ("king", "bridge_mine"):
            dry = dry_run(env, name, 1800, 0, 741200)
            print(name, "dry centroid T0..", [tuple(round(v, 1) for v in (centroid(dry[0], t, dry[1]) or (-1, -1)))
                                            for t in range(1800, 2000, 20)])
            for g in (None, 0, 20, 40):
                r = sweep_one(env, name, 1800, 0, g or 0, "lattice", dry, tornado=g is not None)
                print(json.dumps(r))
    else:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        if a.mode == "lead":                               # the leading-Rocket variant, Tornado after the Rocket
            main_sweep(a.out, list(range(0, 66, 4)), lead=True, only=[x for x in a.only.split(',') if x])
        else:
            main_sweep(a.out, list(range(-26, 82, 2)), only=[x for x in a.only.split(',') if x])   # Tornado tap >= T0
