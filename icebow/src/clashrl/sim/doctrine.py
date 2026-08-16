"""Doctrine-prior placement distributions for rollout exploration (DOCTRINE.md, tranche 1).

The user's scaffolding idea in the mathematically safe shape (log.txt 2026-08-14): when the
trainer's CELL exploration floor fires, its mass is routed through a DOCTRINE distribution for
the current (card, board state) instead of uniform -- so the value function gets to SEE the
outcomes of known-good placements early, and keeps them only if the returns justify it.

Hard rules of the mechanism (do not weaken):
  * ROLLOUT-ONLY. Greedy eval, the benchmark, and live play never touch this module.
  * The caller mixes this into the sampling distribution and stores the MIXTURE log-prob, so the
    PPO ratio stays exact importance sampling (same argument as the uniform floors).
  * ANNEALABLE: sim.doctrine_frac -> 0 removes the scaffold without touching anything else.
  * Ground truth only: every trigger reads the ENGINE, never the policy's (noised) observation --
    this is a teaching prior, and it must not inherit perception noise.

Each rule returns peaked-but-not-delta weights (a spot plus its neighbourhood) so the policy
learns the AREA, not one memorised tile. All spots quote DOCTRINE.md row numbers.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# ---- geometry helpers -------------------------------------------------------

def _add_spot(w: Dict[int, float], env, x: float, y: float, weight: float = 3.0,
              ring: float = 1.0) -> None:
    """`weight` on the cell at (x, y) plus `ring` on its 8-neighbourhood."""
    gx, gy = env.actions.coords_to_grid(x, y)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            nx, ny = gx + dx, gy + dy
            if 0 <= nx < env.gw and 0 <= ny < env.gh:
                c = ny * env.gw + nx
                w[c] = w.get(c, 0.0) + (weight if (dx == 0 and dy == 0) else ring)


def _deck_ids(env, *bases: str) -> set:
    """Deck indices whose BASE card name is one of ``bases`` (evo folds onto its base)."""
    out = set()
    for i, k in enumerate(env.deck_keys):
        base = k[:-4] if k.endswith("_evo") else k
        if base in bases:
            out.add(i)
    return out


def _enemies(env):
    return [u for u in env.eng.units if u.team == 1 and u.hp > 0]


def _deepest_ground_threat(env):
    """The enemy GROUND unit deepest into our half (y > 0.5); None if none."""
    cand = [u for u in _enemies(env) if not u.spec.flying and u.spec.kind == "troop" and u.y > 0.5]
    return max(cand, key=lambda u: u.y) if cand else None


def _opp_cards(env) -> set:
    return set(getattr(env.opponent, "cards", []) or [])


def _pull_resistant(u) -> bool:
    """Units a Tornado barely moves, so no rule should aim a pull at one.

    "Be aware that some units are very resistant to the pull from Tornado, such as charging Princes
    and heavy units such as Giant and Golem" (X-Bow Ice Wizard Control guide). The same page is
    blunt about the failure mode this prevents -- against a Hog with a tank in front, "DO NOT
    attempt to Tornado ... instead use Rocket". Heft is now sourced (game-file `mass`), so this
    reads the real number rather than guessing from a name list.
    """
    if getattr(u.spec, "knockback_immune", False):
        return True
    m = getattr(u.spec, "mass", None)
    return bool(m and m >= 12)


# ---- the rule table ---------------------------------------------------------

def doctrine_cells(env, card_id: int) -> Optional[List[Tuple[int, float]]]:
    """(cell, weight) prior for playing ``card_id`` right now, or None (caller falls back to the
    uniform floor). Weights need not be normalised; the caller masks to deployable and normalises."""
    keys = env.deck_keys
    if not (0 <= card_id < len(keys)):
        return None
    base = keys[card_id][:-4] if keys[card_id].endswith("_evo") else keys[card_id]
    w: Dict[int, float] = {}
    eng = env.eng
    enemies = _enemies(env)
    threat = _deepest_ground_threat(env)
    king_asleep = not eng.towers[0][2].active

    if base == "tesla":
        # #1/#5/#6/#15: centre-band pull vs any tower-bound/building-targeting or deep threat.
        movers = [u for u in enemies if (u.spec.building_only or u.spec.kind == "troop") and u.y > 0.30]
        if not movers:
            return None
        # #14: vs an EARTHQUAKE deck the "(0-3)" spot -- centre column ~3 tiles from the river,
        # above the princess-corner EQ region, still pulls the Hog. NB the 24-row grid is 1.33
        # tiles/row: 0.548 -> row 14 (~3 tiles from river) and 0.585 -> row 15 (~4.5 tiles, the
        # standard pull depth). Values nearer the row boundary quantise into the SAME row and the
        # EQ distinction silently vanishes (caught by the rule tests).
        y = 0.548 if "earthquake" in _opp_cards(env) else 0.585
        _add_spot(w, env, 0.48, y, 4.0, 1.5)
        _add_spot(w, env, 0.44, y, 1.5, 0.5)
        _add_spot(w, env, 0.52, y, 1.5, 0.5)

    elif base == "x_bow":
        if env._defensive:
            _add_spot(w, env, 0.48, 0.55, 4.0, 1.5)          # #56: defensive bow, centre band
        else:
            # #53/#47: behind-bridge lock spots. Opposite lane of the enemy's committed mass
            # (the punish rule); EDGE column vs rocket decks so their rocket can't clip tower+bow.
            edge = "rocket" in _opp_cards(env)
            left, right = (0.16, 0.84) if edge else (0.26, 0.73)
            mass_left = sum(u.spec.elixir for u in enemies if u.x < 0.5)
            mass_right = sum(u.spec.elixir for u in enemies if u.x >= 0.5)
            wl, wr = (4.0, 2.0) if mass_right > mass_left else (2.0, 4.0) if mass_left > mass_right else (3.0, 3.0)
            _add_spot(w, env, left, 0.50, wl, 1.0)
            _add_spot(w, env, right, 0.50, wr, 1.0)
            _add_spot(w, env, 0.48, 0.47, 1.0, 0.3)          # centre-forward, front row only (low weight)

    elif base == "knight":
        # #59 (S+): MK deep + king asleep -> knight IN FRONT OF THE KING, the second bait of the
        # activation chain (his jump onto the bait splashes the king -- the leap + its 2.2-tile
        # splash are modeled; skels rule places the first bait).
        mk = next((u for u in enemies if u.spec.base == "mega_knight" and u.y > 0.52), None)
        if mk is not None and king_asleep:
            kt = eng.towers[0][2]                             # ENGINE king, not the screen anchor
            _add_spot(w, env, kt.x, kt.y - 1.8 / 32.0, 4.0, 1.0)
            return list(w.items())
        # #58/#61 (tranche 2): KITE the heavy single-target melees CENTRE instead of body-blocking
        # -- a PEKKA/MK dragged off-lane never reaches the bow/tower, and body-blocking them just
        # feeds the hit. Kite spot replaces the on-path block for these targets.
        if threat is not None and threat.spec.base in ("pekka", "mega_knight"):
            _add_spot(w, env, 0.48, 0.62, 3.5, 1.0)
            _add_spot(w, env, 0.40 if threat.x < 0.48 else 0.56, 0.60, 1.5, 0.5)
            return list(w.items())
        # #49: enemy mortar -> walk into the 3.5-tile blind spot (deploy at our bridge edge, he
        # enters it himself; the mortar loses its lock).
        mortar = next((u for u in enemies if u.spec.base == "mortar"), None)
        if mortar is not None:
            _add_spot(w, env, mortar.x, max(0.50, mortar.y + 0.04), 4.0, 1.0)
        # #41: firecracker king-activation bait -- 4 tiles in front of the king, 2 inside the
        # princess (her shrapnel splashes the king). Only while the king is asleep.
        fc = next((u for u in enemies if u.spec.base == "firecracker" and u.y > 0.35), None)
        if fc is not None and king_asleep:
            _add_spot(w, env, 0.35 if fc.x < 0.5 else 0.61, 0.63, 3.5, 1.0)
        # #2/#28/#31: body-block the deepest ground threat on its path (also the PEKKA kite start).
        if threat is not None:
            _add_spot(w, env, threat.x, min(threat.y + 0.05, 0.64), 3.0, 1.0)
        if not w:
            return None

    elif base == "skeletons":
        # #10: surround a lone tower-bound unit near our princess line; #30: triangle on a heavy
        # melee; #27: on top of a bridge princess locked on our tower.
        princess = next((u for u in enemies if u.spec.base == "princess" and 0.38 <= u.y <= 0.52), None)
        if princess is not None:
            _add_spot(w, env, princess.x, max(0.50, princess.y), 4.0, 1.0)
        # #59 (S -- the leap + its tower-splash are modeled+fixed): MK deep + king asleep -> the
        # activation-bait spot ~4 tiles in front of the ENGINE's king (its towers sit deeper than
        # the screen anchors -- king (0.50, 0.906), not the live 0.72; hardcoding screen-space y
        # here put the bait 7 tiles short, caught by test). Knight rule places the second bait.
        mk = next((u for u in enemies if u.spec.base == "mega_knight" and u.y > 0.52), None)
        if mk is not None and king_asleep:
            kt = eng.towers[0][2]
            _add_spot(w, env, kt.x + (0.05 if mk.x >= kt.x else -0.05), kt.y - 4.2 / 32.0, 3.5, 1.0)
        if threat is not None:
            tb = threat.spec.base
            if tb == "electro_giant":
                # #66 (corrected 2026-08-14): his reflect is an AOE RADIUS -- anything attacking
                # inside it gets zapped REGARDLESS of side. There is NO good skels placement on an
                # E-Giant; the counter is ranged-only (IW/Tesla/tower). No spot -> the corner-cycle
                # fallback below applies instead of a surround that feeds him.
                pass
            elif tb in ("mega_knight", "valkyrie", "dark_prince"):
                # #58/#64 (geometry corrected 2026-08-14): "behind" only exists when the unit is
                # DEEP in our half. A blocker at our OFFENSIVE bow (bridge rows) has its back on
                # the enemy side -- undeployable -- so there the skels go LATERAL, on/beside it,
                # as a distraction that buys the bow 2-3 more shots.
                if threat.y >= 0.60:
                    _add_spot(w, env, threat.x, max(0.50, threat.y - 0.06), 3.0, 1.0)   # true behind
                else:
                    _add_spot(w, env, threat.x + (0.045 if threat.x < 0.48 else -0.045),
                              max(0.50, threat.y), 3.0, 1.0)                            # lateral distract
            else:
                _add_spot(w, env, threat.x, threat.y, 3.0, 1.5)   # surround: centre + ring IS the triangle
        if not w:
            # #standing-5: cycle corners on a quiet board (low weight -- mostly the policy's call)
            _add_spot(w, env, 0.10, 0.86, 1.0, 0.3)
            _add_spot(w, env, 0.86, 0.86, 1.0, 0.3)

    elif base == "ice_wizard":
        # #standing-4: behind the engagement, 0.64-0.68, threat lane biased centre; off-axis vs
        # splash threats (#39) is approximated by the lateral ring.
        if threat is None and not any(u.spec.flying and u.y > 0.35 for u in enemies):
            return None
        tx = threat.x if threat is not None else 0.48
        _add_spot(w, env, 0.48 + (0.10 if tx < 0.48 else -0.10), 0.66, 3.0, 1.5)
        _add_spot(w, env, 0.48, 0.66, 2.0, 1.0)

    elif base == "tornado":
        # #3/#16: king activation -- a tower-bound unit past our princess line while the king
        # sleeps (air INCLUDED: balloon pulls). #52/#37: clump >=2 enemies to the centre band.
        # Never a rule for a LONE tank (DOCTRINE.md niche note).
        bound = [u for u in enemies if (u.spec.building_only or u.y > 0.55) and u.hp > 0
                 and not _pull_resistant(u)]
        if king_asleep and any(u.y > 0.52 for u in bound):
            kt = eng.towers[0][2]                             # pull TO the ENGINE king's doorstep
            _add_spot(w, env, kt.x, kt.y - 1.5 / 32.0, 5.0, 1.0)
        clump = [u for u in enemies if u.y > 0.42 and not _pull_resistant(u)]
        if len(clump) >= 2:
            cx = sum(u.x for u in clump) / len(clump)
            _add_spot(w, env, 0.48 + (cx - 0.48) * 0.5, 0.55, 3.0, 1.0)
        # THE SNEAKY LOCK (icebow guide): "Tornado units out of X-Bow range for a sneaky lock",
        # and explicitly "if they play a Knight near their tower and they don't have anything else
        # on the arena, Tornado the Knight out of X-Bow range to get it on tower". The bow retargets
        # the TOWER once its defender is dragged off, which is how a lock happens without a tank.
        bow = next((u for u in eng.units
                    if u.team == 0 and u.spec.base == "x_bow" and u.hp > 0), None)
        if bow is not None:
            for u in enemies:
                if _pull_resistant(u) or u.spec.kind != "troop":
                    continue
                if abs(u.x - bow.x) + abs(u.y - bow.y) < 0.22:   # close enough to be its target
                    # aim BEYOND the defender, away from the bow: the pull drags it off the bow's line
                    dx, dy = u.x - bow.x, u.y - bow.y
                    n = max(1e-6, abs(dx) + abs(dy))
                    _add_spot(w, env, u.x + dx / n * 0.05, u.y + dy / n * 0.05, 4.0, 1.0)
                    break
        if not w:
            return None

    elif base == "the_log":
        # #22/#23/#28: GROUND swarms / charge units, our half or bridge. HARD air guard: if every
        # candidate flies, there is NO log rule (the Log cannot touch air -- user correction).
        ground = [u for u in enemies if not u.spec.flying and 0.38 <= u.y]
        # THE TOMBSTONE RULE (icebow guide, verbatim): "always Log a Tombstone at half hp -- it'll
        # destroy it and the death skeletons". Two cards' worth of value from a 2-elixir spell, and
        # it is a BUILDING, so the generic ground-swarm rule above never proposed it.
        tomb = next((u for u in enemies if u.spec.base == "tombstone" and u.hp > 0
                     and u.hp <= u.spec.hp * 0.55), None)
        if tomb is not None:
            _add_spot(w, env, tomb.x, tomb.y, 4.5, 1.0)
        if not ground:
            return None if not w else list(w.items())
        tgt = max(ground, key=lambda u: u.y)
        _add_spot(w, env, tgt.x, max(0.46, min(tgt.y, 0.62)), 3.5, 1.0)

    elif base == "rocket":
        # TORNADO SYNERGY (user doctrine, 2026-08-16) -- FIRST, because it is the only rule that
        # is time-critical. The Tornado is what MAKES a rocket-sized clump in this deck; a bundle
        # that big rarely forms on its own. Aim at the pull CENTRE, where the bodies are being
        # dragged to, not at where any one of them currently stands.
        nado = _live_nado(env)
        if nado is not None:
            _add_spot(w, env, float(nado["cx"]), float(nado["cy"]), 5.0, 1.5)
        # #50: fresh pump (exists as reward; the prior points the SAMPLER at it too).
        pump = next((u for u in enemies if u.spec.base == "elixir_collector" and u.age <= 12.0), None)
        if pump is not None:
            _add_spot(w, env, pump.x, pump.y, 4.0, 1.0)
        # #56/#57: defensive phase -> the weaker enemy princess tower.
        if env._defensive:
            alive = [t for t in eng.towers[1][:2] if t.alive]
            if alive:
                tgt = min(alive, key=lambda t: t.hp)
                _add_spot(w, env, tgt.x, tgt.y, 3.0, 1.0)
        # #35: tower + valuable support alignment (the coded rocket-combo, sampler-side).
        for t in eng.towers[1][:2]:
            if t.alive and any(u.spec.kind == "troop" and 4 <= u.spec.elixir <= 6
                               and abs(u.x - t.x) + abs(u.y - t.y) < 0.14 for u in enemies):
                _add_spot(w, env, t.x, t.y + 0.02, 3.5, 1.0)
        # #63 (tranche 2): the midladder SUPPORT WALL -- >=3 troops of cost >=3 inside one blast
        # radius, anywhere on the board, is rocket value even without tower alignment.
        heavies = [u for u in enemies if u.spec.kind == "troop" and u.spec.elixir >= 3]
        for u in heavies:
            near = [v for v in heavies if abs(v.x - u.x) + abs(v.y - u.y) < 0.12]
            if len(near) >= 3:
                cx = sum(v.x for v in near) / len(near)
                cy = sum(v.y for v in near) / len(near)
                _add_spot(w, env, cx, cy, 3.0, 1.0)
                break
        if not w:
            return None

    else:
        return None

    return list(w.items()) if w else None


# ---- WHICH card, not just where ---------------------------------------------

def _blast_group(enemies, radius: float = 0.12, min_cost: int = 3, need: int = 2):
    """The biggest cluster of enemy troops costing >= ``min_cost`` that one blast covers.

    Returns (members, cx, cy) or None. `radius` is in BOARD FRACTION (Manhattan), matching the
    existing cell rules -- a rocket's 2-tile blast on an 18x32 board.
    """
    heavies = [u for u in enemies if u.spec.kind == "troop" and u.spec.elixir >= min_cost]
    best = None
    for u in heavies:
        near = [v for v in heavies if abs(v.x - u.x) + abs(v.y - u.y) < radius]
        if len(near) >= need and (best is None or len(near) > len(best)):
            best = near
    if not best:
        return None
    return best, sum(v.x for v in best) / len(best), sum(v.y for v in best) / len(best)


def _live_nado(env):
    """An agent Tornado cast that is still gathering, with enough elixir bundled to be worth a
    rocket. Returns the watch record (it carries the pull CENTRE) or None.

    The window is deliberately short. The combo is a timing play -- "place both cards fast or the
    Rocket will miss" -- and the pull only holds bodies together for a moment, so a rocket
    nominated later would be aimed at a clump that has already walked apart.
    """
    for wnd in reversed(getattr(env, "_nado_watch", None) or ()):
        if env.eng.t - float(wnd.get("t0", 0.0)) > 2.5:
            continue
        alive = [u for u in wnd.get("pulled", ()) if u.hp > 0 and u.spec.kind == "troop"]
        if sum(u.spec.elixir for u in alive) >= 6:
            return wnd
    return None


def doctrine_cards(env) -> Optional[Dict[int, float]]:
    """{card_id: weight} prior over WHICH card to play now, or None to leave the floor uniform.

    WHY THIS EXISTS (measured 2026-08-16). The cell prior above answers "where should the rocket
    go", but nothing ever chose the rocket: 0 plays across four separate evaluations and 14,300
    training matches. Probing the reward showed why, and it is NOT that rocket is punished --
    a rocket that kills a 13-elixir support trio pays +1.0, and the tower + support 2-for-1 pays
    w_wincon x combo_mult = 2.4, on par with an X-Bow play. The problem is DISCOVERY: those
    payoffs need a precise aim on a rare board, so a uniformly-sampled rocket earns ~0.00 (or
    -0.3 into empty ground), the policy's estimate of its value never leaves zero, and it never
    reaches the states where the existing shaping would pay. A card the sampler never selects
    cannot learn from any reward, however well designed.

    So this nominates the rocket only in the situations that real play (and the coded rewards)
    agree are rocket situations. Same hard rules as the cell prior: rollout-only, ground truth,
    annealable to nothing via sim.doctrine_frac.
    """
    eng = env.eng
    enemies = _enemies(env)
    hand = set(env._hand_ids())
    w: Dict[int, float] = {}

    def _holdable(*bases):
        for i in _deck_ids(env, *bases):
            if i in hand and eng.elixir[0] >= env.specs[i].elixir:
                return i
        return None

    def _bump(card_id, v):
        if card_id is not None:
            w[card_id] = max(w.get(card_id, 0.0), float(v))

    # ---- TORNADO ----------------------------------------------------------------------------
    nid = _holdable("tornado")
    if nid is not None:
        king_asleep = not eng.towers[0][2].active
        pullable = [u for u in enemies if u.spec.kind == "troop" and not _pull_resistant(u)]
        # KING ACTIVATION. "Tornado any Miners or Hog Riders to the King Tower for an easy
        # activation" -- a third defensive tower for the rest of the match is the biggest single
        # payoff this card has.
        if king_asleep and any(u.y > 0.52 for u in pullable):
            _bump(nid, 5.0)
        # THE DEPLOY-TIMER WINDOW, which is the whole timing skill: "deploy the Tornado one second
        # before you think their tank will spawn; you want the Tornado to be pulling while the tank
        # is in its deploy timer, since it won't be walking against (and resisting) its pull", and
        # "the Tornado only lasts for one second, so the timing is a bit strict". A unit still in
        # its deploy delay is exactly that window, and nothing in the sim was aiming at it.
        if any(getattr(u, "deploy_left", 0.0) > 0.0 for u in pullable):
            _bump(nid, 4.5)
        # CLUMP for the Ice Wizard / Rocket to punish.
        if len([u for u in pullable if u.y > 0.42]) >= 2:
            _bump(nid, 3.5)
        # THE SNEAKY LOCK: our bow is up and something is sitting on it.
        bow = next((u for u in eng.units if u.team == 0 and u.spec.base == "x_bow" and u.hp > 0), None)
        if bow is not None and any(abs(u.x - bow.x) + abs(u.y - bow.y) < 0.22 for u in pullable):
            _bump(nid, 4.0)

    # ---- THE LOG ----------------------------------------------------------------------------
    lid = _holdable("the_log")
    if lid is not None:
        ground = [u for u in enemies if not u.spec.flying and u.spec.kind == "troop" and u.y >= 0.42]
        swarm = [u for u in ground if u.spec.elixir <= 3]
        if len(swarm) >= 3:
            _bump(lid, 4.0)                          # what the card is FOR
        elif len(ground) >= 1 and any(u.spec.charge_range for u in ground):
            _bump(lid, 3.5)                          # resets a charge (Battle Ram / Prince / Ram Rider)
        if any(u.spec.base == "tombstone" and u.hp <= u.spec.hp * 0.55 for u in enemies):
            _bump(lid, 4.5)                          # kills the hut AND its death skeletons
        # CYCLE USE: "Log at the bridge (if Tornado is in hand)" -- the Log is the cheap cycle card,
        # but only while the Tornado is still there to answer a swarm. Quiet board only.
        if not ground and nid is not None and eng.elixir[0] >= 8.0:
            _bump(lid, 2.0)

    # ---- ROCKET -----------------------------------------------------------------------------
    rid = _holdable("rocket")
    if rid is None:
        return w or None

    def bump(v):
        _bump(rid, v)

    # 1. FRESH PUMP. An unanswered Elixir Collector out-economies a control deck; the reward
    #    already pays full win-condition credit for killing one inside its window.
    if any(u.spec.base == "elixir_collector" and u.age <= env.pump_window for u in enemies):
        bump(4.0)

    # 2. THE 2-FOR-1. A 4-6 elixir support body sitting next to a live princess tower is the
    #    classic "rocket the Musketeer behind the tower" -- tower chip AND a card-advantage kill.
    for t in eng.towers[1][:2]:
        if not t.alive:
            continue
        if any(u.spec.kind == "troop" and not u.spec.building_only and 4 <= u.spec.elixir <= 6
               and abs(u.x - t.x) + abs(u.y - t.y) < 0.14 for u in enemies):
            bump(4.0)

    # 3. A BUNDLE worth the 6 elixir. Guides put the bar at "troops typically worth 4 or more
    #    elixir", and warn against spending it on lone cheap bodies -- so this counts the elixir
    #    actually covered rather than the number of bodies: three Skeletons are not a rocket.
    grp = _blast_group(enemies)
    if grp is not None:
        members, _, _ = grp
        if sum(u.spec.elixir for u in members) >= 6:
            bump(3.5 if len(members) >= 3 else 3.0)

    # 4. TORNADO SYNERGY -- the reason clumps exist in this deck at all. A rocket-sized bundle
    #    rarely forms by itself; the Tornado MAKES one, and the follow-up has to be immediate
    #    ("place both cards fast or the Rocket will miss"). While a cast is still pulling, the
    #    rocket is the intended second half of the combo.
    if _live_nado(env) is not None:
        bump(5.0)

    # 5. THE TIEBREAK RACE (user doctrine, 2026-08-16). An icebow match that reaches overtime is
    #    decided by whose LOWEST princess tower is lower, so once the bow is not breaking through,
    #    rocket-cycling the weaker enemy tower is the win condition -- "launch a Rocket in the
    #    final ten seconds to assure your victory". Only nominate while we are actually behind on
    #    that race or level with it; if our lowest tower is already the healthier one, chipping is
    #    optional and the elixir is better held for defence.
    if env._defensive or eng.t >= env._double_time:
        ours = [t for t in eng.towers[0][:2] if t.alive]
        theirs = [t for t in eng.towers[1][:2] if t.alive]
        if ours and theirs:
            my_low = min(t.hp for t in ours)
            op_low = min(t.hp for t in theirs)
            if op_low >= my_low:                     # losing or level on the tiebreak
                bump(4.5)

    # 6. NO CHEAPER ANSWER. A heavy threat is over the river and nothing else in hand answers it.
    #    Rocket is not the efficient counter, but "acceptable ... if you have no other effective
    #    answer in your hand" -- a bad trade beats taking the whole push.
    threat = _deepest_ground_threat(env)
    if threat is not None and threat.spec.elixir >= 4 and threat.y > 0.52:
        others = [i for i in env._hand_ids()
                  if i != rid and i >= 0 and eng.elixir[0] >= env.specs[i].elixir
                  and env.specs[i].kind != "spell"]
        if not others:
            bump(3.0)

    return w or None
