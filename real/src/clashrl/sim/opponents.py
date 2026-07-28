"""Scripted opponent archetypes for the sim (team 1 = top). Deliberately simple heuristic bots so
the agent faces varied, plausible pressure across MANY matches. Not meant to be strong -- just to
cover defend / cycle-chip / beatdown / siege styles so the policy learns robust responses.

Grow these (or add self-play) later; see real/DECK_SWITCH.md.
"""
from __future__ import annotations

from .engine import build_spec

# Representative decks of common ladder cards (must exist in the KB; missing -> harmless defaults).
_DECKS = {
    "hog_cycle":  ["hog_rider", "musketeer", "knight", "skeletons", "ice_spirit", "cannon", "fireball", "zap"],
    "beatdown":   ["giant", "musketeer", "mini_pekka", "archers", "minions", "fireball", "arrows", "knight"],
    "control":    ["valkyrie", "musketeer", "tesla", "skeletons", "ice_spirit", "fireball", "archers", "knight"],
    "siege":      ["x_bow", "tesla", "archers", "skeletons", "ice_spirit", "fireball", "knight", "rocket"],
}


class ScriptedBot:
    """One heuristic action per agent step: defend the deepest threat in our half, else apply
    pressure per style (beatdown saves to ~full then commits; the rest chip more freely)."""

    def __init__(self, cfg, db, rng, style: str):
        self.style = style
        self.rng = rng
        deck = _DECKS.get(style, _DECKS["hog_cycle"])
        self.specs = [build_spec(db, k) for k in deck]

    def act(self, eng) -> None:
        team = 1
        elix = eng.elixir[team]
        affordable = [s for s in self.specs if s.elixir <= elix]
        if not affordable:
            return
        # DEFEND: an enemy (team 0) unit has entered our half (y < 0.5)
        threats = [u for u in eng.units if u.team == 0 and u.y < 0.5]
        if threats:
            deepest = min(threats, key=lambda u: u.y)             # closest to our king
            troops = [s for s in affordable if s.kind == "troop" and not s.building_only]
            if troops:
                s = min(troops, key=lambda s: s.elixir)
                eng.deploy(team, s, deepest.x, max(0.12, deepest.y - 0.06))
                return
            spells = [s for s in affordable if s.kind == "spell"]
            if spells and len(threats) >= 3:
                s = min(spells, key=lambda s: s.elixir)
                eng.deploy(team, s, deepest.x, deepest.y)
                return
        # ATTACK
        if self.style == "beatdown" and elix < 9.5:
            return                                                # save up for a big push
        offense = [s for s in affordable if s.kind != "spell"]
        if not offense:
            return
        lane = self.rng.choice([0.25, 0.75])
        if self.style == "beatdown":
            tank = max(offense, key=lambda s: s.hp)               # heaviest unit at the back
            eng.deploy(team, tank, lane, 0.18)
        elif self.style == "siege":
            sieges = [s for s in offense if s.siege] or offense
            eng.deploy(team, self.rng.choice(sieges), lane, 0.42)
        else:                                                     # cycle / control: chip at the bridge
            wc = [s for s in offense if s.building_only] or offense
            eng.deploy(team, self.rng.choice(wc), lane, 0.46)


def make_opponent(cfg, db, rng) -> ScriptedBot:
    """A random archetype (uniform over the four styles)."""
    style = rng.choice(list(_DECKS.keys()))
    return ScriptedBot(cfg, db, rng, style)
