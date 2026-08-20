"""Card -> strategic threat profile (the detector <-> attributes bridge).

Turns a DETECTED card class name (as produced by the board detector, including the
``_evo`` / ``_hero`` / ``_ability`` / ``_aoe`` taxonomy suffixes from
``config/detect_classes.yaml``) into a compact, identity-grounded threat profile
derived from the card knowledge base (:class:`clashrl.cards.CardDB`): whether it is
a win condition, a siege building, a spell, flying, a swarm, a tank, etc., plus the
numbers (elixir / hitpoints / dps / tower damage) a counter decision needs.

This is the stable, policy-independent FOUNDATION for the planned perception
upgrade: once the detector reliably names enemy cards, these profiles will feed
identity-grounded threat features into the observation so the policy can learn to
COUNTER using its own hand's attributes + the threat's known attributes -- instead
of the coarse pixel heuristics in :mod:`clashrl.threats`. Nothing here touches the
policy or the observation yet; :func:`roles_report` (``run.py card-roles``) just
lets you review the derived tagging and spot cards that still need curating.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np
import yaml

from .cards import CardDB, _key, load as load_cards

# Detection-taxonomy suffixes appended to a base card key (see config/detect_classes.yaml).
_SUFFIXES = ("_evo", "_hero", "_ability", "_aoe")


def base_key(name: str) -> str:
    """Base card key for a detected class name, stripping detection suffixes
    (``tesla_evo`` / ``knight_hero`` / ``skeleton_king_ability`` / ``fireball_aoe`` -> base).
    Stacked suffixes fold FULLY (``knight_hero_ability`` -> ``knight``)."""
    k = _key(name)
    changed = True
    while changed:
        changed = False
        for suf in _SUFFIXES:
            if k.endswith(suf):
                k = k[: -len(suf)]
                changed = True
                break
    return k


@dataclass
class ThreatProfile:
    """Strategic threat profile for a (detected) card, derived from the KB.

    ``known`` = the base card was found in the KB at all; ``tagged`` = it carries the
    curated strategic fields (win_condition / flags / targets). A card can be ``known``
    but not ``tagged`` (stats imported, strategy not yet curated) -- those still need a
    human pass before the role flags below can be trusted.
    """
    name: str                       # base card key
    known: bool = False             # found in the card KB (curated or stats)?
    tagged: bool = False            # has curated strategic fields (win_condition/flags/targets)?
    kind: Optional[str] = None      # troop | building | spell
    win_condition: bool = False
    siege: bool = False             # a building that attacks towers from the enemy side (X-Bow / Mortar)
    spell: bool = False
    building: bool = False
    flying: bool = False            # moves through the air
    attacks_air: bool = False
    swarm: bool = False
    tank: bool = False
    splash: bool = False
    death_damage: bool = False      # deals area damage when it dies (Balloon / Golem / Giant Skeleton ...)
    building_targeting: bool = False
    elixir: Optional[int] = None
    hitpoints: Optional[int] = None
    dps: Optional[int] = None
    tower_damage: Optional[int] = None
    attack_range: Optional[str] = None   # attack reach: melee | short | long (from CardDB.attack_range)
    melee: bool = False                  # a melee attacker (reach == melee) -- e.g. a tornado-pull target
    pull: bool = False                   # a PULL spell (Tornado): its value is the clump it creates, which
                                         # only exists 2-3.5s later -- so it must NOT be graded by role match

    def roles(self) -> List[str]:
        """Active role tags, most strategically salient first (for display / aggregation)."""
        out: List[str] = []
        if self.win_condition:
            out.append("win_condition")
        if self.siege:
            out.append("siege")
        if self.spell:
            out.append("spell")
        if self.building and not self.siege:
            out.append("building")
        if self.building_targeting and not self.win_condition:
            out.append("building_targeting")
        if self.tank:
            out.append("tank")
        if self.swarm:
            out.append("swarm")
        if self.flying:
            out.append("air")
        if self.splash:
            out.append("splash")
        if self.death_damage:
            out.append("death_damage")
        if out:
            return out
        if not self.known:
            return ["unknown"]
        if not self.tagged:
            return ["untagged"]
        return [self.kind] if self.kind else ["troop"]


def profile(db: CardDB, name: str) -> ThreatProfile:
    """Resolve a detected class name to its :class:`ThreatProfile` via the KB.

    MEMOISED PER DB INSTANCE (2026-08-19): the KB is read-only at runtime and the result is a
    frozen ThreatProfile, but this was rebuilt from six dict lookups on every call -- 8.4k calls
    in a 5-match profile, ~10% of a match's runtime, all returning identical objects. The cache
    lives ON the db so a rebuilt/replaced CardDB never serves stale profiles.
    """
    base = base_key(name)
    cache = getattr(db, "_profile_cache", None)
    if cache is None:
        cache = db._profile_cache = {}
    hit = cache.get(base)
    if hit is not None:
        return hit
    c = db.get(base)
    if not c:
        out = cache[base] = ThreatProfile(name=base, known=False)
        return out
    kind = c.get("kind")
    flags = set(db.flags(base))
    tagged = any(k in c for k in ("win_condition", "flags", "targets"))
    wc = bool(c.get("win_condition"))
    building = kind == "building"
    building_targeting = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    dps = c.get("dps") if c.get("dps") is not None else c.get("damage_per_second")
    # RAMPING ATTACKERS (2026-08-20 audit). Mighty Miner and the Inferno family publish their
    # FIRST-STAGE damage, so the KB stored Mighty Miner at 40 damage / 100 dps -- roughly a tenth
    # of the ~1000 he reaches on one target. This layer only decides ROLES, and the tank branch of
    # counters() tests `dps >= 150`, so the deck's designated tank-melter read as "not an answer
    # to a tank" and was charged the full misread penalty every time he did his job.
    # Deliberately role-layer only: sim/engine.py builds its combat model from `damage`/`dps` and
    # is untouched, so this cannot double-count anything there.
    ramp = c.get("damage_ramp") or {}
    stages, hit_s = ramp.get("damages") or (), float(ramp.get("hit_speed") or 0.0)
    if stages and hit_s > 0.0:
        dps = max(float(dps or 0.0), float(stages[-1]) / hit_s)
    reach = db.attack_range(base)                        # melee | short | long | None
    out = cache[base] = ThreatProfile(
        name=base,
        known=True,
        tagged=tagged,
        kind=kind,
        win_condition=wc,
        siege=("siege" in flags),                        # explicit siege flag (X-Bow / Mortar)
        spell=kind == "spell",
        building=building,
        flying=db.is_flying(base) or ("flying" in flags),
        attacks_air=db.attacks_air(base),
        swarm="swarm" in flags,
        tank=("tank" in flags) or ("mini_tank" in flags),
        splash=db.has_splash(base) or ("splash" in flags),
        death_damage="death_damage" in flags,
        building_targeting=building_targeting,
        elixir=c.get("elixir"),
        hitpoints=c.get("hitpoints"),
        dps=dps,
        tower_damage=db.tower_damage(base),
        attack_range=reach,
        melee=reach == "melee",
        pull=("pull" in flags),
    )
    return out


# --- Stage 3: identity-grounded threat features (the detector -> obs bridge) ------------------
# When the detector RELIABLY names an enemy card, we look up its KB role and expose a compact,
# team-agnostic feature block so the policy can learn to COUNTER by identity (air/swarm/tank/
# win-condition/building-targeter) instead of the coarse red-blob heuristics. The SIM builds this
# from ground truth (filtered to the recognised whitelist to mimic the detector's coverage); the
# LIVE env builds it from high-confidence whitelisted detections. Same layout both sides.
IDENTITY_DIM = 10
_VEL_NORM = 0.6    # depth/sec that reads as "fast" (~a troop covering the half-field in <2s)

# --- the identity block's WATCH LINE -----------------------------------------------------------
# How far up the board the identity block looks, in the normalised y where 0.5 is the RIVER and 1.0
# is your king. This used to be hard-coded to 0.5 in every producer, which meant a win condition was
# only ever recognised AFTER it had crossed -- and it crossed with depth ~0, i.e. the "a wincon is
# coming" flags arrived at the LATEST possible moment, too late to pre-place a defensive building
# that still has to deploy and acquire a target. Watching from the BRIDGE instead lights the role
# flags (win_condition / building_targeting) while the push is still arriving, and gives a real depth
# and approach VELOCITY to act on.
# EVERY producer must use the SAME value -- live play, the live RL env, the sim, the sim's mirrored
# opponent and the offline labeller -- or the policy trains on one distribution and plays on another.
IDENTITY_FRONT_DEFAULT = 0.44      # ~the deploy line / bridge approach (action.deploy_top)


def identity_front(cfg) -> float:
    """The y at which the identity block starts watching (see IDENTITY_FRONT_DEFAULT)."""
    return float(cfg.get("observation", "identity_front_y", default=IDENTITY_FRONT_DEFAULT))


def identity_depth(y: float, front: float) -> float:
    """Advance toward your king, normalised over the WATCHED span: 0.0 at ``front``, 1.0 at your king.

    Renormalising (rather than keeping the old 'fraction past the river') is what makes the depth [7]
    and velocity [8] features meaningful before the river is crossed -- with the old formula anything
    short of the river clamped to 0 and the push looked stationary until it was already on top of you.
    """
    span = max(1e-6, 1.0 - float(front))
    return min(1.0, max(0.0, (float(y) - float(front)) / span))

# --- opponent SHORT-TERM MEMORY (strategic complement to the reactive identity block) --------------
OPP_MEMORY_DIM = 8         # width of OpponentMemory.update() -- appended to the obs AFTER the identity block
_OPP_ELIXIR_NORM = 7.0     # avg-elixir normaliser (cheap-cycle ~2-3 <-> heavy beatdown ~5-7)
_OPP_ACT_NORM = 4.0        # recognised-presence EWMA normaliser (recent-activity / tempo)
_OPP_STAGE_NORM = 4.0      # back-line staging-count normaliser
_OPP_TAU_S = 10.0          # activity EWMA time constant in SECONDS -- see OpponentMemory.update
_OPP_DECAY = 0.9           # legacy PER-STEP decay, used only when update() is called without a dt


def identity_threat_vector(items, db: CardDB, prev_depth: float = 0.0,
                           dt: float = 0.0, horizon: float = 1.0) -> np.ndarray:
    """KB-grounded role + MOTION features for the RECOGNISED enemy threats on your half.

    ``items`` = iterable of ``(base_card_name, depth_frac)`` where depth_frac in [0,1] is how far
    the unit has advanced toward your king. ``prev_depth`` = the deepest-depth ([7]) this returned on
    the PREVIOUS observation and ``dt`` = the seconds since -> the approach velocity of the threat
    front; ``horizon`` = seconds to look ahead (~a defender's deploy time). Returns an ``IDENTITY_DIM``
    float vector:
      0 recognised-threat-present  1 tank  2 swarm  3 air(flying)  4 building/siege
      5 win_condition  6 building_targeting(ignores troops -> needs a building)  7 deepest depth
      8 approach VELOCITY (depth/sec toward your king, normalised)
      9 PREDICTED deepest depth after ``horizon`` s ( depth + velocity*horizon ) -- where the threat
        front will be when a ~horizon-second-deploy defender finishes deploying.
    All-zero when nothing is recognised (so the policy falls back to the red-blob threat block)."""
    v = np.zeros(IDENTITY_DIM, dtype=np.float32)
    known = [(base, float(depth), profile(db, base)) for base, depth in items]
    known = [k for k in known if k[2].known]
    seen = bool(known)
    max_depth = 0.0
    if seen:
        # PRIORITISE, DO NOT BLEND (2026-08-20). This used to OR every threat's role bits together
        # and take the MAXIMUM depth across all of them, which describes a unit that is not on the
        # board: a Golem at the bridge beside a lone Skeletons walking deep came out as
        # "tank + swarm, 80% of the way in" -- the depth belonging to the harmless card. The
        # urgency the reward and the advisor read was the SMALL threat's, so answering the vector
        # meant answering the Skeletons and ignoring the Golem (the reported behaviour).
        #
        # Danger is already priced by threat_value.ignore_cost_frac: the share of a princess tower
        # a card takes if ignored completely (Skeletons 0.4%, Golem 73%). Rank on it, break ties on
        # depth, and let the winner describe itself.
        from . import threat_value as _tv

        def _danger(base):
            try:
                return float(_tv.ignore_cost_frac(db, base))
            except Exception:  # noqa: BLE001 -- an unpriced card is not automatically harmless
                return 0.0

        scored = [(_danger(b), d, p, b) for b, d, p in known]
        primary = max(scored, key=lambda s: (s[0], s[1]))
        # Role bits: the primary, plus any OTHER threat that is not ignorable on its own -- a real
        # multi-card push still reads as a push, while a stray Skeletons cannot paint "swarm" onto
        # a Golem. If everything present is ignorable the old union stands; that board belongs to
        # triage (group_ignore_frac), which refuses it outright.
        floor = getattr(_tv, "IGNORE_FRAC", 0.05)
        speak = [s for s in scored if s[0] >= floor] or scored
        if primary not in speak:
            speak = [primary] + speak
        for _dgr, _dep, p, _b in speak:
            if p.tank:
                v[1] = 1.0
            if p.swarm:
                v[2] = 1.0
            if p.flying:
                v[3] = 1.0
            if p.siege or p.building:
                v[4] = 1.0
            if p.win_condition:
                v[5] = 1.0
            if p.building_targeting:
                v[6] = 1.0
        # DEPTH IS THE PRIMARY'S: the urgency of the thing that actually has to be answered.
        max_depth = float(primary[1])
        v[0] = 1.0
        v[7] = min(1.0, max_depth)
        vel = (max_depth - prev_depth) / dt if dt and dt > 1e-3 else 0.0
        vel = max(0.0, vel)                                    # only INCOMING threats count
        v[8] = min(1.0, vel / _VEL_NORM)
        v[9] = min(1.0, max_depth + vel * float(horizon))     # extrapolate to the post-deploy state
    return v


class OpponentMemory:
    """Per-match STATEFUL short-term memory of the opponent -- the STRATEGIC complement to the reactive,
    per-frame identity block. It accumulates what the opponent has COMMITTED over the whole match from the
    RECOGNISED (whitelisted) enemy cards (SIM = ground truth; LIVE = the detector), so the policy conditions
    on 'who is this / what are they building', not just the red blob in front of it right now. Reset each
    match. ``update(items)`` returns an ``OPP_MEMORY_DIM`` vector; ``items`` = iterable of ``(base_card,
    local_y)`` for recognised enemy troops, local_y in [0,1] (>=0.5 = your half / attacking, <0.5 = THEIR
    half / staging a push at the back). Layout:
      0 seen win_condition (persistent)   1 seen tank/beatdown (persistent)   2 seen swarm (persistent)
      3 seen air/flying (persistent)      4 seen building/siege (persistent)
      5 opponent AVG ELIXIR seen (cheap-cycle <-> heavy beatdown, normalised)
      6 recent ACTIVITY/tempo (EWMA of recognised presence -- how hard they're committing lately)
      7 back-line STAGING mass (recognised enemy troops on THEIR half now -- a push building at the back)
    All-zero until something is recognised (policy falls back to the identity + red-blob blocks)."""

    def __init__(self, db: CardDB):
        self.db = db
        self.reset()

    def reset(self) -> None:
        self._roles = np.zeros(5, dtype=np.float32)   # persistent seen-role flags: win/tank/swarm/air/building
        self._seen: dict = {}                          # distinct base card -> its elixir (for the cost profile)
        self._activity = 0.0                           # EWMA of recognised on-board presence (tempo)

    def update(self, items, dt: float | None = None) -> np.ndarray:
        """Fold one observation into the memory; ``dt`` = seconds since the previous update.

        The tempo EWMA ([6]) decays in WALL-CLOCK time, not per call. A fixed per-step factor was
        correct while every decision was one fixed slice apart, but the live act loop is now
        EVENT-DRIVEN (``play.react_min_gap_s``): it wakes early the moment perception spots an enemy
        commitment, so live steps run 0.3-1.0s while the sim is pinned to ``sim.agent_dt``. A
        per-step factor would therefore shrink the memory window to a THIRD of its trained length
        exactly when the opponent commits -- the one moment the tempo feature is supposed to carry
        signal. ``exp(-dt/_OPP_TAU_S)`` keeps the horizon at _OPP_TAU_S seconds on both sides at any
        cadence (and stays correct if act_period / perception_hz are retuned later). Omitting ``dt``
        keeps the legacy per-step behaviour; at the sim's 1.0s step the two agree to 0.9048 vs
        0.9000, so this is a live-parity fix, not a retrain trigger."""
        n = 0
        staging = 0.0
        for base, ly in items:
            p = profile(self.db, base)
            if not p.known:
                continue
            n += 1
            if base not in self._seen:
                self._seen[base] = float(self.db.elixir(base) or 0.0)
            if p.win_condition:
                self._roles[0] = 1.0
            if p.tank:
                self._roles[1] = 1.0
            if p.swarm:
                self._roles[2] = 1.0
            if p.flying:
                self._roles[3] = 1.0
            if p.siege or p.building:
                self._roles[4] = 1.0
            if ly < 0.5:                               # on THEIR half = staging / building a push at the back
                staging += 1.0
        decay = _OPP_DECAY if dt is None else math.exp(-max(0.0, float(dt)) / _OPP_TAU_S)
        self._activity = self._activity * decay + n * (1.0 - decay)
        v = np.zeros(OPP_MEMORY_DIM, dtype=np.float32)
        v[0:5] = self._roles
        if self._seen:
            v[5] = min(1.0, (sum(self._seen.values()) / len(self._seen)) / _OPP_ELIXIR_NORM)
        v[6] = min(1.0, self._activity / _OPP_ACT_NORM)
        v[7] = min(1.0, staging / _OPP_STAGE_NORM)
        return v


def counters(play: ThreatProfile, threat_id: np.ndarray) -> bool:
    """Does a card with profile ``play`` counter the RECOGNISED threat block ``threat_id``
    (the vector from :func:`identity_threat_vector`)? Role-based, KB-grounded: air-defence vs
    flying, splash vs swarm, a building/high-DPS vs a tank, a building vs a building-targeter,
    and -- see below -- a body vs a bare win condition, damage vs enemy siege.

    This answers ROLE VALIDITY only ("can this card deal with that"), never elixir efficiency:
    spending a 6-cost spell on a 3-cost threat is judged by the elixir_trade term, which already
    prices overspending. Keeping the two separate is why this stays a small role table.
    """
    if threat_id is None or len(threat_id) < IDENTITY_DIM or threat_id[0] < 0.5:
        return False
    if threat_id[3] >= 0.5 and not (play.attacks_air or play.flying):
        # YOU CANNOT COUNTER WHAT YOU CANNOT TOUCH (2026-08-16). Only the air-defence branch
        # below used to test the flying bit, so every LATER branch could still credit a
        # ground-only card against an air threat -- and the swarm branch (splash OR spell) did
        # exactly that for THE LOG against a flying swarm: counters(the_log, flying swarm)
        # returned True, so the referee PAID for logging minions/bats. That is the "model logs
        # air cards" behaviour the user reported, taught directly by this table.
        # One guard up front, so no branch can ever credit an unreachable threat.
        return False
    if (getattr(play, "building_targeting", False) and play.kind == "troop"
            and threat_id[6] < 0.5):
        # ...AND THE SAME TRUTH ON THE GROUND (2026-08-20 audit). A building-targeting TROOP --
        # Hog Rider, Ram Rider, Battle Ram, Balloon -- walks straight past a knight or a pekka to
        # reach a building. It can no more "counter" a tank than the Log can counter a Minion
        # Horde, yet the tank branch below credited it on raw DPS (Hog is 198), so the referee
        # paid +1.0 for answering a tank with the deck's own win condition. Compounded in hogeq,
        # where _wincon_exec has no hog branch at all: this misread was the ONLY positive reward
        # the Hog Rider could earn anywhere, actively teaching "defend with your win condition".
        # The exception is threat_id[6] -- an enemy building-targeter, where trading them is real.
        return False
    if threat_id[3] >= 0.5:                                            # flying threat -> air defence
        return True
    if threat_id[2] >= 0.5 and (play.splash or play.spell):            # swarm -> splash / spell
        return True
    if threat_id[1] >= 0.5 and (play.building or (play.dps or 0) >= 150):  # tank -> building / high DPS
        return True
    if threat_id[6] >= 0.5 and play.building:                          # building-targeter -> a building
        return True
    # BARE WIN CONDITION -- a win-condition TROOP carrying no other role (Miner is the archetype:
    # not a tank, not air, not a swarm, and NOT building-targeting, so every branch above misses it).
    # It walks (or tunnels) straight at the tower, so the answer is simply a BODY that engages it: any
    # troop, or a defensive (non-siege) building. Spells are excluded because one rarely kills a lone
    # win condition and the trade is bad; our own siege building cannot defend. Tanks and buildings are
    # excluded from this branch so heavy/siege win conditions keep their stricter rules above.
    #
    # NB there is deliberately NO enemy-siege branch: an offensive X-Bow/Mortar is deployed on the
    # OPPONENT'S half, and identity_threat_vector only admits enemies that have crossed onto YOURS
    # (sim/view.identity_items filters local y >= 0.5, and env.py filters gy >= 0.5). Enemy siege
    # therefore never reaches this function, so a branch for it would be dead code. Answering it --
    # e.g. a Tesla at the bridge, which outranges nothing but sits close enough to shell the bow --
    # requires the threat block to see ACROSS the river first.
    if (threat_id[5] >= 0.5 and threat_id[1] < 0.5 and threat_id[4] < 0.5
            and threat_id[3] < 0.5):
        # ...and NOT FLYING (2026-08-15): the docstring above always said "not air", but the
        # code never checked the bit -- so a ground Knight dropped "against" a Balloon was
        # credited +1.0 for a body-block that cannot touch it. A flying bare win condition is
        # answered by the air-defence branch at the top, nothing else.
        return play.kind == "troop" or (play.building and not play.siege)
    return False


def _detect_classes(cfg) -> List[str]:
    if cfg is not None:
        f = Path(cfg.path(cfg.get("detect", "classes_file", default="config/detect_classes.yaml")))
    else:
        f = Path(__file__).resolve().parents[2] / "config" / "detect_classes.yaml"
    data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    return [str(c) for c in (data.get("classes") or [])]


def _fmt(p: ThreatProfile) -> str:
    stats = []
    if p.elixir is not None:
        stats.append(f"{p.elixir}e")
    if p.hitpoints is not None:
        stats.append(f"{p.hitpoints}hp")
    if p.dps is not None:
        stats.append(f"{p.dps}dps")
    if p.attack_range:
        stats.append(p.attack_range)
    return f"[{p.kind or '?'}] {', '.join(p.roles())}   {' '.join(stats)}".rstrip()


def roles_report(cfg=None, show_all: bool = False, card: Optional[str] = None) -> None:
    """Print the strategic role derived for the detector's classes so you can verify the
    tagging (and see which cards still need curating). ``--card`` inspects one; ``--all``
    dumps every class."""
    db = load_cards(cfg)
    if card:
        p = profile(db, card)
        print(f"{card}  ->  base '{p.name}'")
        print(f"  {_fmt(p)}")
        print(f"  known={p.known} tagged={p.tagged} win_condition={p.win_condition} "
              f"siege={p.siege} flying={p.flying} attacks_air={p.attacks_air} melee={p.melee} "
              f"reach={p.attack_range} building_targeting={p.building_targeting} tower_damage={p.tower_damage}")
        return

    classes = _detect_classes(cfg)
    profs = [profile(db, c) for c in classes]

    def bases(pred) -> List[str]:
        return sorted({p.name for p in profs if p.known and p.tagged and pred(p)})

    win = bases(lambda p: p.win_condition)
    siege = bases(lambda p: p.siege)
    spells = bases(lambda p: p.spell)
    air = bases(lambda p: p.flying)
    swarm = bases(lambda p: p.swarm)
    tank = bases(lambda p: p.tank)
    stats_only = sorted({p.name for p in profs if p.known and not p.tagged})
    missing = sorted({p.name for p in profs if not p.known})
    n_tagged = sum(1 for p in profs if p.known and p.tagged)

    def show(title: str, items: List[str]) -> None:
        print(f"\n{title} ({len(items)}):")
        print("  " + (", ".join(items) if items else "(none)"))

    print(f"[card-roles] {len(classes)} detector classes  ->  "
          f"{n_tagged} fully tagged, {len(stats_only)} stats-only, {len(missing)} not in KB "
          f"(base cards; _evo/_hero/_ability/_aoe collapse to their base)")
    show("WIN CONDITIONS", win)
    show("SIEGE (building that attacks towers: X-Bow / Mortar)", siege)
    show("SPELLS", spells)
    show("AIR / FLYING", air)
    show("SWARM", swarm)
    show("TANK", tank)
    show("STATS ONLY -> curate win_condition/targets/flags in cards.yaml (some may be win conditions!)", stats_only)
    show("NOT IN KB -> add to cards.yaml/cards_stats.json if you face them", missing)

    if show_all:
        print("\n--- every detector class ---")
        for cls, p in zip(classes, profs):
            tail = "" if _key(cls) == p.name else f" (base {p.name})"
            print(f"  {cls:30s}{tail:16s} {_fmt(p)}")
