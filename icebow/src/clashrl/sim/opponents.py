"""Opponents for the sim. Two kinds:

* :class:`ScriptedBot` -- pilots a real meta deck (sampled from the meta-deck pool, see meta_decks.py)
  with simple, deck-agnostic heuristics whose aggression is set by the deck's inferred STYLE
  (cycle / control / beatdown / siege). Not strong -- just varied, plausible pressure so the policy
  learns robust responses across MANY decks.
* :class:`SelfPlayOpponent` -- pilots team 1 with a FROZEN past copy of the agent's own policy, viewing
  a MIRRORED board (see sim/view.py) so the same policy plays both sides. Snapshotted into a small
  league by train_sim and mixed in with the scripted bots (`sim.selfplay_prob`).
"""
from __future__ import annotations

from typing import List

import numpy as np

from .engine import _dist, build_spec
from ..cycle import cycle_vector
from .. import card_threat
from .. import detect_obs
from .. import interactions
from . import view

_NEG = -1e9   # finite mask value (matches train_sim_ppo; -inf can NaN through a softmax)


# =================================================================================================
# ABILITY AI -- when an OPPONENT presses its champion/hero button.
# =================================================================================================
# Boss Bandit's Getaway Grenade used to be fired by the ENGINE, below a per-unit rolled HP
# fraction. That modelled a rule the game removed: Boss_Bandit.wikitext History 8/7/2025 says the
# grenade "can be activated a total of 2 times INDEPENDENT ON Boss Bandit's hitpoints", and the
# page describes it only as a button (conflicts.md C5). Owner ruling: it becomes a normal button
# and the OPPONENT decides.
#
# This is the framework EVERY champion and hero ability uses, so it is keyed on the ability's
# SHAPE rather than on the card. Three families, and each one is a different question about the
# board:
#   escape     is this body in trouble, or too far forward to survive being answered?
#   defensive  is it about to be swarmed?
#   offensive  is it deep enough that the ability buys tower damage?
# I8 adds ~16 hero kinds on top; a new kind picks a family here (or the KB overrides it per card)
# and needs no new bot code.
_ABILITY_FAMILY = {
    # Getaway Grenade IS the escape ability: invisible, then 6 tiles backwards, "This allows her
    # to escape any form of damage".
    "movement_flight": "escape",
    # Cloaking Cape reads as offence (a 1.8x attack-speed buff) but every worked example on the
    # page is a save -- dodging an X-Bow/Mortar lock, diverting troops, walking past a Tesla.
    # Untargetable-while-shooting is a defensive tool that happens to deal damage.
    "stealth": "escape",
    # Explosive Escape is BOTH, and the page says which one to plan around: "One of his weaknesses
    # are swarms, and Explosive Escape's bomb mitigates that."
    "bomb": "defensive",
    # Soul Summoning answers a push with 6-16 bodies; the page warns against firing it with
    # nothing to tank for the Skeletons.
    "soul_bank": "defensive",
    # Royal Rescue: "This makes him very effective against large tanks and can prevent a lot of
    # damage done to Crown Towers."
    "guardian": "defensive",
    # Pensive Protection is -65% incoming damage plus reflection. It is only worth elixir while
    # something is actually shooting him.
    "reflect": "defensive",
    # Dashing Dash chains through their defence; it needs targets in range to do anything at all.
    "dash_chain": "offensive",
    # Lightning Link is 4 s of area damage around a tether -- a push tool, and its crown-tower
    # column says it is meant to be on the tower.
    "zone": "offensive",
}

# Per-family defaults. Every one is a CHOICE, not a published number -- no page states when to
# press the button -- so they live in one table, are overridable per card through a KB `ability_ai`
# dict, and are named rather than buried in the branch that reads them.
_ABILITY_AI_DEFAULTS = {
    "escape": {"hp_frac": 0.55, "over_river": True},
    "defensive": {"crowd_n": 3, "crowd_tiles": 4.0},
    "offensive": {"tower_tiles": 7.0, "min_enemies": 0},
}


class ScriptedBot:
    """One heuristic action per agent step: defend the deepest threat in our half, else apply
    pressure per the deck's style (beatdown saves to ~full then commits; the rest chip more freely).

    ADAPTIVE mode (Tier-1 'smart opponents', training-only -- the eval benchmark stays frozen on
    non-adaptive bots): observation-driven counter-play vs the agent, each behaviour gated by a
    per-bot knowledge roll + a human reaction delay:
      * ANTI-SIEGE -- the meta response to icebow: an agent X-Bow on the field gets answered after
        ``reaction_s`` with a big spell (when the bow is supported) or their heaviest troop dropped
        on top of it.
      * COUNTER-HOLDING -- once the X-Bow has been SEEN, their heaviest troop is reserved as the
        siege answer (not spent on casual defence/cycle) unless elixir overflows.
      * DUMP PUNISH -- the agent committing 8+ elixir within ~6s gets punished immediately in the
        OPPOSITE lane (real players' core habit vs siege decks over-committing).
      * SPLIT-PUSH -- after SEEING one agent tornado, pushes alternate/split lanes so a single
        clump-pull can no longer catch the whole attack (the human counter to tornado value -- and
        exactly the pressure pattern that forces the agent to learn real tornado timing).
    """

    def __init__(self, cfg, db, rng, cards: List[str], style: str, levels: "List[int] | None" = None,
                 adaptive: bool = False, evo: "List[str] | None" = None,
                 evo_candidates: "List[str] | None" = None,
                 hero_candidates: "List[str] | None" = None,
                 support: "List[str] | None" = None):
        self.style = style
        self.cards = list(cards)                                  # deck card keys (for matchup detection)
        self.rng = rng
        levels = levels or [11] * len(cards)
        self.specs = [build_spec(db, k, lvl) for k, lvl in zip(cards, levels)]
        self._backline_done = False                              # one backline-support opening per match
        self._backline_prob = float(cfg.get("sim", "backline_support_prob", default=0.05))
        self._backline_until = float(cfg.get("sim", "backline_support_until_s", default=45.0))
        self.anywhere_prob = float(cfg.get("sim", "anywhere_deploy_prob", default=0.75))   # Miner-style tower drops
        # --- adaptive knobs (rolled per bot -> a POPULATION of skill levels, not one clone) ---
        self.adaptive = bool(adaptive)
        ad = cfg.get("sim", "adaptive", default={}) or {}
        rs = ad.get("reaction_s", [1.0, 3.0])
        self.reaction_s = rng.uniform(float(rs[0]), float(rs[1]))
        self.anti_siege_know = adaptive and rng.random() < float(ad.get("anti_siege_prob", 0.8))
        self.hold_counter = adaptive and rng.random() < float(ad.get("hold_counter_prob", 0.6))
        self.punish_know = adaptive and rng.random() < float(ad.get("punish_prob", 0.6))
        self.split_know = adaptive and rng.random() < float(ad.get("split_prob", 0.7))
        troops = [s for s in self.specs if s.kind == "troop" and not s.building_only and not s.flying]
        self._reserved = max(troops, key=lambda s: s.hp) if troops else None   # the held siege answer
        self._xbow_ever = False          # agent siege seen at least once this match
        self._siege_seen_t = None        # when the CURRENT bow was first seen (reaction delay)
        self._nado_seen = False          # agent tornado seen -> start splitting pushes
        self._spend: list = []           # (t, elixir, x) of observed agent deploys
        self._seen_deploy_t = -1.0
        self._punish_cd = 0.0
        self._flip = rng.random() < 0.5  # split-push lane alternator
        self._ability_armed_t = None     # engine time the ability window opened (reaction delay)
        # HAND + CYCLE. A real opponent holds 4 of its 8 cards and must cycle the rest before it can
        # repeat one. Without this the bot chose from the WHOLE deck every step, so it could open the
        # same card twice in a row (and never ran out of its best answer) -- the agent was training
        # against a deck with no cycle cost at all.
        self.cycle = list(range(len(self.specs)))
        rng.shuffle(self.cycle)
        # THE EVOLUTION SLOT (2026-08-26, I3). Two sources, in order of authority:
        #
        #   `evo`            -- a DECLARED slot. Authoritative if one ever exists; today none does.
        #                       The battlelog field it used to come from turned out to report the
        #                       player's OWNED evolution level, not the fielded slot (it yielded
        #                       THREE evolutions for 153/233 decks against a game that allows at
        #                       most two, and reported a level for `berserker`, which has no
        #                       evolution), so all 233 declarations were stripped. The hook stays.
        #   `evo_candidates` -- every card in this deck that really HAS an evolution, derived from
        #                       the KB's 42 `_evo` rows (== the 42 wiki-verified evolutions in
        #                       research/sim_parity/ledger/r1a_evolutions.json).
        #
        # WHY A UNIFORM DRAW over the candidates rather than one fixed pick: no source identifies
        # the slotted card, so naming one would be FALSE PRECISION -- and a fixed slot is also
        # worse training, because the policy would overfit a single opponent evolution per deck.
        # Drawing per match stays honest about what is unknown AND gives the agent the variety it
        # actually faces. This is NOT the old bug returning: the old code picked "the first card
        # whose `<key>_evo` builds", and build_spec FABRICATED a spec for any `_evo` key, so the
        # pick was always deck index 0 and 689 of the 1000 meta decks fielded a PHANTOM (base
        # stats wearing the evo's name). This draw ranges only over cards that provably have an
        # evolution, so every outcome is real. MEASURED by tools/evo_audit.py: 0 phantoms.
        #
        # THE LOADOUT IS THREE SLOTS (16/3/2026, Heroes revid 437509: the format became "one
        # Evolution, one Hero and one Wild (from 2 evo and 2 hero)"). I3 shipped the Evolution
        # slot; I8 adds the other two, and the WILD slot is what makes a second evolution legal
        # again -- which is why the old "exactly one draw, one slot, never two" note is gone.
        self.evo_idx, self.evo_spec, self.evo_cycles, self.evo_charge = -1, None, 2, 0
        self.evo_declared = [k for k in (evo or []) if k in self.cards]
        # RNG: the bot's OWN stream, so a seeded ScriptedBot fields a reproducible loadout while a
        # vectorised run gets a different one per env. Every draw below is skipped when there is
        # nothing to draw, so a deck with no candidate does not perturb the stream.
        self.evo_pool = [k for k in (evo_candidates or []) if k in self.cards]
        self.hero_pool = [k for k in (hero_candidates or []) if k in self.cards]
        # THE DECK'S MEASURED TOWER TROOP (I8). Parsed and carried since R4 and completely INERT
        # until now: the engine rolled one per match from a config-level weight table while the
        # pool held the real answer per deck. `support` arrives as a list because the loader
        # normalises every slot field to one; a deck names at most one tower troop.
        self.support = list(support or [])
        _order = list(self.evo_declared)
        if not _order and self.evo_pool:
            _order = [self.evo_pool[rng.randrange(len(self.evo_pool))]]   # ONE uniform draw
        _taken = set()                        # deck INDICES already spoken for by a slot
        for _k in _order:
            _i = self.cards.index(_k)
            _ev = self._build_evo(db, _k, levels[_i])
            if _ev is None:
                continue
            self.evo_idx, self.evo_spec = _i, _ev
            # CYCLES from the EVOLUTION'S OWN ROW. A curated `evolution.cycles` still wins, then
            # the wiki's Cycles column (`evo_cycles` on the `_evo` row); the old flat `or 2` was
            # simply wrong for every import-only evo -- Evo Elite Barbarians is 1, not 2.
            # `db.evo_cycles()` now implements exactly that order for all 42 evolutions (I1
            # backport: it used to gate on a curated `evolution.available` that only 6 base cards
            # carry, so it returned 0 for the other 36 and this had to duplicate the lookup).
            # The `or 2` remains only as a floor: 0 would read as "already charged" forever.
            self.evo_cycles = int(db.evo_cycles(_k) or 2)
            _taken.add(_i)
            break                                            # ONE card in the Evolution slot

        # ---- THE HERO SLOT (I8, owner ruling 2026-08-26) -----------------------------------
        # ALWAYS field one when the deck has a candidate, uniform over `hero_candidates`. Same
        # honesty argument as the evolution draw: no accessible source names the slotted card, so
        # naming one would be false precision AND worse training (the policy would overfit a fixed
        # opponent hero per deck). MEASURED over the shipped pool: 842 of 1000 decks qualify.
        #
        # A HERO IS NOT A CHARGE MECHANIC. An evolution must be cycled `evo_cycles` times before it
        # appears; the card in the Hero slot simply IS the hero from its first play. So the slot is
        # applied by swapping the spec ONCE here rather than being resolved on every `_play`.
        self.hero_idx, self.hero_spec = -1, None
        _hero_choices = [k for k in self.hero_pool if self.cards.index(k) not in _taken]
        if not _hero_choices and self.hero_pool:
            # COLLISION: the Evolution slot took the deck's only hero-capable card. The two owner
            # rulings ("always field one evolution", "always field one hero") can only conflict
            # here, and only when a SINGLE card is the sole candidate for both -- so the fix is to
            # move the EVOLUTION, which by construction still has somewhere else to go whenever
            # this branch is reachable (`_hero_choices` is empty with a non-empty `hero_pool`
            # exactly when the pool is that one card). MEASURED before the fix: 194 of 4982 decks
            # with a hero candidate (3.9%) fielded no hero at all.
            _alt = [k for k in self.evo_pool if self.cards.index(k) != self.evo_idx]
            if _alt:
                _k = _alt[rng.randrange(len(_alt))]
                _i = self.cards.index(_k)
                _ev = self._build_evo(db, _k, levels[_i])
                if _ev is not None:
                    _taken.discard(self.evo_idx)
                    self.evo_idx, self.evo_spec = _i, _ev
                    self.evo_cycles = int(db.evo_cycles(_k) or 2)
                    _taken.add(_i)
                    _hero_choices = [k for k in self.hero_pool if self.cards.index(k) not in _taken]
        if _hero_choices:
            _k = _hero_choices[rng.randrange(len(_hero_choices))]      # ONE uniform draw
            _i = self.cards.index(_k)
            _hs = self._build_hero(db, _k, levels[_i])
            if _hs is not None:
                self.hero_idx, self.hero_spec, self.specs[_i] = _i, _hs, _hs
                _taken.add(_i)

        # ---- THE WILD SLOT (I8, owner ruling 2026-08-26) -----------------------------------
        # A second evolution, a second hero, or NEITHER, at 1/3 each, renormalised over whatever is
        # still legal: a wild evo must differ from the slot evo, a wild hero from the slot hero,
        # and a category with no candidate left redistributes its share over the rest.
        #
        # THE 1/3 IS AN UNMEASURED CHOICE. No source publishes how often players fill the Wild slot
        # or with what -- the battlelog does not carry slots at all (conflicts.md, R4 CORRECTION),
        # and RoyaleAPI / Deck Shop / StatsRoyale are all 403. A flat three-way split is the
        # least-assuming prior over "evo / hero / empty", not a measurement, and it is a CONFIG
        # KNOB (sim.wild_evo_prob, sim.wild_hero_prob) exactly so a real source can replace it
        # without touching this file.
        self.wild_evo_idx, self.wild_evo_spec = -1, None
        self.wild_evo_cycles, self.wild_evo_charge = 2, 0
        self.wild_hero_idx, self.wild_hero_spec = -1, None
        self.wild_kind = ""                   # "evo" | "hero" | "" -- what the wild slot took
        self.wild_choices = (0, 0)            # (legal wild evos, legal wild heroes) at draw time
        _p_evo = float(cfg.get("sim", "wild_evo_prob", default=1.0 / 3.0))
        _p_hero = float(cfg.get("sim", "wild_hero_prob", default=1.0 / 3.0))
        _wild_evo = [k for k in self.evo_pool if self.cards.index(k) not in _taken]
        _wild_hero = [k for k in self.hero_pool if self.cards.index(k) not in _taken]
        # What was LEGAL when the wild draw was taken, recorded so the distribution can be audited
        # against the 1/3 without re-deriving legality from the outcome (which is circular: a deck
        # whose only spare evo candidate is the hero's card has no legal wild evo, and counting it
        # as one makes an unbiased draw look skewed).
        self.wild_choices = (len(_wild_evo), len(_wild_hero))
        if _wild_evo or _wild_hero:
            # "neither" keeps whatever the other two do not claim, so the three shares always sum
            # to 1 and dropping a category cannot silently RAISE the chance of an empty slot.
            _w = [(_p_evo if _wild_evo else 0.0), (_p_hero if _wild_hero else 0.0),
                  max(0.0, 1.0 - _p_evo - _p_hero)]
            _tot = sum(_w)
            _r = rng.random() * _tot if _tot > 0.0 else 0.0
            if _wild_evo and _r < _w[0]:
                _k = _wild_evo[rng.randrange(len(_wild_evo))]
                _i = self.cards.index(_k)
                _ev = self._build_evo(db, _k, levels[_i])
                if _ev is not None:
                    self.wild_evo_idx, self.wild_evo_spec = _i, _ev
                    self.wild_evo_cycles = int(db.evo_cycles(_k) or 2)
                    self.wild_kind = "evo"
                    _taken.add(_i)
            elif _wild_hero and _r < _w[0] + _w[1]:
                _k = _wild_hero[rng.randrange(len(_wild_hero))]
                _i = self.cards.index(_k)
                _hs = self._build_hero(db, _k, levels[_i])
                if _hs is not None:
                    self.wild_hero_idx, self.wild_hero_spec, self.specs[_i] = _i, _hs, _hs
                    self.wild_kind = "hero"
                    _taken.add(_i)
        # The held siege answer is chosen by HP and a hero body can be the biggest thing in the
        # deck, so it is re-derived AFTER the swaps -- and it MUST be: `_play` finds a card by
        # object identity in `self.specs`, so a stale spec object would resolve to index -1 and
        # quietly bypass the cycle.
        troops = [s for s in self.specs if s.kind == "troop" and not s.building_only and not s.flying]
        self._reserved = max(troops, key=lambda s: s.hp) if troops else None

    @staticmethod
    def _build_evo(db, key: str, level: int):
        """The `<key>_evo` spec, or None when the KB cannot really build one.

        Shared by the Evolution slot and the Wild slot so the two cannot diverge -- and these
        guards are why phantoms stay at 0: a missing row RAISES (I3) instead of handing back the
        base card wearing the evolution's name, and a row that builds to nothing is refused too.
        """
        try:
            spec = build_spec(db, key + "_evo", level)
        except KeyError:          # no KB row for it yet -- field nothing, never fake the base card
            return None
        return None if (spec.hp <= 0 and spec.kind != "spell") else spec

    @staticmethod
    def _build_hero(db, key: str, level: int):
        """The `<key>_hero` spec, or None when the KB cannot really build one.

        Same contract as `_build_evo`, for the same reason: `build_spec` raises for a key with no
        hero row, so a stale `hero_candidates` list can only field FEWER heroes -- never a phantom
        one wearing the base card's stats.
        """
        try:
            spec = build_spec(db, key + "_hero", level)
        except KeyError:
            return None
        return None if (spec.hp <= 0 and spec.kind != "spell") else spec

    def _try_ability(self, eng, team: int = 1) -> bool:
        """Press this deck's champion/hero ability button, if the board says to.

        One decision per bot step, taken BEFORE the card action, because an ability spends its own
        elixir and does not leave the hand -- a real player does both in the same beat.

        RULING 5 is respected here as well as in the engine: the button belongs to the NEWEST
        living body, so the bot asks whether THAT body wants to fire rather than scanning for any
        body that would. Asking the wrong body would make the bot fire a Boss Bandit's grenade
        because an older, forgotten one was cornered.

        Returns True if the ability actually went off.
        """
        bodies = [u for u in eng.units
                  if u.team == team and u.hp > 0 and u.spec.ability_kind and u.deploy_left <= 0.0]
        if not bodies:
            return False
        u = max(bodies, key=lambda b: b.deploy_seq)
        s = u.spec
        # Cheap refusals first -- these are the same tests champion_ability applies, and asking
        # them here keeps a hopeless board from paying the reaction-delay bookkeeping below.
        if u.ability_cd_left > 0.0 or eng._ability_uses_left(u) <= 0:
            return False
        if eng.elixir[team] < s.ability_cost:
            return False
        ai = dict(s.ability_ai)
        family = str(ai.get("family") or _ABILITY_FAMILY.get(s.ability_kind, "defensive"))
        knobs = dict(_ABILITY_AI_DEFAULTS.get(family, {}))
        knobs.update(ai)
        if not self._ability_wants(eng, u, family, knobs):
            self._ability_armed_t = None            # the window closed: the next one pays again
            return False
        # HUMAN REACTION. Without it the bot fires on the exact tick the condition flips, which is
        # both inhuman and unlearnable -- the policy would face a perfectly-timed grenade every
        # time. The delay is the bot's own rolled `reaction_s`, the same population knob the
        # adaptive behaviours use, so a match faces one opponent's timing rather than the mean.
        if self._ability_armed_t is None:
            self._ability_armed_t = float(eng.t)
        if eng.t - self._ability_armed_t < self.reaction_s:
            return False
        self._ability_armed_t = None
        return bool(eng.champion_ability(team))

    def _ability_wants(self, eng, u, family: str, k: dict) -> bool:
        """The per-family predicate. Split out so a test can drive it without a whole match."""
        if family == "escape":
            # In trouble, or too deep to walk back. `_RIVER` is y = 0.5 and team 1 attacks
            # DOWNWARD, so "past the river" is y > 0.5 for them and y < 0.5 for us.
            if u.hp <= u.spec.hp * float(k.get("hp_frac", 0.55)):
                return True
            if k.get("over_river"):
                return u.y > 0.5 if u.team == 1 else u.y < 0.5
            return False
        if family == "defensive":
            n = int(k.get("crowd_n", 3))
            r = float(k.get("crowd_tiles", 4.0))
            near = sum(1 for e in eng.units
                       if e.team != u.team and e.hp > 0 and e.spec.kind == "troop"
                       and _dist(u.x, u.y, e.x, e.y) <= r)
            return near >= n
        if family == "offensive":
            r = float(k.get("tower_tiles", 7.0))
            if not any(_dist(u.x, u.y, t.x, t.y) <= r for t in eng.towers[1 - u.team] if t.alive):
                return False
            need = int(k.get("min_enemies", 0))
            if need <= 0:
                return True
            return sum(1 for e in eng.units
                       if e.team != u.team and e.hp > 0
                       and _dist(u.x, u.y, e.x, e.y) <= r) >= need
        return False

    def _hand_specs(self):
        """The 4 cards currently in hand (the rest are cycling)."""
        return [self.specs[i] for i in self.cycle[:4]]

    def _pocket_lane(self, eng, team: int = 1):
        """Lane x this bot may push TROOPS into past the river, or None.

        Taking one of the defender's princess towers grants deployment territory across the river on
        that tower's side (the "pocket"). This bot already reaches over with SPELLS -- it aims them
        at the X-Bow and at the deepest attacker -- but it never walked a troop into a pocket it had
        earned, so a won lane went unpunished and the policy never had to defend one.

        Returns the lane x of an OPEN pocket (engine coords), preferring one that already has our
        pressure in it, else None when no defender princess is down.
        """
        try:
            foe = eng.towers[1 - int(team)][:2]                # the DEFENDER's princesses
        except Exception:
            return None
        dead = [t for t in foe if not t.alive]
        if not dead:
            return None
        return float(self.rng.choice(dead).x)

    def _play(self, eng, spec, x: float, y: float) -> bool:
        """Deploy + send that card to the back of the cycle. EVERY deploy goes through here, so no
        branch can bypass the cycle.

        An EVOLUTION slot charges by playing its base card `evo_cycles` times; the next play of
        that card fields the `_evo` spec instead. There are now up to TWO such slots -- the
        dedicated one and the Wild slot (I8) -- and they charge independently, because they are
        different cards with their own Cycles numbers.

        A HERO slot needs nothing here: the card in it IS the hero from its first play, so
        `__init__` swapped the spec once and every path below already carries it.
        """
        idx = next((i for i, s in enumerate(self.specs) if s is spec), -1)
        for _sidx, _spec, _cyc, _chg in ((self.evo_idx, self.evo_spec, self.evo_cycles, "evo_charge"),
                                         (self.wild_evo_idx, self.wild_evo_spec,
                                          self.wild_evo_cycles, "wild_evo_charge")):
            if idx != _sidx or _spec is None:
                continue
            if getattr(self, _chg) >= _cyc and eng.elixir[1] >= _spec.elixir:
                spec = _spec                                  # the charged Evolution takes the slot
            break
        if not eng.deploy(1, spec, x, y):
            return False
        if idx == self.evo_idx and self.evo_spec is not None:
            self.evo_charge = 0 if spec is self.evo_spec else self.evo_charge + 1
        elif idx == self.wild_evo_idx and self.wild_evo_spec is not None:
            self.wild_evo_charge = 0 if spec is self.wild_evo_spec else self.wild_evo_charge + 1
        if idx >= 0 and idx in self.cycle:
            self.cycle.remove(idx)
            self.cycle.append(idx)
        return True

    # ---- observation (what a human sees: the agent's deploys) -----------------
    def _observe(self, eng) -> None:
        d = eng.last_deploy.get(0)
        if not d:
            return
        spec, x, _y, t = d
        if t == self._seen_deploy_t:
            return
        self._seen_deploy_t = t
        self._spend.append((t, float(spec.elixir), float(x)))
        if len(self._spend) > 24:
            self._spend.pop(0)
        if spec.base == "tornado":
            self._nado_seen = True
        if spec.siege:
            self._xbow_ever = True

    def _usable(self, affordable, elix):
        """Affordable specs minus the RESERVED siege answer while counter-holding (released when
        elixir overflows -- a human doesn't sit at 10 forever holding one card)."""
        if not (self.hold_counter and self._xbow_ever) or self._reserved is None or elix >= 9.5:
            return affordable
        return [s for s in affordable if s is not self._reserved]

    def _try_anti_siege(self, eng, affordable, elix) -> bool:
        if not self.anti_siege_know:
            return False
        team = 1
        bows = [u for u in eng.units
                if u.team == 0 and u.spec.siege and u.hp > 0 and u.deploy_left <= 0]
        if not bows:
            self._siege_seen_t = None
            return False
        self._xbow_ever = True
        xb = min(bows, key=lambda u: u.y)                        # the most forward bow
        if self._siege_seen_t is None:
            self._siege_seen_t = eng.t
        if eng.t - self._siege_seen_t < self.reaction_s:
            return False
        # supported bow + a big spell in hand -> spell it (fireball/lightning value); else heaviest
        # troop dropped ON TOP so it tanks/kills the bow (the classic anti-siege answer).
        support = sum(1 for u in eng.units
                      if u.team == 0 and u is not xb and u.hp > 0
                      and abs(u.x - xb.x) + abs(u.y - xb.y) < 0.16)
        spells = [s for s in affordable if s.kind == "spell" and s.spell_dmg >= 300]
        if support >= 2 and spells:
            s = max(spells, key=lambda sp: sp.spell_dmg)
            self._play(eng, s, xb.x, xb.y)
            self._siege_seen_t = None                            # re-arm (reacts again if the bow survives)
            return True
        troops = [s for s in affordable if s.kind == "troop" and not s.building_only and not s.flying]
        if troops:
            tank = max(troops, key=lambda s: s.hp)
            self._play(eng, tank, xb.x, max(0.08, xb.y - 0.05))
            self._siege_seen_t = None
            return True
        return False

    def _try_punish(self, eng, affordable) -> bool:
        if not self.punish_know or eng.t < self._punish_cd:
            return False
        recent = [(t, e, x) for (t, e, x) in self._spend if eng.t - t <= 6.0]
        tot = sum(e for _, e, _ in recent)
        if tot < 8.0:
            return False
        mean_x = sum(x for _, _, x in recent) / len(recent)
        lane = eng.lanes[1] if mean_x < 0.5 else eng.lanes[0]    # punish the OPPOSITE lane
        offense = [s for s in affordable if s.kind != "spell"]
        if not offense:
            return False
        wc = [s for s in offense if s.building_only] or offense
        s = max(wc, key=lambda sp: sp.elixir)                    # commit the punish, don't poke
        self._play(eng, s, lane, 0.46)
        self._punish_cd = eng.t + 15.0
        return True

    def act(self, eng) -> None:
        team = 1
        if self.adaptive:
            self._observe(eng)
        # THE ABILITY BUTTON. Not gated on `adaptive`: an enemy champion that never uses its
        # ability is a different card, and the eval benchmark runs non-adaptive bots. It also does
        # not `return` -- the ability spends its own elixir and leaves the hand alone, so the bot
        # still takes its card action this step. Read `elix` AFTER, or the affordability list
        # would be computed against elixir the ability has already spent.
        self._try_ability(eng, team)
        elix = eng.elixir[team]
        affordable = [s for s in self._hand_specs() if s.elixir <= elix]
        if not affordable:
            return
        if self.adaptive and self._try_anti_siege(eng, affordable, elix):
            return
        usable = self._usable(affordable, elix)
        # DEFEND: an enemy (team 0) unit has entered our half (y < 0.5)
        threats = [u for u in eng.units if u.team == 0 and u.y < 0.5]
        if threats:
            deepest = min(threats, key=lambda u: u.y)             # closest to our king
            troops = [s for s in usable if s.kind == "troop" and not s.building_only]
            if troops:
                s = min(troops, key=lambda s: s.elixir)
                self._play(eng, s, deepest.x, max(0.12, deepest.y - 0.06))
                return
            spells = [s for s in usable if s.kind == "spell"]
            if spells and len(threats) >= 3:
                s = min(spells, key=lambda s: s.elixir)
                self._play(eng, s, deepest.x, deepest.y)
                return
        if self.adaptive and self._try_punish(eng, affordable):
            return
        # BACKLINE SUPPORT OPENING (control/beatdown): once, early, drop a mid-cost ranged support BEHIND the
        # king (the "Musketeer behind the tower" open) -- realistic pressure AND the setup the agent learns to
        # punish (rocket the support + tower for a 2-for-1).
        if (not self._backline_done and not threats and eng.t < self._backline_until
                and self.style in ("control", "beatdown") and self.rng.random() < self._backline_prob):
            supports = [s for s in usable if s.kind == "troop" and not s.building_only
                        and 4 <= s.elixir <= 6 and not s.flying]
            if supports:
                self._backline_done = True
                self._play(eng, self.rng.choice(supports), self.rng.choice(eng.lanes), 0.10)
                return
        # PUMP OPENING: an Elixir Collector in the deck is placed like a real player -- at spare elixir,
        # under no pressure, at most one on the field. Placement VARIETY is deliberate: behind the KING
        # (king-adjacent = the agent must NOT rocket it), the PRINCESS pocket (rocketable together with
        # the tower = the double hit), or mid-back (the solo-rocket case) -- all three answers train.
        pump = next((s for s in usable if s.gen_every > 0), None)
        if (pump is not None and not threats and elix >= pump.elixir + 2
                and not any(u.team == team and u.spec.gen_every > 0 for u in eng.units)
                and self.rng.random() < 0.35):
            spot = self.rng.choice(((0.5 + self.rng.choice([-0.06, 0.06]), 0.06),    # hugging the king
                                    (self.rng.choice(eng.lanes), 0.13),              # princess pocket
                                    (self.rng.choice([0.35, 0.62]), 0.10)))          # mid-back
            self._play(eng, pump, spot[0], spot[1])
            return        # ATTACK
        if self.style == "beatdown" and elix < 9.5:
            return                                                # save up for a big push
        offense = [s for s in usable if s.kind != "spell" and s.gen_every <= 0]
        if not offense:
            return
        # DEPLOY-ANYWHERE cards (Miner / Goblin Drill, KB flag) tunnel STRAIGHT to the defender's tower --
        # they never walk the lane. Dropping one at the bridge like a Knight, which is what the generic
        # offense path did, means the agent never trains on the scenario the card actually creates: an
        # enemy suddenly ON its tower with no approach to read. Placed on a live princess tower here.
        anywhere = [s for s in offense if s.deploy_anywhere]
        if anywhere and self.rng.random() < self.anywhere_prob:
            tw = [t for t in eng.towers[1 - team][:2] if t.alive]
            if tw:
                target = self.rng.choice(tw)
                if self._play(eng, self.rng.choice(anywhere), target.x, target.y):
                    return
        splitting = self.adaptive and self.split_know and self._nado_seen
        if splitting:
            self._flip = not self._flip                          # tornado seen -> stop stacking one lane
            lane = eng.lanes[0] if self._flip else eng.lanes[1]
        else:
            lane = self.rng.choice(eng.lanes)
        if self.style == "beatdown":
            tank = max(offense, key=lambda s: s.hp)               # heaviest unit BEHIND the king (deep back)
            pk = self._pocket_lane(eng, team)
            if pk is not None and float(self.rng.random()) < 0.35:
                self._play(eng, tank, pk, 0.60)   # tank straight into the pocket, no walk-up needed
            else:
                self._play(eng, tank, lane, 0.10)
            if splitting:                                         # split the support into the OTHER lane
                cheap = [s for s in offense if s is not tank and s.elixir <= 4]
                if cheap and eng.elixir[team] >= min(s.elixir for s in cheap):
                    self._play(eng, self.rng.choice(cheap), 1.0 - lane, 0.14)
        elif self.style == "siege":
            sieges = [s for s in offense if s.siege] or offense
            self._play(eng, self.rng.choice(sieges), lane, 0.42)
        else:                                                     # cycle / control: chip at the bridge
            wc = [s for s in offense if s.building_only] or offense
            pick = self.rng.choice(wc)
            # POCKET PRESSURE: with a princess already down, drop the chip INSIDE the pocket rather
            # than at the bridge -- past the river on the won side, which is the whole point of
            # taking a tower. Not every time: a bot that always pockets is as predictable as one
            # that never does, and the bridge play is still correct when the defence is set.
            pk = self._pocket_lane(eng, team)
            if pk is not None and float(self.rng.random()) < 0.55:
                self._play(eng, pick, pk, 0.62)
            else:
                self._play(eng, pick, lane, 0.46)
            if splitting:                                         # two-lane chip so one tornado can't catch all
                cheap = [s for s in offense if s is not pick and s.elixir <= 3]
                if cheap and eng.elixir[team] >= min(s.elixir for s in cheap):
                    self._play(eng, self.rng.choice(cheap), 1.0 - lane, 0.46)


def make_opponent(cfg, db, rng, pool: List[dict], level: "int | None" = None,
                  adaptive: bool = False) -> ScriptedBot:
    """Sample a meta deck (weighted by its popularity) and pilot it per its inferred style. Each of its
    cards rolls a RANDOM level (sim.enemy_levels weighted by sim.enemy_level_weights -- default 13-16
    with 14 most likely, 16 least), so the opponent's card levels vary like a real ladder opponent.

    ``level`` (FAIR eval): if given, ALL the opponent's cards use this fixed level instead of the rolled
    ladder levels -- removing the level handicap. The roll still happens first so rng consumption (and
    thus the sampled deck sequence) is IDENTICAL to the handicapped path, making fair-vs-ladder an
    apples-to-apples comparison on the same matchups.

    ``adaptive`` (TRAINING only -- the eval benchmark never passes it, so eval curves stay comparable):
    each bot rolls sim.adaptive_prob to become an ADAPTIVE bot (counter-holding / anti-siege / dump
    punish / split-push, see ScriptedBot). The roll uses a DERIVED rng so the deck/level sequence
    stays identical whether or not adaptation is enabled."""
    if not pool:
        from .meta_decks import load_meta_decks
        pool = load_meta_decks(cfg, db)
    weights = [max(0.01, float(d.get("weight", 1.0))) for d in pool]
    # DECK EXPLOITERS (sim.deck_pfsp_power). AlphaStar's league runs exploiter agents whose job is
    # to find and punish the main agent's weaknesses rather than to win overall, and that diversity
    # is what forces novel strategy instead of convergence on one comfortable style.
    #
    # Self-play cannot supply it HERE: a frozen self can only pilot OUR deck, so it trains the
    # mirror -- one matchup of ~100, and icebow is rare on ladder. Raising selfplay_prob to Dota-
    # like levels was tried (0.5 + PFSP power 2.0) and drove the benchmark 19.3% -> 1.3% overnight.
    #
    # The league that matters here is the META DECK POOL. So: exploit it. A deck we keep LOSING to
    # is a weakness in exactly AlphaStar's sense, and it gets sampled more often -- popularity
    # weight times a loss-rate factor. Decks we already beat keep their popularity weight, so the
    # distribution stays recognisably ladder-shaped rather than collapsing onto our worst matchup
    # (which is the failure mode the 0.5/power-2.0 self-play mix demonstrated).
    # TRAINING ONLY, gated on `adaptive` exactly like the adaptive bots are. The eval benchmark
    # builds its opponents through this same function and never passes adaptive=True, "so eval
    # curves stay comparable" (see the adaptive docstring). Weighting the EVAL pool toward the decks
    # we lose to would sink the benchmark for reasons that have nothing to do with the policy and
    # make every run incomparable with every previous one -- which is exactly the mistake the
    # adaptive flag exists to prevent.
    _pw = float(cfg.get("sim", "deck_pfsp_power", default=0.0)) if adaptive else 0.0
    if _pw > 0.0:
        _st = getattr(cfg, "_deck_record", None)
        if _st:
            for i, d in enumerate(pool):
                rec = _st.get(str(d.get("name", i)))
                if rec and rec[1] >= 3:                    # need a few games before trusting it
                    lossrate = 1.0 - (float(rec[0]) / float(rec[1]))
                    weights[i] *= (0.25 + lossrate) ** _pw
    deck = rng.choices(pool, weights=weights, k=1)[0]
    _deck_name = str(deck.get("name", "?"))
    lv = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
    lw = cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1])
    levels = [rng.choices(lv, weights=lw, k=1)[0] for _ in deck["cards"]]
    if level is not None:
        levels = [int(level)] * len(deck["cards"])
    is_adaptive = adaptive and rng.random() < float(cfg.get("sim", "adaptive_prob", default=0.65))
    _bot = ScriptedBot(cfg, db, rng, deck["cards"], deck["style"], levels, adaptive=is_adaptive,
                       evo=deck.get("evo"),       # a DECLARED slot, if a source ever names one
                       evo_candidates=deck.get("evo_candidates"),   # else drawn from the legal set
                       hero_candidates=deck.get("hero_candidates"),  # I8: the Hero + Wild slots
                       support=deck.get("support"))                  # I8: the measured tower troop
    _bot.deck_name = _deck_name          # so a result can be attributed back to the deck (deck PFSP)
    return _bot


class SelfPlayOpponent:
    """Pilots team 1 with a FROZEN copy of the agent's policy. The policy only ever learned team 0's
    point of view (you at the bottom, deploy low, attack up), so we show it a 180-degree MIRRORED board
    (sim/view.py) where team 1 sits at the bottom, run the exact same greedy gate/card/cell choice the
    trainer uses, then transform the chosen cell back to the engine frame before deploying. It plays the
    AGENT's deck (the only deck the policy understands) at random ladder levels, and cycles its hand the
    same way the env does, so it is a genuine self-mirror -- a strong, adaptive sparring partner."""

    def __init__(self, cfg, env, net, rng):
        self.rng = rng
        self.net = net                                           # frozen DQN (policy + gate), eval mode
        self.actions = env.actions
        self.db = env.db
        self.n_cards = env.n_cards
        self.gw, self.gh = env.gw, env.gh
        self.n_cells = env.n_cells
        self.obs_shape = env.obs_shape
        self.threat_dim = env.threat_dim
        self.use_detector = env.use_detector          # Stage 3: mirror the identity block for team 1
        self.detector_cards = env.detector_cards
        self.det_recall = env.det_recall              # mirror the sim detector-noise so a snapshot self sees
        self.det_precision = env.det_precision         # the same sparse/noisy identity signal it trained on
        self.det_recall_by_card = env.det_recall_by_card   # ...including the per-card recall override
        self.use_interactions = env.use_interactions   # mirror the troop-interaction block for team 1
        self.use_tower_obs = getattr(env, "use_tower_obs", False)   # ...and the crown-tower HP block
        self.use_canvas = getattr(env, "use_canvas", False)         # ...and the semantic obs CANVAS
        self.canvas_presence_recall = getattr(env, "canvas_presence_recall", 1.0)
        # Own canvas history: the opponent is rebuilt each env.reset(), so this starts empty per match.
        self._canvas_stack = detect_obs.CanvasStack(detect_obs.canvas_stack_len(cfg),
                                                    detect_obs.canvas_stack_dt(cfg))
        self.use_pred_canvas = detect_obs.predictive_enabled(cfg)
        self.pred_dt = detect_obs.predictive_dt(cfg)
        self.pred_horizon = detect_obs.eta_horizon(cfg)
        self.use_hp_canvas = detect_obs.hp_enabled(cfg)
        self.sight_range = env.sight_range
        self.agent_dt = env.agent_dt
        self.predict_horizon = env.predict_horizon
        self.identity_front = getattr(env, "identity_front", card_threat.IDENTITY_FRONT_DEFAULT)
        self._dr = env.domain_rand                    # share the match's visual restyle (resampled by env.reset)
        self._prev_ident_depth = 0.0
        self._opp_mem = card_threat.OpponentMemory(env.db)   # per-match opponent memory (mirrors team 0)
        self.anywhere_ids = env.anywhere_ids
        self.deck_keys = env.deck_keys
        lv = cfg.get("sim", "enemy_levels", default=[13, 14, 15, 16])
        lw = cfg.get("sim", "enemy_level_weights", default=[3, 5, 2, 1])
        levels = [rng.choices(lv, weights=lw, k=1)[0] for _ in self.deck_keys]
        self.specs = [build_spec(self.db, k, lvl) for k, lvl in zip(self.deck_keys, levels)]
        # The snapshot must choose actions under the SAME mask the trainer applies (see
        # train_sim_ppo.masked_logits): card = in-hand AND affordable, cell = the deployable set.
        # Kept as plain lists here and cached as tensors on first act() (torch is imported lazily).
        self._costs = [float(s.elixir) for s in self.specs]
        self._yourhalf = self.actions.deployable_mask(False)
        # POCKET, for the OPPONENT. Taking one of OUR princess towers grants team 1 deployment
        # territory across the river on that side, exactly as it grants us one for taking theirs.
        # Without this the sim is asymmetric: we could punish a won lane and the opponent could not,
        # so the policy would learn to defend a board state that never arrives.
        #
        # Four variants precomputed, chosen per act() from the LIVE board -- towers die mid-match,
        # so this cannot be cached once like _yourhalf was.
        self._half_variants = [self.actions.deployable_mask(False, (bool(c & 2), bool(c & 1)))
                               for c in range(4)]
        self._mask_cache: dict = {}
        self._gate_tau = float(cfg.get("sim", "ppo_gate_threshold", default=0.25))
        # exposed so the env's matchup doctrine (reads opponent .style / .cards) still works
        from .meta_decks import classify_style
        self.cards = list(self.deck_keys)
        self.style = classify_style(self.db, self.deck_keys)
        # PHYSICAL card slots (8), not the 10 policy identities -- an Evolution shares its base
        # card's cycle position and only appears once that slot has banked `cycles` plays.
        self.slots = self.db.deck_slots()
        self.n_slots = max(1, len(self.slots))
        self.slot_base_id = [self.deck_keys.index(s["base"]) for s in self.slots]
        self.slot_evo_id = [self.deck_keys.index(s["evo"]) if s["evo"] in self.deck_keys else -1
                            for s in self.slots]
        self.slot_cycles = [int(s["cycles"]) for s in self.slots]
        self.slot_of = {}
        for si in range(self.n_slots):
            self.slot_of[self.slot_base_id[si]] = si
            if self.slot_evo_id[si] >= 0:
                self.slot_of[self.slot_evo_id[si]] = si
        self.evo_charge = [0] * self.n_slots
        self.cycle = list(range(self.n_slots))
        self.rng.shuffle(self.cycle)

    def _slot_card_id(self, slot: int) -> int:
        evo = self.slot_evo_id[slot]
        if evo >= 0 and self.evo_charge[slot] >= self.slot_cycles[slot]:
            return evo
        return self.slot_base_id[slot]

    def _hand_ids(self):
        return [self._slot_card_id(s) for s in self.cycle[:4]]

    def _play_slot(self, card_id: int) -> None:
        slot = self.slot_of.get(card_id)
        if slot is None:
            return
        if card_id == self.slot_evo_id[slot]:
            self.evo_charge[slot] = 0
        elif self.slot_evo_id[slot] >= 0:
            self.evo_charge[slot] += 1
        self.cycle.remove(slot)
        self.cycle.append(slot)

    def act(self, eng) -> None:
        import torch

        oh, ow, _ = self.obs_shape
        obs = view.render_obs(eng, oh, ow, team=1, dr=self._dr)   # same match 'arena look' as team 0
        if self.use_canvas:                                       # mirrored semantic canvas for team 1
            ch = view.semantic_channels(eng, oh, ow, team=1, rng=self.rng,
                                        presence_recall=self.canvas_presence_recall)
            if self.use_pred_canvas:                              # ...and the mirrored FORECAST slice
                units, mine_t, en_t = view.interaction_state(eng, 1, self.detector_cards, self.rng,
                                                             self.det_recall, self.det_recall_by_card)
                pred = detect_obs.predictive_channels(units, mine_t, en_t, self.db, oh, ow,
                                                      dt_s=self.pred_dt, horizon_s=self.pred_horizon)
                ch = np.concatenate([ch, detect_obs.channels_to_uint8(pred)], axis=2)
            if self.use_hp_canvas:                            # mirrored HP truth for team 1
                hp = detect_obs.hp_channels(view.hp_state(eng, 1, self.rng,
                                                          self.canvas_presence_recall), oh, ow)
                ch = np.concatenate([ch, detect_obs.channels_to_uint8(hp)], axis=2)
            obs = np.concatenate([obs, self._canvas_stack.push(ch, eng.t)], axis=2)
        hand = np.zeros(self.n_cards, np.float32)
        for i in self._hand_ids():
            hand[i] = 1.0
        nxt = cycle_vector([self._slot_card_id(s) for s in self.cycle], self.n_cards)   # graded upcoming-order
        elx = np.array([eng.elixir[1] / 10.0], np.float32)
        base_dim = self.threat_dim \
            - ((card_threat.IDENTITY_DIM + card_threat.OPP_MEMORY_DIM) if self.use_detector else 0) \
            - (interactions.INTERACTION_DIM if self.use_interactions else 0) \
            - (view.TOWER_DIM if self.use_tower_obs else 0)
        thr = view.threat_vector(eng, base_dim, team=1)
        if self.use_detector:
            ident = card_threat.identity_threat_vector(
                view.apply_detector_noise(view.identity_items(eng, 1, self.detector_cards,
                                                              self.identity_front),
                                          self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                          self.det_recall_by_card),
                self.db, prev_depth=self._prev_ident_depth, dt=self.agent_dt, horizon=self.predict_horizon)
            self._prev_ident_depth = float(ident[7])
            mem = self._opp_mem.update(
                view.apply_detector_noise(view.opponent_memory_items(eng, 1, self.detector_cards),
                                          self.det_recall, self.det_precision, self.rng, self.detector_cards,
                                          self.det_recall_by_card), dt=self.agent_dt)
            # Slot 5 mirrors the opponent-elixir signal from team 1's perspective.
            mem[5] = eng.elixir[0] / 10.0
            thr = np.concatenate([thr, ident, mem]).astype(np.float32)
        if self.use_interactions:                      # mirrored: team 1 sees ITS towers as 'mine'
            units, mine_t, en_t = view.interaction_state(eng, 1, self.detector_cards, self.rng,
                                                         self.det_recall, self.det_recall_by_card)
            ivec = interactions.interaction_vector(units, mine_t, en_t, self.db)
            thr = np.concatenate([thr, ivec]).astype(np.float32)
        if self.use_tower_obs:                         # ...same mirroring for the tower block
            thr = np.concatenate([thr, view.tower_vector(eng, 1)]).astype(np.float32)

        dev = next(self.net.parameters()).device
        obs_t = torch.from_numpy(obs).float().permute(2, 0, 1).unsqueeze(0).to(dev) / 255.0
        hand_t = torch.from_numpy(hand).unsqueeze(0).to(dev)
        nxt_t = torch.from_numpy(nxt).unsqueeze(0).to(dev)
        elx_t = torch.from_numpy(elx).unsqueeze(0).to(dev)
        thr_t = torch.from_numpy(thr).unsqueeze(0).to(dev)
        with torch.no_grad():
            cq, ceq, gq = self.net(obs_t, hand_t, nxt_t, elx_t, thr_t)
        cache = self._mask_cache
        if not cache:
            cache["cost"] = torch.tensor(self._costs, dtype=torch.float32, device=dev)
            cache["half"] = torch.tensor(self._yourhalf, dtype=torch.bool, device=dev)
            cache["half_var"] = [torch.tensor(h, dtype=torch.bool, device=dev)
                                 for h in self._half_variants]
        # WHICH POCKETS TEAM 1 HAS EARNED: our princesses that are dead. Sides SWAP here -- this
        # opponent chooses cells in our local frame and mirrors them with (1-x, 1-y) on the way
        # out, so a pocket on the engine's left is on this frame's right.
        try:
            _mine = eng.towers[0][:2]                     # OUR princesses
            _eng_left = any((not t.alive) and float(t.x) < 0.5 for t in _mine)
            _eng_right = any((not t.alive) and float(t.x) >= 0.5 for t in _mine)
            _code = (2 if _eng_right else 0) + (1 if _eng_left else 0)   # swapped, see above
        except Exception:
            _code = 0
        _half = cache["half_var"][_code] if _code else cache["half"]
        # AFFORDABILITY, not just in-hand. Without the cost term the snapshot argmaxes onto a card it
        # cannot pay for, eng.deploy() returns False and the tick is silently wasted -- that made the
        # frozen self far weaker than the agent it is meant to mirror (inflating training winrate).
        playable = (hand_t[0] >= 0.5) & (cache["cost"] <= float(eng.elixir[1]) + 1e-6)
        if not bool(playable.any()):
            return                                   # nothing playable: the trainer masks the play gate
        cq = cq.masked_fill(~playable.unsqueeze(0), _NEG)
        # PPO snapshots (net._ppo) carry LOGITS: the gate is a PROBABILITY thresholded at
        # sim.ppo_gate_threshold (a raw logit compare is tau=0.5, which under-deploys badly).
        # DQN snapshots keep the additive Q rule (wait_q vs play_q + best card + best cell).
        if getattr(self.net, "_ppo", False):
            wait = bool(torch.sigmoid(gq[0, 1] - gq[0, 0]) <= self._gate_tau)
        else:
            # PER-CARD maps: the additive Q rule needs the cell map of the card it would
            # actually play, so the card argmax has to come FIRST now.
            wait = bool(gq[0, 0] >= gq[0, 1] + cq[0].max() + ceq[0, int(cq[0].argmax())].max())
        if wait:
            return                                               # gate says WAIT
        card = int(cq[0].argmax())
        # Mask cells to the legal set BEFORE the argmax (what the trainer does). Clamping afterwards
        # folds many illegal cells onto one boundary cell and distorts the placement the policy chose.
        ceq_c = ceq[0, card]                                     # this card's placement map
        if card not in self.anywhere_ids:
            ceq_c = ceq_c.masked_fill(~_half, _NEG)
        cell = int(ceq_c.argmax())

        cell = self.actions.deploy_clamp(card in self.anywhere_ids, cell)
        lnx, lny = self.actions.cell_center(cell % self.gw, cell // self.gw)
        ex, ey = 1.0 - lnx, 1.0 - lny                            # mirror the local cell back to engine coords
        if eng.deploy(1, self.specs[card], ex, ey):
            self._play_slot(card)

