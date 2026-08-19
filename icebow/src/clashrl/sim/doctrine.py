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

import math

from .. import card_threat
from .. import threat_value
from .engine import _TILES_X, _TILES_Y, _TORNADO_RADIUS, build_spec


def _tower_level(env) -> int:
    return int(env.cfg.get("env", "my_tower_level", default=15) or 15)


def _enemy_level(env) -> int:
    """The level the opponent's cards are assumed to sit at, for the ignore-cost model."""
    return int(env.cfg.get("sim", "enemy_card_level", default=11) or 11)

# ---- placement geometry -----------------------------------------------------
#
# The fundamentals research (2026-08-16) produced two placement rules that every guide states and
# nothing here implemented. Both are GEOMETRY, so they are computed from the engine's own tower
# positions and ranges rather than transcribed as magic tile numbers -- which also let the first
# one be checked, and it failed.


def _tiles(ax: float, ay: float, bx: float, by: float) -> float:
    """Distance in TILES between two board points (the board is 18 x 32 tiles, not square)."""
    return math.hypot((ax - bx) * _TILES_X, (ay - by) * _TILES_Y)


def _my_princesses(env):
    return [t for t in env.eng.towers[0][:2] if getattr(t, "hp", 0) > 0]


def _double_cover(env, x: float, y: float) -> bool:
    """Do BOTH our princess towers reach a unit standing here?

    This is the whole point of the centre pull -- "troops stuck in the centre take damage from the
    building AND both towers" -- and it is a hard geometric fact, so it is measured, not guessed.
    MEASURED against the engine at its configured 8.0-tile tower reach: the centre double-cover
    zone begins **3.69 tiles from the river** (y = 0.6154 at x = 0.50), close to the guides' folk
    rule of "four tiles from the river, dead centre" without being identical to it -- their number
    is for the real game's 7.5-tile towers, where the same computation gives 4.40.

    It also showed the existing Tesla pull spot (0.48, 0.585) is 8.51 tiles from BOTH princess
    towers, outside the reach of each, so the rule named after this benefit was not obtaining it.
    That gap is the reason to compute the rule instead of transcribing the tile number.
    """
    rng = float(env.cfg.get("sim", "tower_range", default=7.5) or 7.5)
    towers = _my_princesses(env)
    return len(towers) >= 2 and all(_tiles(x, y, t.x, t.y) <= rng for t in towers)


def _spell_pair_risk(env, x: float, y: float) -> bool:
    """Could ONE spell the opponent is known to hold hit this cell AND one of our towers?

    A circle of radius r covers two points only if they are within 2r of each other, so this is
    exact given the radius. Radii come from the engine's own specs (rocket 2.0, fireball 2.5,
    lightning/poison 3.5 tiles) rather than a guide's table, so they cannot drift apart.

    This is why placements are quoted as "7-2 avoids Rocket value on the tower and the building":
    a structure parked next to a tower turns their spell into a two-for-one for free.
    """
    known = _opp_cards(env)
    if not known:
        return False
    towers = _my_princesses(env)
    if not towers:
        return False
    for base in known:
        try:
            spec = build_spec(env.db, str(base), 11)
        except Exception:  # noqa: BLE001
            continue
        if spec.kind != "spell" or not spec.spell_radius:
            continue
        reach = 2.0 * float(spec.spell_radius)
        if any(_tiles(x, y, t.x, t.y) <= reach for t in towers):
            return True
    return False


#: how hard the two geometric rules push. Deliberately mild -- they REWEIGHT the spots a rule
#: already proposed rather than moving them, so a tuned rule keeps its intent and the sampler
#: still sees every option.
_DOUBLE_COVER_BONUS = 1.4
_SPELL_RISK_PENALTY = 0.6


def _shape_placement(w: Dict[int, float], env, base: str) -> None:
    """Apply the two geometric rules to a finished cell prior, in place.

    Only for STRUCTURES. A troop is gone in seconds and its placement is about the engagement;
    a building or an X-Bow stands there for its whole lifetime, which is what makes both the
    double-cover payoff and the one-spell-two-targets risk worth paying for.
    """
    if not w or base not in ("tesla", "x_bow", "bomb_tower", "cannon", "tombstone"):
        return
    acts = env.actions
    gw = int(acts.gw)
    for cell in list(w):
        cx, cy = acts.cell_center(int(cell) % gw, int(cell) // gw)
        if _double_cover(env, cx, cy):
            w[cell] *= _DOUBLE_COVER_BONUS
        if _spell_pair_risk(env, cx, cy):
            w[cell] *= _SPELL_RISK_PENALTY


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


# ---- Tornado king activation ------------------------------------------------
#
# WHY THE WINDOW IS ALWAYS SMALL. Our princess tower centre is 6.52 tiles from the king's, an
# attacker standing on the arena side of it is ~8 tiles out, and the pull radius is 5.5 -- so the
# cast has to sit near the king AND still reach the attacker, which is the user's rule that the
# troop wants to be near the EDGE of the pull. The mechanic itself is the retarget: dragging a
# unit off what it was hitting breaks its lock (see _tick_zones), and it re-picks the king if the
# king has become the nearest building. It does NOT have to be dragged onto the king.
#
# Heavy building-targeters on a lane march (Giant, Golem, Battle Ram) still do not activate, and
# that agrees with the guides rather than contradicting them: those want a building "in the 4-3
# placement" pulling them centre first, a two-card setup no single cast expresses.
def _king_spots(env, u):
    """Candidate Tornado casts that drag ``u`` into our king. MIRRORED BY CONSTRUCTION.

    The arena is exactly symmetric -- left and right princess x sum to 1.000000 = 2 x king.x, and
    the 18-column grid mirrors exactly -- so any rule that comes out asymmetric is a bug in the
    rule. An earlier version stored a measured per-lane table and looked asymmetric for two
    compounding reasons, both mine:

      * the sweep grid ran dx from -3.0 to +1.0, which covers the left lane's working region but
        CLIPS the right lane's, and
      * whole- and half-tile offsets land exactly on tile boundaries, where the snap's floor()
        breaks ties the same way on both sides -- so mirrored inputs land on non-mirrored tiles
        and the measurement showed a consistent half-tile bias.

    Re-swept on a symmetric grid the two sides agree: the same number of working spots, the same
    depth, and a single mirrored |dx| = 0.5 activates from either lane. So the offset is stored
    once and its sign taken from which side of the king the attacker is on.

    Two candidates are offered, not one. The FRONT-OF-KING spot is where a marching attacker gets
    caught; the ON-LINE spot -- on the segment from the attacker to the king -- is what works for
    troops that arrive AT the tower (Miner, Balloon) and generalises to any melee attacker,
    including the non-win-condition ones, which is the whole point of computing it rather than
    tabulating win conditions.
    """
    kt = env.eng.towers[0][2]
    side = -1.0 if u.x < kt.x else 1.0
    out = [(kt.x + side * 0.5 / 18.0, kt.y - 4.5 / 32.0)]
    dxt, dyt = (u.x - kt.x) * 18.0, (u.y - kt.y) * 32.0
    d = (dxt * dxt + dyt * dyt) ** 0.5
    if d > 1e-6:
        # as close to the king as the pull can still reach the attacker from, capped where the
        # calibration sweep showed activations (3.0-4.0 tiles for tower-arrivals)
        stand = min(4.0, max(3.0, d - _TORNADO_RADIUS + 0.3))
        if d - stand <= _TORNADO_RADIUS:
            out.append((kt.x + (dxt / d) * stand / 18.0, kt.y + (dyt / d) * stand / 32.0))
    return out


def llm_state_key(env) -> str:
    """Coarse bucket an LLM-proposed rule generalises over.

    Deliberately lossy: a rule should cover a FAMILY of boards, not one frame, and the table stays
    small enough to read. Shared with tools/llm_doctrine.py so the key that was verified is exactly
    the key that gets looked up -- if these two ever drift, every verified rule silently stops
    matching, which is the failure mode a shared function exists to prevent.
    """
    eng = env.eng
    foes = [u for u in eng.units if u.team == 1 and u.hp > 0 and u.spec.kind == "troop"]
    deep = sum(1 for u in foes if u.y > 0.52)
    # PER-BODY SHARE, not the card price per body. Summing the full cost for every unit made a
    # Goblin Gang read as 15 elixir and a Skeleton Army as 45, and since the bucket saturates at
    # worth_4 every swarm board looked identical to a genuine heavy push -- so a rule learned
    # against three Skeletons would be served up against a Golem. Same accounting the trade
    # ledger uses.
    worth = sum(float(u.spec.elixir) / max(1, u.spec.squad_count or u.spec.count) for u in foes)
    return "|".join([
        "ot" if eng.t >= env._double_time else ("x2" if eng.t >= 120 else "x1"),
        "king_%s" % ("asleep" if not eng.towers[0][2].active else "awake"),
        "deep_%d" % min(3, deep),
        "worth_%d" % min(4, int(worth // 4)),
        "elx_%d" % min(10, int(eng.elixir[0])),
    ])


_LLM_RULES = None


def _llm_rules(env):
    """Engine-verified LLM proposals, loaded once. Empty when the file is absent or disabled.

    Every entry in this file beat "hold the card" in the engine over repeated seeds before it was
    written -- see tools/llm_doctrine.py. Nothing a model merely asserted gets in, which matters
    because the best local model scored 6/10 on this project's own doctrine eval and every model
    tested made the same X-Bow-into-a-committed-push mistake the reward ledger was separately
    found to be paying for.
    """
    global _LLM_RULES
    if _LLM_RULES is None:
        _LLM_RULES = {}
        try:
            if env.cfg.get("sim", "llm_doctrine", default=True):
                import json
                from pathlib import Path
                # parents[3], not [2]: this module sits at src/clashrl/sim/, one deeper than
                # cards.py, so [2] resolves to src/ and the file is silently never found.
                p = Path(__file__).resolve().parents[3] / "config" / "llm_doctrine.json"
                if p.exists():
                    _LLM_RULES = json.loads(p.read_text(encoding="utf-8")).get("rules") or {}
        except Exception:  # noqa: BLE001
            _LLM_RULES = {}
    return _LLM_RULES


def _my_bow(env):
    """Our standing X-Bow, or None. The one asset in this deck worth defending FOR ITS OWN SAKE."""
    return next((u for u in env.eng.units
                 if u.team == 0 and u.spec.base == "x_bow" and u.hp > 0), None)


#: How close an enemy has to be before it counts as coming for the bow rather than the tower.
_BOW_GUARD_TILES = 5.5
#: One placement-grid row, normalised. Any offset smaller than this is not representable.
_ROW = 1.0 / 24.0
#: Shallowest deployable y on our side (ActionSpace.min_own_gy = row 13 of 24).
_OWN_FRONT = 13.5 / 24.0


def _own_half(y: float) -> float:
    """Clamp to a row we can actually deploy on. Without it, "behind the bow" walked off our
    half whenever the bow sat near the bridge, and the prior was silently masked away."""
    return min(max(float(y), _OWN_FRONT), 23.5 / 24.0)


def _bow_attackers(env, bow):
    """Enemy troops close enough to the bow to be threatening it, nearest first.

    A bow that fires for its whole lifetime is worth roughly a tower; one that dies at three
    seconds is six elixir gifted. So "what is walking at my bow" is a different question from
    "what is walking at my tower", and until now nothing asked it.
    """
    out = [u for u in _enemies(env)
           if u.spec.kind == "troop" and _tiles(u.x, u.y, bow.x, bow.y) <= _BOW_GUARD_TILES]
    return sorted(out, key=lambda u: _tiles(u.x, u.y, bow.x, bow.y))


def _bow_defence_cells(env, base: str, w: Dict[int, float]) -> bool:
    """Placements that keep a standing X-Bow firing. True if a rule fired.

    The roles, and why each one goes where it goes (DOCTRINE.md 2, "internal synergies"):

      knight     -- IN FRONT, one row toward the threat. He is the bodyguard: the answer walking
                    at the bow hits him instead, and the evo takes 60% less while walking.
      skeletons  -- ON the attacker. Three bodies on a distracted single-target melee kill it
                    fast, and even losing them buys the bow two or three more shots.
      ice_wizard -- BEHIND the bow, offset. He is never the kill; he is the multiplier, and he
                    has to be out of the one spell that would take him and the bow together.
      tesla      -- between the bow and the threat, pulling. It survives, which is the whole
                    reason it is the answer to something committed.
    """
    bow = _my_bow(env)
    if bow is None:
        return False
    threats = _bow_attackers(env, bow)
    if not threats:
        return False
    t = threats[0]
    # OFFSETS MUST CLEAR A GRID ROW. The placement grid is 24 rows over the board, so one row is
    # 0.0417 normalised (1.33 tiles) -- the natural "one row in front of the bow" written as 0.04
    # quantises straight back onto the bow's own cell and the geometry silently vanishes. Every
    # offset here is therefore at least _ROW.
    toward = _ROW if t.y > bow.y else -_ROW          # one row from the bow, on the threat's side
    if base == "knight":
        _add_spot(w, env, bow.x, _own_half(bow.y + toward), 4.0, 1.0)
        return True
    if base == "skeletons":
        _add_spot(w, env, t.x, _own_half(t.y), 4.0, 1.5)      # centre + ring IS the surround
        return True
    if base == "ice_wizard":
        # BEHIND means deeper in OUR half -- always +y, never "opposite the threat", which put him
        # on the enemy side of the river when the attacker had already walked past the bow.
        # Offset sideways too: directly behind is inside one Fireball of the bow.
        side = 0.06 if bow.x < 0.48 else -0.06
        _add_spot(w, env, bow.x + side, _own_half(bow.y + 2 * _ROW), 4.0, 1.0)
        return True
    if base == "tesla":
        _add_spot(w, env, (bow.x + t.x) / 2.0, _own_half(bow.y + toward), 4.0, 1.2)
        return True
    return False


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
    """(cell, weight) prior for playing ``card_id``, with the geometric rules applied.

    A thin wrapper on purpose. The rule body below has SIX exit points, and shaping each one
    separately is exactly the kind of edit that silently misses a branch -- so the shaping happens
    once, here, where nothing can route around it.
    """
    got = _doctrine_cells_rules(env, card_id)
    if not got:
        return got
    keys = env.deck_keys
    base = keys[card_id][:-4] if keys[card_id].endswith("_evo") else keys[card_id]
    w = dict(got)
    _shape_placement(w, env, base)
    return list(w.items())


def _doctrine_cells_rules(env, card_id: int) -> Optional[List[Tuple[int, float]]]:
    """The hand-written rule table. See :func:`doctrine_cells` for the shaping applied on top."""
    keys = env.deck_keys
    if not (0 <= card_id < len(keys)):
        return None
    base = keys[card_id][:-4] if keys[card_id].endswith("_evo") else keys[card_id]
    w: Dict[int, float] = {}
    eng = env.eng
    enemies = _enemies(env)
    threat = _deepest_ground_threat(env)
    king_asleep = not eng.towers[0][2].active

    # DEFEND THE BOW FIRST. A standing X-Bow is the deck's whole win condition and it cannot
    # defend itself; the plays that keep it alive are placements RELATIVE TO IT, which none of the
    # threat-relative rules below express. Checked before them so the bodyguard beats the generic
    # body-block whenever both would fire.
    if _bow_defence_cells(env, base, w):
        return list(w.items())

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
        # DO NOT STEAL A LIVE KING ACTIVATION (SS2.2, Hunter CR naming it his own mistake: his
        # Tesla sniped the very unit that was about to wake his King Tower -- "if I didn't put that
        # Tesla, we would have had king tower... I probably should have put it one higher"). A king
        # activation is a permanent, game-long defensive asset; one building's chip is not. So
        # while the king is ASLEEP and a ground attacker is already deep enough to wake it, the
        # Tesla moves one placement ROW toward the river (smaller y = away from the king), out of
        # the line where it would kill the activator first. One ROW, not one tile: the grid is 24
        # rows, so a sub-row nudge quantises back to the same cell and changes nothing.
        if king_asleep and any(u.hp > 0 and not u.spec.flying and u.y > 0.62 for u in enemies):
            y -= _ROW
        _add_spot(w, env, 0.48, y, 4.0, 1.5)
        _add_spot(w, env, 0.44, y, 1.5, 0.5)
        _add_spot(w, env, 0.52, y, 1.5, 0.5)
        # THE DOUBLE-COVER SPOT, which the band above does not reach. Measured: (0.48, 0.585) sits
        # 8.51 tiles from BOTH princess towers, outside the 8.0 reach of each -- so the rule named
        # for the centre pull was collecting the pull and none of the crossfire that is supposed to
        # pay for it. Coverage starts at y = 0.615 (3.69 tiles from the river).
        #
        # Added ALONGSIDE rather than replacing it, at a comparable weight, because the two trade
        # against each other in a way this cannot settle from geometry: deeper buys both towers,
        # shallower stops the push further from the tower. Both are sampled and the reward decides.
        # Not offered against an EARTHQUAKE deck, where the whole point of the shallow spot is to
        # sit above the region their spell farms.
        if "earthquake" not in _opp_cards(env):
            _add_spot(w, env, 0.50, 0.645, 3.5, 1.2)

    elif base == "x_bow":
        if env._defensive:
            # THE CENTRAL LESSON (DOCTRINE_RESEARCH.md SS3, Hunter CR): NEVER place a mid-map or
            # defensive X-Bow against a deck holding Rocket. His stated chain is: they rocket the
            # bow (six elixir lost for nothing) -> they rocket your tower -> you rocket back -> the
            # resulting deficit means you never get a bow lock all game.
            #
            # This is the case the reward's `xbow_into_push` term cannot see: that term explicitly
            # EXEMPTS a defensive bow ("behind xbow_front it IS the answer, a second pull
            # building"), and it triggers on a committed PUSH, whereas this triggers on the
            # opponent's DECK. That term measures -276.0 over 69 fires and is never once positive,
            # so the forward case is already priced; this closes the other half.
            #
            # Suppressed rather than re-weighted: "never" is the doctrine, and a weaker spot would
            # still be sampled.
            if "rocket" not in _opp_cards(env):
                _add_spot(w, env, 0.48, 0.55, 4.0, 1.5)      # #56: defensive bow, centre band
        else:
            # #53/#47: behind-bridge lock spots. Opposite lane of the enemy's committed mass
            # (the punish rule); EDGE column vs rocket decks so their rocket can't clip tower+bow.
            edge = "rocket" in _opp_cards(env)
            left, right = (0.16, 0.84) if edge else (0.26, 0.73)
            mass_left = sum(u.spec.elixir for u in enemies if u.x < 0.5)
            mass_right = sum(u.spec.elixir for u in enemies if u.x >= 0.5)
            wl, wr = (4.0, 2.0) if mass_right > mass_left else (2.0, 4.0) if mass_left > mass_right else (3.0, 3.0)
            # WHICH TOWER IS WORTH SHOOTING beats which lane is emptier. Live overtime, one tower
            # down each side: several technically perfect offensive bows, every one of them in the
            # lane whose enemy princess was ALREADY DESTROYED -- six elixir aimed at nothing, since
            # the bow can then only fall through to the far tankier king.
            #
            # Applied as a multiplier on the lane weights rather than a new spot, so the punish
            # rule above still chooses BETWEEN live lanes and only loses its say when one of them
            # has nothing left to shoot at.
            etw = env.eng.towers[1]
            l_alive = etw[0].hp > 0 if len(etw) > 0 else True
            r_alive = etw[1].hp > 0 if len(etw) > 1 else True
            if l_alive != r_alive:                          # exactly one down: never bow the dead lane
                wl, wr = (6.0, 0.0) if l_alive else (0.0, 6.0)
            elif l_alive and r_alive and len(etw) > 1:
                # Both up: concentrate on the WEAKER one so successive bows work toward a single
                # kill instead of splitting chip across two towers.
                full = max(etw[0].hp, etw[1].hp) or 1.0
                if etw[1].hp < etw[0].hp - 0.10 * full:
                    wr *= 1.8
                elif etw[0].hp < etw[1].hp - 0.10 * full:
                    wl *= 1.8
            if wl > 0.0:
                _add_spot(w, env, left, 0.50, wl, 1.0)
            if wr > 0.0:
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
            kt = eng.towers[0][2]
            # PER-TROOP KING-ACTIVATION SPOTS, MEASURED against this engine rather than
            # transcribed from a guide's tile pictures -- the engine is what the policy has to
            # satisfy, and the two do not agree (see the fidelity note in _KING_SPOTS).
            # The old single spot (king.x, king.y - 1.5 tiles) activates NOTHING: a hog on the
            # left princess tower sits 6.5 tiles from the king, past the 5.5-tile pull radius,
            # so a cast centred on the king never even catches it. The working offsets sit ~4.5
            # tiles IN FRONT of the king and slightly toward the lane.
            # ANY pullable attacker will do it, not just the win conditions -- the user's note, and
            # the reason this is computed per unit. Prefer the one already deepest into our half.
            # ANY pullable attacker will do it, not just the win conditions -- the user's note, and
            # why the spots are computed per unit. Prefer the one deepest into our half.
            deep = max(bound, key=lambda u: u.y)
            for i, (sx, sy) in enumerate(_king_spots(env, deep)):
                _add_spot(w, env, sx, sy, 5.0 if i == 0 else 4.0, 1.5)
        clump = [u for u in enemies if u.y > 0.42 and not _pull_resistant(u)]
        if len(clump) >= 2:
            cx = sum(u.x for u in clump) / len(clump)
            _add_spot(w, env, 0.48 + (cx - 0.48) * 0.5, 0.55, 3.0, 1.0)
        # TORNADO-BACK, the standard air-swarm answer (SS2.3): pull the flock BACKWARD -- deeper
        # into our half, toward our own tower -- so the tower re-targets it. The generic clump rule
        # above aims at the fixed centre band, which for a flock already past that band is FORWARD
        # of them: it drags them away from the guns that are supposed to kill them. For air swarms
        # the pull DIRECTION, not the clump centre, is the entire play.
        air = [u for u in enemies if u.spec.flying and u.y > 0.55 and not _pull_resistant(u)]
        if len(air) >= 2:
            ax = sum(u.x for u in air) / len(air)
            ay = max(u.y for u in air)
            tw = min(_my_princesses(env), key=lambda t: abs(t.x - ax), default=None)
            if tw is not None:
                # aim BEHIND the flock, between it and our tower, so the pull walks it onto guns
                _add_spot(w, env, (ax + tw.x) / 2.0, min(0.74, ay + _ROW), 4.0, 1.2)
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


def _hold_the_building(env, w: Dict[int, float], quiet: bool) -> Dict[int, float]:
    """Strip DEFENSIVE-BUILDING nominations from a quiet board, whatever proposed them.

    A post-filter rather than a condition inside each rule, because the nomination that actually
    caused the reported behaviour came from the auto-generated LLM rule table, not from a
    hand-written rule -- and any future rule can make the same mistake. Enforcing it once, at the
    exit, means no rule can route around it.

    Same condition as the reward's ``_building_waste``, deliberately: the prior must not nominate
    what the reward then charges for. The X-Bow is exempt via the siege flag -- it is a building
    by kind but it is our win condition.
    """
    if not quiet or not w:
        return w
    if not env._opp_holds_wincon():
        return w                       # nothing left to save it for
    return {c: v for c, v in w.items()
            if not (env.specs[c].kind == "building" and not env.specs[c].siege)}


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

    # ---- FUNDAMENTALS: IS THERE ANYTHING TO ANSWER AT ALL? ----------------------------------
    # This tier sits ABOVE every counter rule below, and it is the one that was missing. All of
    # them answer "what beats X"; none asked "is X worth beating", so the policy spent cards on a
    # lone Skeletons -- which costs 0.4% of a Princess Tower if ignored completely
    # (clashrl.threat_value, computed from our own card DB at our tower level). Every guide states
    # the principle -- "if a card don't solve a situation or don't affect the battle, don't play
    # it", "don't defend single weak units when accepting 100-200 damage costs less elixir" -- but
    # only as prose, so nothing could act on it.
    #
    # Threats ADD: three ignorable units arriving together are one real push, which is why this
    # triages the GROUP and not each body (reading the push as a whole is the whole skill).
    #
    # The prior REPLACES the exploration floor over the cards it names, so nominating the right
    # card here is also how a wrong one gets suppressed.
    committed = [u for u in enemies if u.y > 0.42 and u.spec.kind != "spell"]
    # An EMPTY board is the strongest version of "nothing to answer", not a special case to skip:
    # leaving it out is how a Tesla got nominated into open grass, which is exactly the play the
    # user reported (planted well, dead of old age before their win condition arrived).
    cost = threat_value.group_ignore_frac(
        env.db, [u.spec.base for u in committed],
        tower_level=_tower_level(env), enemy_level=_enemy_level(env)) if committed else 0.0
    quiet = cost < threat_value.IGNORE_FRAC
    if quiet:
        # NOT a defence situation. The tower handles this by itself, so the elixir belongs in the
        # win condition -- "with a quiet enemy board and 6+ elixir the play is the X-Bow;
        # otherwise cycle the cheapest card or hold".
        #
        # HOLD is the default, and the thresholds are the reason. This deck is 3.5 cycle, not 2.9:
        # banking is correct play, so a cycle card is nominated only near the LEAK point where
        # holding starts throwing elixir away. Nominating it at 2 elixir would have taught the
        # opposite of the deck's own doctrine.
        if eng.elixir[0] >= 6.0:
            _bump(_holdable("x_bow"), 4.0)
        if eng.elixir[0] >= 8.0:
            cheap = min((i for i in hand if eng.elixir[0] >= env.specs[i].elixir),
                        key=lambda i: env.specs[i].elixir, default=None)
            _bump(cheap, 1.5)
        # NO early return. The rules below also cover plays keyed off THEIR half -- rocketing a
        # fresh Elixir Collector, the support parked behind their tower, the overtime tiebreak --
        # and returning here made every one of them unreachable whenever our own half was quiet,
        # which is precisely when those plays are correct. The defensive rules below cannot fire
        # on a quiet board anyway: each needs an enemy near our side to trigger at all.

    # ---- TESLA IS FOR THEIR WIN CONDITION ---------------------------------------------------
    # It pulls and it SURVIVES, which is exactly what a win condition needs answering with, and
    # it has a 30 s lifetime -- so one spent early is simply not there when the Hog/Giant/Balloon
    # arrives. The user's report: a Tesla planted in a good spot on an EMPTY board, dead by the
    # time the real push came. The reward now prices that (env._building_waste); this is the
    # other half -- when a win condition IS on the board, Tesla outranks everything else.
    wincons = [u for u in enemies
               if u.y > 0.30 and card_threat.profile(env.db, u.spec.base).win_condition]
    if wincons:
        _bump(_holdable("tesla"), 6.0)                # above every other rule in this table
        # and the cheap support that buys the building time to do its work
        _bump(_holdable("skeletons"), 3.0)
        _bump(_holdable("ice_wizard"), 3.0)

    # ---- DEFEND THE STANDING BOW ------------------------------------------------------------
    # The bow is the deck's tower damage, and an unprotected one dies to whatever they send at it
    # -- six elixir for a few shots. So when it is up and something is walking at it, nominate the
    # cards that keep it firing, by role: knight tanks the answer, tesla holds and survives,
    # skeletons distract, ice wizard slows the whole group. Weighted at the top of the table
    # because losing the bow loses the match plan, not just the exchange.
    bow = _my_bow(env)
    if bow is not None:
        attackers = _bow_attackers(env, bow)
        if attackers:
            melee = [u for u in attackers if not u.spec.charge_range and (u.spec.reach or 0.0) <= 2.0]
            _bump(_holdable("knight"), 4.5 if melee else 3.0)     # the bodyguard
            _bump(_holdable("skeletons"), 4.0)                    # distract / surround
            _bump(_holdable("ice_wizard"), 3.5 if len(attackers) >= 2 else 2.5)
            _bump(_holdable("tesla"), 4.0 if len(attackers) >= 2 else 3.0)

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

    # ---- LLM-PROPOSED, ENGINE-VERIFIED ------------------------------------------------------
    # Weighted BELOW the hand-written rules on purpose. Those were derived from the deck guides
    # and checked against the engine by hand; these cleared an automated gate, which is a lower
    # bar. Where both fire, the hand-written rule should win the sampler.
    rules = _llm_rules(env)
    if rules:
        hit = rules.get(llm_state_key(env))
        if hit:
            cid = _holdable(str(hit.get("card", "")))
            if cid is not None:
                _bump(cid, 2.5)

    # ---- ROCKET -----------------------------------------------------------------------------
    rid = _holdable("rocket")
    if rid is None:
        return _hold_the_building(env, w, quiet) or None

    def bump(v):
        _bump(rid, v)

    # 1. FRESH PUMP. An unanswered Elixir Collector out-economies a control deck; the reward
    #    already pays full win-condition credit for killing one inside its window.
    #    TWO GATES (DOCTRINE_RESEARCH.md SS1.1 R5, Hunter CR): (a) STOP rocketing pumps once
    #    overtime starts -- the tower is worth more than the tempo by then; (b) skip it when the
    #    board threat means we cannot defend at post-rocket elixir. He declined a pump rocket at
    #    7 elixir for exactly (b), and the bot's `spell_waste` term (-23.7, never positive) is
    #    what casting into that state looks like from the reward's side.
    if any(u.spec.base == "elixir_collector" and u.age <= env.pump_window for u in enemies):
        committed = [u for u in enemies if u.y > 0.42 and u.spec.kind != "spell"]
        threat_cost = threat_value.group_ignore_frac(
            env.db, [u.spec.base for u in committed],
            tower_level=_tower_level(env), enemy_level=_enemy_level(env)) if committed else 0.0
        if eng.t < env._double_time and threat_cost < threat_value.MUST_ANSWER_FRAC:
            bump(4.0)

    # 2. THE 2-FOR-1. A 4-6 elixir support body sitting next to a live princess tower is the
    #    classic "rocket the Musketeer behind the tower" -- tower chip AND a card-advantage kill.
    for t in eng.towers[1][:2]:
        if not t.alive:
            continue
        # LETHALITY CHECK (SS1.1 R4). "Rocket the support next to the tower" is a REMOVAL play,
        # so the body must actually die: hp under the rocket's damage and no shield soaking it.
        # Without this the rule fired on Royal Giants and shielded 4-costs, where 1484 does not
        # come close to a kill -- the verifier caught the pool generalising "4+ elixir supports
        # will be one-shot", which is false for exactly those cards.
        rk_dmg = float(env.specs[rid].spell_dmg or 0.0)
        if any(u.spec.kind == "troop" and not u.spec.building_only and 4 <= u.spec.elixir <= 6
               and u.hp <= rk_dmg and u.shield_left <= 0.0 and u.spec.shield_hp <= 0.0
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

    # 6. CYCLE STATE, NOT ELIXIR MATH (DOCTRINE_RESEARCH.md SS1.1 R1 -- the single highest-value
    #    rule in the whole corpus, and the fix for the MEASURED failure: rocket was played 2 times
    #    in 1288 plays, 0.2%).
    #
    #    This gate used to require that NOTHING else in hand was affordable, which is a board state
    #    that essentially never occurs -- so the trigger a professional actually uses was
    #    unreachable and the rule was dead code. Hunter CR states it as a HAND condition, not a
    #    value judgement: "the trigger for rocketing a support troop is CYCLE STATE, not elixir
    #    math -- rocket it when your normal answers (Knight, Tesla) are not in hand." That is
    #    observable, which matters here: the prior has been nominating rocket in rollouts for
    #    14,300+ matches without the policy learning to value it, because the payoff is too rare
    #    and too precise to find by sampling. A hand condition can be learned.
    #
    #    R3, THE OVERSPEND TEST, is the same rule from the other side and is the corpus's most
    #    on-point observation -- Hunter naming his own worst play of a match as a rocket he did
    #    NOT cast: "I had to drop nine elixir on that prince. If I would have just rocketed..."
    #    So: if the cheapest sufficient answer in hand costs 7+ chained elixir, the 6-elixir
    #    rocket IS the cheap answer, not the expensive one.
    threat = _deepest_ground_threat(env)
    if threat is not None and threat.spec.elixir >= 4 and threat.y > 0.52:
        # N3 (SS1.2): vs a Giant Skeleton the BUILDING is the answer, not the spell. Hunter's
        # measured error of one video -- Rocket+Log instead of Tesla, tower lost, and he named
        # Tesla-on-zero-elixir as the correct play. Veto rather than a negative weight, because
        # the building rule below should win outright.
        veto = threat.spec.base == "giant_skeleton" and _holdable("tesla") is not None
        # N6: a LONE Sparky has a cheaper answer -- Tornado it into the Knight so the tower helps.
        # The quote is "rocket the sparkies anytime he puts value WITH them", i.e. gated on the
        # opponent adding accompanying investment; the pool's "on sight" reading was the opposite.
        if threat.spec.base == "sparky":
            supported = sum(1 for u in enemies
                            if u is not threat and u.spec.kind == "troop" and u.y > 0.42) >= 1
            if not supported and _holdable("tornado") is not None and _holdable("knight") is not None:
                veto = True
        if not veto:
            answers = [i for i in env._hand_ids()
                       if i != rid and i >= 0 and eng.elixir[0] >= env.specs[i].elixir
                       and env.specs[i].kind != "spell"]
            # THE DESIGNATED ANSWERS for a committed body in this deck are the Knight (body-block)
            # and the Tesla (pull + survive). Ice Wizard and Skeletons shape a push; they do not
            # stop a 4+ elixir threat on their own, which is why they do not count here.
            has_designated = (_holdable("knight") is not None or _holdable("tesla") is not None)
            if not has_designated:
                bump(4.0)                       # R1: the cheap answers are out of rotation
            elif not answers:
                bump(3.0)                       # the original last-resort case
            else:
                # R3: everything affordable is chip-sized relative to the threat, so stopping it
                # means chaining several cards. 7+ elixir of chaining loses to a 6-elixir rocket.
                cheapest_stack = sum(sorted(float(env.specs[i].elixir) for i in answers)[:2])
                if cheapest_stack >= 7.0:
                    bump(3.5)

    return _hold_the_building(env, w, quiet) or None
