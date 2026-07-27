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

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import yaml

from .cards import CardDB, _key, load as load_cards

# Detection-taxonomy suffixes appended to a base card key (see config/detect_classes.yaml).
_SUFFIXES = ("_evo", "_hero", "_ability", "_aoe")


def base_key(name: str) -> str:
    """Base card key for a detected class name, stripping one detection suffix
    (``tesla_evo`` / ``knight_hero`` / ``skeleton_king_ability`` / ``fireball_aoe`` -> base)."""
    k = _key(name)
    for suf in _SUFFIXES:
        if k.endswith(suf):
            return k[: -len(suf)]
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
    """Resolve a detected class name to its :class:`ThreatProfile` via the KB."""
    base = base_key(name)
    c = db.get(base)
    if not c:
        return ThreatProfile(name=base, known=False)
    kind = c.get("kind")
    flags = set(db.flags(base))
    tagged = any(k in c for k in ("win_condition", "flags", "targets"))
    wc = bool(c.get("win_condition"))
    building = kind == "building"
    building_targeting = ("building_targeting" in flags) or (c.get("targets") == "buildings_only")
    dps = c.get("dps") if c.get("dps") is not None else c.get("damage_per_second")
    reach = db.attack_range(base)                        # melee | short | long | None
    return ThreatProfile(
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
    )


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
