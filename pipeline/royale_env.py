"""RoyaleSim (research/ext/Royale, the owner's friend's Rust engine) behind the interface ``e1_eval.run_match`` drives,
so the S1 policy, the live deploy rule and the ghost pool run on it UNCHANGED. L68.

Mirrors ``scratchpad/gauntlet/L62/engine_env.py`` + ``e1_pool.PoolV1Mixin``: ghosts fire at their recorded tick, a
not-enough-elixir refusal is retried each tick for up to ``elixir_slack`` ticks, the episode starts at
``warmup_ticks`` (90: the real engine refuses every deploy before 4.5 s; RoyaleSim's LOGIC_BATTLE_START_COOLDOWN_MS is
the same 4,500 ms). Coordinates: side 0 / Blue at low y in both, but RoyaleSim is 18,000 units per tile against the
pool's 1,000 (arena 324,000 x 576,000; kings at (162000, 54000) = tile (9, 3), measured L68) -- hence ``SCALE``.
Overtime: the pinned runtime ships120 s, matching the 2026 corpus. Normal play stops at tick6000;
level-crown matches then resolve through the upstream tower drain (judge tick6147, state tick6148).

What the engine cannot play is a DECK problem, not a runtime one: ``reset`` refuses an entry whose decks name a card
the catalogue lacks, unless ``subs`` maps it to one it has (e.g. {"Tornado": "Arrows"} for an engine without Tornado; RoyaleSim plays real Tornado since 2026-09-23, and no run passes subs).
Evolution / hero forms: ``forms_mode`` "base" (default) plays every card as the base card, as before RoyaleSim had
forms. "deck" plays each entry's decked form (``@evolution`` -> 1, ``@hero`` -> 2; pool items' ``form``) through
``MatchSetup.forms``: an evolved card plays its evolution on every third play of it (the engine's counter,
``PlayerState.evo``); a hero has an ability button. Opt-in ``hero_abilities`` presses ready, affordable buttons near enemies;
its default False preserves the original command and RNG paths. A form the engine refuses (RoyaleSim
369fe33: only Tesla / Knight / Skeletons evolve, only Knight has a hero, of icebow's cards) falls back to the base card
and is recorded per reset in ``form_fallbacks`` [(side, name, form)]; ``loaded_forms[side]`` = what was loaded, in
``deck_ids`` order (e1_eval feeds it to the policy's form inputs).

Uses the reviewed runtime selected by pipeline.royale_runtime; missing or stale installs fail explicitly.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from typing import Optional

from pipeline.royale_runtime import activate as _activate_runtime

_activate_runtime()

from royalegym.protocol import (BLUE, EMPTY_CARD, HAND_SIZE, STATUS_HERO, DeployCommand, DeployStatus, EntityKind,
                                MatchSetup, ShuffleMode, Winner)
from royalegym.rust_engine import RustEngine

from pipeline.e1_pool import ours

SCALE = 18                      # RoyaleSim units per pool/real-engine unit (18,000 vs 1,000 per tile)
# RoyaleSim's elixir regen, (from_tick, elixir per tick) -- MEASURED T12b (.foreman/scratch/T12b/elixir_schedule_probe.py:
# every tick of a mirror all-spell match from tick 0 to its end, both sides): start 6.000 at tick 0 (as the real engine);
# 1/56 per tick on [0, 2400), 1/28 from 2400, and from tick 4800 upstream's triple rate (RoyaleSim e4dc73b,
# match.MANA_REGEN_MS_OVERTIME 9300 ms a bar = 1/18.6 per tick, the real engine's 0.0537); play stops at tick6000.
# It replaced our 2026-09-25 local patch (3/56). The real engine's schedule is opp_elixir_count.REGEN_SCHEDULE;
# e1_eval's opp-elixir counter uses this one on RoyaleSim envs.
REGEN_SCHEDULE = ((0, 1 / 56), (2400, 1 / 28), (4800, 1 / 18.6), (6000, 0.0))
NOT_ENOUGH_ELIXIR = 13         # the real engine's code, so e1_eval / the ghost retry read it unchanged
NOT_IN_HAND = 1003              # deck_index names a card that is not in the hand right now
REFUSED_BASE = 2000             # 2000 + DeployStatus for every other refusal
FORMS_MODES = ("base", "deck")
ABILITY_POLICIES = ("generic", "v2")
# Ability press policy v2 (L70): per-ability calibrated P(press within 1 s) from scratchpad/gauntlet/L70/abilities
# (ability_policy.py + ability_models_v2.json, CALIBRATION_V2.md). RoyaleSim card name -> the model's key; a button whose
# card is not here (e.g. a hero Ice Wizard: no pro data) keeps the generic rule and is counted (ability_fallback_generic).
V2_KEYS = {"Giant": "giant-hero", "Balloon": "balloon-hero", "Bowler": "bowler-hero", "Goblins": "goblins-hero",
           "Knight": "knight-hero", "Musketeer": "musketeer-hero", "Tombstone": "tombstone-hero",
           "Valkyrie": "valkyrie-hero", "Wizard": "wizard-hero", "Berserker": "berserker-hero",
           "BarbLog": "barbarian-barrel-hero", "DarkPrince": "dark-prince-hero", "IceGolemite": "ice-golem-hero",
           "EliteArcher": "magic-archer-hero", "MegaMinion": "mega-minion-hero", "MiniPekka": "mini-pekka-hero",
           "ArcherQueen": "archer-queen", "GoldenKnight": "golden-knight", "SkeletonKing": "skeleton-king",
           "MightyMiner": "mighty-miner", "Monk": "monk", "LittlePrince": "little-prince", "Goblinstein": "goblinstein",
           "BossBandit": "boss-bandit"}
V2_REPRESS_TICKS = 60      # boss-bandit's second charge: phase2_build.eligible (>= 3 s after the first press)
_POLICY = None


def _v2_policy():
    """The L70 ability_policy module, loaded by path on first use (not at import: nothing else needs it)."""
    global _POLICY
    if _POLICY is None:
        import importlib.util
        from pathlib import Path
        p = Path(__file__).resolve().parents[1] / "scratchpad/gauntlet/L70/abilities/ability_policy.py"
        spec = importlib.util.spec_from_file_location("l70_ability_policy", p)
        _POLICY = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_POLICY)
    return _POLICY


FORM_OF = {"": 0, "base": 0, "evolution": 1, "hero": 2}   # name suffix / pool item ``form`` -> MatchSetup.forms value
# (card_id, form) -> whether this process's RoyaleSim build loads it. ponytail: one engine build per process assumed.
_FORM_LOADS: dict[tuple[int, int], bool] = {}
RESULT_CODE_NAMES = {NOT_ENOUGH_ELIXIR: "not_enough_elixir", NOT_IN_HAND: "not_in_hand",
                     **{REFUSED_BASE + s: s.name.lower() for s in DeployStatus}}


def deal_order(slugs: list[str], plays: list[str]) -> Optional[list[int]]:
    """A deck order (indices into ``slugs``) under which RoyaleSim's ShuffleMode.NONE deal -- hand = the first four,
    then a queue: a played card's slot takes the queue's front and the card joins its back (the real game's cycle,
    measured L68) -- has every recorded play in hand when it is made. The pool's ``final`` order does NOT: it only
    reproduces the opening hand under the real engine's own seeded deal. None if no order fits.
    ponytail: first fit of 70 hands x 24 queues; cards the recording never forces are ordered arbitrarily."""
    from itertools import combinations, permutations
    idx = [slugs.index(p) for p in plays]
    for hand in combinations(range(8), 4):
        rest = [i for i in range(8) if i not in hand]
        for queue in permutations(rest):
            h, q = set(hand), list(queue)
            for i in idx:
                if i not in h:
                    break
                h.remove(i)
                h.add(q.pop(0))
                q.append(i)
            else:
                return list(hand) + list(queue)
    return None


class UnsupportedDeck(ValueError):
    """An entry's deck names a card RoyaleSim does not load (and ``subs`` does not cover)."""


class _Core:
    """The ``env.eng`` face: act / observe / last_episode, as the socket client to the real engine offers."""

    def __init__(self, env: "RoyalePoolEnv"):
        self.env = env
        self.last_episode: Optional[dict] = None

    def act(self, *, side: int, deck_index: int = -1, x: int = 0, y: int = 0,
            ability_button: Optional[int] = None) -> dict:
        env = self.env
        if ability_button is not None:
            (r,) = env.core.step([DeployCommand(side, HAND_SIZE + ability_button, 0, 0)], 0)
            code = NOT_ENOUGH_ELIXIR if r.status == DeployStatus.NOT_ENOUGH_ELIXIR else REFUSED_BASE + int(r.status)
            return {"accepted": r.status == DeployStatus.OK, "result_code": 0 if r.status == DeployStatus.OK else code}
        cid = env.deck_ids[side][deck_index]
        before = env.core.state()
        player = before.players[side]
        hand = player.hand
        if cid not in hand:
            return {"accepted": False, "result_code": NOT_IN_HAND}
        if env.feature_version >= 3:
            form = (2 if env.forms_mode == "deck" and env.loaded_forms[side][deck_index] == 2
                    else int(any(v[0] == cid and v[2] for v in player.evo)))
        (r,) = env.core.step([DeployCommand(side, hand.index(cid), int(x) * SCALE, int(y) * SCALE)], 0)
        if r.status == DeployStatus.OK:
            if env.ability_policy == "v2":      # the v2 press model's deployment clock + per-deployment denominator
                env._last_play[side, cid] = int(before.tick)
                if cid in env._hero_ids[side]:
                    env.ability_deployments[side][env.names[cid]] += 1
            if getattr(env, 'behaviour_telemetry', None) is not None:
                env.behaviour_telemetry.play(before.tick, side, env.names[cid], int(x), int(y),
                                             elixir=before.players[side].elixir_milli / 1000.0)
            if env.feature_version >= 3:
                env.public_plays.append(dict(tick=int(before.tick), side=side, card=env.names[cid], form=form,
                                             x=int(x), y=int(y), accepted=True, play_index=len(env.public_plays)))
            return {"accepted": True, "result_code": 0}
        code = NOT_ENOUGH_ELIXIR if r.status == DeployStatus.NOT_ENOUGH_ELIXIR else REFUSED_BASE + int(r.status)
        return {"accepted": False, "result_code": code}

    def observe(self) -> dict:
        return self.env.raw()


class RoyalePoolEnv:
    def __init__(self, *, decision_ticks: int = 10, elixir_slack: int = 40, tail_cap: int = 7200,
                 warmup_ticks: int = 90, seed: int = 0, subs: Optional[dict[str, str]] = None,
                 forms_mode: str = "base", hero_abilities: bool = False, feature_version: int = 1,
                 ability_policy: str = "generic", **_ignored):
        self.feature_version = int(feature_version)
        if type(hero_abilities) is not bool:
            raise ValueError("hero_abilities must be a bool")
        self.hero_abilities = hero_abilities
        if ability_policy not in ABILITY_POLICIES:
            raise ValueError(f"ability_policy {ability_policy!r} not in {ABILITY_POLICIES}")
        if ability_policy == "v2" and not hero_abilities:
            raise ValueError("ability_policy v2 needs hero_abilities=True")
        self.ability_policy = ability_policy
        if forms_mode not in FORMS_MODES:
            raise ValueError(f"forms_mode {forms_mode!r} not in {FORMS_MODES}")
        self.forms_mode = forms_mode
        self.core = RustEngine()
        self.ids = {c.name: c.card_id for c in self.core.cards()}
        self.names = {v: k for k, v in self.ids.items()}
        self.decision_ticks, self.elixir_slack, self.tail_cap = int(decision_ticks), int(elixir_slack), int(tail_cap)
        self.warmup_ticks, self.seed, self.subs = int(warmup_ticks), int(seed), dict(subs or {})
        self.eng = _Core(self)
        self._code_names = RESULT_CODE_NAMES
        self.elixir_regen_schedule = REGEN_SCHEDULE          # e1_eval's opp-elixir counter reads it (T12b)

    # ---------------------------------------------------------------- decks
    def card_id(self, name: str) -> int:
        n = self.subs.get(name, name)
        if n not in self.ids:
            raise UnsupportedDeck(name)
        return self.ids[n]

    def _setup(self, deal: dict, order: dict, wanted: Optional[dict]) -> MatchSetup:
        """The MatchSetup for deal ids ``deal[s]`` (= ``deck_ids[s]`` permuted by ``order[s]``). ``wanted`` (deck mode):
        {side: decked form per ``deck_ids`` entry}; refused forms fall back to 0 (``form_fallbacks``). Base mode:
        today's setup exactly."""
        if self.forms_mode == "base":
            return MatchSetup(decks=[deal[0], deal[1]], shuffle=ShuffleMode.NONE)
        self.form_fallbacks, self.loaded_forms = [], {}
        for s in (0, 1):
            self.loaded_forms[s] = []
            for cid, f in zip(self.deck_ids[s], wanted[s]):
                if f and not self._form_loads(s, cid, f):
                    self.form_fallbacks.append((s, self.names[cid], f))
                    f = 0
                self.loaded_forms[s].append(f)
        return MatchSetup(decks=[deal[0], deal[1]], shuffle=ShuffleMode.NONE,
                          forms=[[self.loaded_forms[s][i] for i in order[s]] for s in (0, 1)])

    def _form_loads(self, side: int, cid: int, form: int) -> bool:
        """Probe (once per process) whether RoyaleSim loads ``cid`` in ``form``: a reset with only that entry marked.
        The real reset follows, so the probe leaves no state behind."""
        if (cid, form) not in _FORM_LOADS:
            d = [list(self.deck_ids[0]), list(self.deck_ids[1])]
            f = [[0] * len(d[0]), [0] * len(d[1])]
            f[side][d[side].index(cid)] = form
            try:
                self.core.reset(self.seed, MatchSetup(decks=d, shuffle=ShuffleMode.NONE, forms=f))
                _FORM_LOADS[cid, form] = True
            except ValueError:
                _FORM_LOADS[cid, form] = False
        return _FORM_LOADS[cid, form]

    # ---------------------------------------------------------------- episode
    def reset(self, entry: dict, *, index=None) -> dict:
        self.entry = entry
        self.side, self.opp = int(ours(entry, "side")), int(entry["ghost_side"])
        self._mirror = self.side == 1
        self.final_decks = {self.side: list(ours(entry, "deck")), self.opp: list(entry["ghost_deck"])}
        self.deck_ids = {s: [self.card_id(it["name"]) for it in self.final_decks[s]] for s in (0, 1)}
        deal, orders = {}, {}
        for s, cmds in ((self.side, ours(entry, "commands")), (self.opp, entry["ghost_commands"])):
            slugs = [it["slug"] for it in self.final_decks[s]]
            order = deal_order(slugs, [c["card"] for c in cmds if not c.get("ability") and c.get("corpus_accepted", True)])
            if order is None:
                raise UnsupportedDeck(f"{entry['tag']}: no deal fits side {s}'s recorded plays")
            deal[s], orders[s] = [self.deck_ids[s][i] for i in order], order
        wanted = None if self.forms_mode == "base" else             {s: [FORM_OF[str(it.get("form", "base"))] for it in self.final_decks[s]] for s in (0, 1)}
        self.core.reset(self.seed, self._setup(deal, orders, wanted))
        self.public_plays = []
        idx = {it["slug"]: i for i, it in enumerate(self.final_decks[self.opp])}
        self._ghosts = sorted(({"tick": int(c["tick"]), "sched": int(c["tick"]), "deck_index": idx[c["card"]],
                                "x": int(c["x"]), "y": int(c["y"]), "card": c["card"]}
                               for c in entry["ghost_commands"] if not c.get("ability")), key=lambda g: g["tick"])
        self._gi, self._pending = 0, []
        self.ghost_ok = self.ghost_rejected = 0
        self.ghost_reject_reasons, self.ghost_events, self.ghost_cards_delivered = {}, [], Counter()
        self.terminated, self.episode, self.eng.last_episode = False, {}, None
        self._reset_abilities()
        self.tick = int(self.core.state().tick)
        self._advance_to(self.warmup_ticks)
        return self.raw()

    def _fire_ghosts_at(self, tick: int) -> None:
        while self._gi < len(self._ghosts) and self._ghosts[self._gi]["tick"] <= tick:
            self._pending.append(self._ghosts[self._gi])
            self._gi += 1
        still = []
        for g in self._pending:
            if g["sched"] > tick:
                still.append(g)
                continue
            r = self.eng.act(side=self.opp, deck_index=g["deck_index"], x=g["x"], y=g["y"])
            if r["accepted"]:
                self.ghost_ok += 1
                self.ghost_events.append((g["tick"], 1, "accepted"))
                self.ghost_cards_delivered[g["card"]] += 1
                continue
            code = r["result_code"]
            if code in (NOT_ENOUGH_ELIXIR, NOT_IN_HAND) and (tick - g["tick"]) < self.elixir_slack:
                g["sched"] = tick + 1
                still.append(g)
                continue
            name = RESULT_CODE_NAMES.get(code, f"code_{code}")
            self.ghost_rejected += 1
            self.ghost_reject_reasons[name] = self.ghost_reject_reasons.get(name, 0) + 1
            self.ghost_events.append((g["tick"], 0, name))
        self._pending = still

    def _next_ghost_tick(self) -> Optional[int]:
        c = [g["sched"] for g in self._pending] + ([self._ghosts[self._gi]["tick"]] if self._gi < len(self._ghosts) else [])
        return min(c) if c else None

    def _advance_to(self, target: int) -> None:
        """Step to ``target``, stopping on every ghost tick on the way (engine_env.py semantics)."""
        while self.tick < target and not self.terminated:
            telemetry = getattr(self, 'behaviour_telemetry', None)
            if telemetry is not None:
                telemetry.observe(self)
            nxt = self._next_ghost_tick()
            stop = target if (nxt is None or nxt > target) else max(min(nxt, target), self.tick + 1)
            if telemetry is not None:
                stop = min(stop, self.tick + 1)
            if self.hero_abilities and self._ability_pending:
                stop = min(stop, self._ability_pending[0][0])
            self.core.step([], stop - self.tick)
            st = self.core.state()
            self.tick = int(st.tick)
            if telemetry is not None:
                telemetry.observe(self)
            if st.game_over:
                self.terminated = True
                c = [p.crowns for p in st.players]
                w = {Winner.BLUE: 0, Winner.RED: 1}.get(Winner(st.winner), -1)
                self.episode = self.eng.last_episode = {"winner": w, "crowns": c, "termination_reason": "game_over"}
                return
            self._fire_ghosts_at(self.tick)
            if self.hero_abilities:
                self._fire_abilities()

    def ghost_undelivered(self) -> int:
        return len(self._ghosts) - self._gi + len(self._pending)

    def _reset_abilities(self) -> None:
        if self.feature_version >= 4:
            self.own_ability_events = []
        if getattr(self, 'behaviour_telemetry', None) is not None:
            from .behaviour_telemetry import BehaviourTelemetry
            self.behaviour_telemetry = BehaviourTelemetry()
        self.ability_presses = {0: Counter(), 1: Counter()}
        self._ability_pending = []
        self._hero_ids = {s: [cid for cid, form in zip(self.deck_ids[s],
                           getattr(self, "loaded_forms", {}).get(s, [])) if form == 2]
                          if self.forms_mode == "deck" else [] for s in (0, 1)}
        self._champ_ids = {0: set(), 1: set()}
        if self.ability_policy == "v2":
            # v2 presses champions too (the generic rule never did): the buttons the engine gives beyond the heroes'.
            self.ability_fallback_generic, self.ability_deployments = Counter(), {0: Counter(), 1: Counter()}
            self._ability_uid, self._last_play, self._ability_check = {}, {}, {0: [None, None], 1: [None, None]}
            for s in (0, 1):
                rows = self.core.state().players[s].abilities
                self._champ_ids[s] = {int(r[3]) for r in rows if r[3] != EMPTY_CARD} - set(self._hero_ids[s])
                self._hero_ids[s] = list(self._hero_ids[s]) + sorted(self._champ_ids[s])
        if not self.hero_abilities or not any(self._hero_ids.values()):
            return
        if not hasattr(self, "_hero_costs"):
            import royalesim
            from royalegym.rust_engine import embedded_card_table, engine_cards_json_path
            column = list(royalesim.CATALOGUE_FIELDS).index("hero")
            self._hero_costs = {cid: row[column] for cid, row in
                               enumerate(json.loads(self.core._battle.catalogue_json()))}
            # BattleState has no attack range. Read the engine-selected table, including
            # hero-local summoned units (e.g. Hero Barbarian Barrel), not base-card stats.
            embedded = embedded_card_table()
            if embedded is not None:
                data = json.loads(embedded)
            else:
                path, _ = engine_cards_json_path()
                data = json.loads(path.read_text(encoding="utf-8"))
            rows = list(data["hero_forms"])
            for form in data["hero_forms"]:
                rows.extend(form.get("tables", {}).get("units", {}).values())
            self._hero_ranges = {r["name"]: int(r.get("range_milli") or 0) * SCALE for r in rows}
            # debug_units exposes troops only. The Goblins button belongs to its
            # flag building, whose table range is zero, not the Goblins' melee range.
            self._hero_buildings = {self.ids[f["form_of"]]: f["ability"]["effect"]["unit"]
                                    for f in data["hero_forms"]
                                    if f["ability"]["effect"]["kind"] == "flag_spawns"}

    def ability_commands(self, side: int) -> list[tuple[int, int, int]]:
        """Ready (button, base card id, newest hero uid), with centre distance <= range + 1.5 tiles.
        Pure engine readiness query; no RNG, observation edits, or policy/card bookkeeping.
        ``ability_policy`` "v2": the press DECISION is the per-ability calibrated model's (``_v2_gate``) instead of the
        range rule -- a seeded draw per (match, side, hero uid, tick), so the same call twice in one tick answers the same.
        """
        if not self.hero_abilities or not self._hero_ids[side]:
            return []
        if self.ability_policy == "v2":
            last = self._ability_check[side]
            if last[1] != self.tick:
                last[:] = [last[1], self.tick]
            self._v2_dt = (self.decision_ticks if last[0] is None else self.tick - last[0]) / 20
            return self._scan(side, self._v2_gate)
        return self._scan(side, self._near)

    def _scan(self, side: int, gate) -> list[tuple[int, int, int]]:
        """The readiness checks (button free, hero card, cost, engine check_deploy, living hero entity) then
        ``gate(button, cid, hero, st)`` -> the final press decision."""
        st = self.core.state()
        buttons = st.players[side].abilities
        pending = {(s, b) for _, s, b, _, _ in self._ability_pending}
        ready = []
        self._units = None
        for button, row in enumerate(buttons):
            cid = row[3]
            if cid not in self._hero_ids[side] or (side, button) in pending:
                continue
            cost = row[2] if cid in self._champ_ids[side] else self._hero_costs[cid]
            if cost is None or st.players[side].elixir_milli < cost * 1000:
                continue
            if self.core.check_deploy(DeployCommand(side, HAND_SIZE + button, 0, 0)) != DeployStatus.OK:
                continue
            # a champion is its biggest living body (Goblinstein is doctor + monster); a hero its newest
            hero = max((e for e in st.entities if e.team == side and e.card_id == cid and e.hp > 0
                        and e.status_flags >= 0 and e.status_flags & STATUS_HERO),
                       key=(lambda e: (e.max_hp, e.uid)) if cid in self._champ_ids[side] else (lambda e: e.uid),
                       default=None)
            if hero is None:
                continue
            if gate(button, cid, hero, st):
                ready.append((button, cid, hero.uid))
        return ready

    def _near(self, button, cid, hero, st) -> bool:
        """The generic rule: any enemy within the hero's attack range + 1.5 tiles."""
        side = hero.team
        if self._units is None:
            self._units = {r[0]: r[1] for r in self.core._battle.debug_units()}
        name = self._units.get(hero.uid, self._hero_buildings.get(cid, self.names[cid] + "_hero"))
        reach = self._hero_ranges[name] + 1500 * SCALE
        return any(e.team == 1 - side and e.hp > 0
                   and (e.x - hero.x) ** 2 + (e.y - hero.y) ** 2 <= reach ** 2 for e in st.entities)

    def _v2_gate(self, button, cid, hero, st) -> bool:
        key = V2_KEYS.get(self.names[cid])
        if key is None:                     # no v2 model (hero Ice Wizard, ...): the old rule, counted at the press
            return self._near(button, cid, hero, st)
        side = hero.team
        info = self._ability_uid.setdefault((side, hero.uid), {"dep": self._last_play.get((side, cid), self.tick),
                                                               "presses": 0, "last": None, "card": self.names[cid]})
        n = info["presses"]       # one press per deployment, except boss-bandit's two charges (>= 3 s apart)
        if n >= (2 if key == "boss-bandit" else 1) or (n and self.tick - info["last"] < V2_REPRESS_TICKS):
            return False
        p = _v2_policy().predict(key, self._ability_features(side, hero, st, info["dep"]), "v2", n)
        q = 1 - (1 - p) ** self._v2_dt
        tag = getattr(self, "entry", {}).get("tag", "")
        return random.Random(f"ability:{self.seed}:{tag}:{side}:{hero.uid}:{self.tick}").random() < q

    def _v2_recheck(self, button, cid, hero, st) -> bool:
        """At landing the decision is made; only a fallback ability re-asks its (range) rule."""
        return V2_KEYS.get(self.names[cid]) is not None or self._near(button, cid, hero, st)

    def _ability_features(self, side: int, hero, st, dep_tick: int) -> list[float]:
        """The 14 FEATURE_NAMES of L70 phase2_build.features, from the live engine state (tiles = units / 18,000;
        HP in the engine's own unit, level 11 = the corpus level; units = enemy troops, structures = enemy buildings +
        alive crown towers; the hero Goblins flag is untargetable and skipped)."""
        goblins = self.ids.get("Goblins")
        units, structures, towers = [], [], []
        for u in st.entities:
            if u.team == side or u.hp <= 0:
                continue
            d = ((u.x - hero.x) ** 2 + (u.y - hero.y) ** 2) ** .5 / (SCALE * 1000)
            if u.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER):
                towers.append(d)
            elif u.card_id == EMPTY_CARD:
                continue
            elif u.kind == EntityKind.BUILDING:
                if not (u.card_id == goblins and u.status_flags & STATUS_HERO):
                    structures.append(d)
            else:
                units.append((d, u.hp))
        sd = structures + towers
        tick, me, foe = self.tick, st.players[side], st.players[1 - side]
        return [(tick - dep_tick) / 20, min(1., max(0., hero.hp / max(1, hero.max_hp))),
                min((d for d, _ in units), default=40.), min(sd, default=40.),
                sum(d <= 3 for d, _ in units), sum(h for d, h in units if d <= 3),
                sum(d <= 5 for d, _ in units), sum(h for d, h in units if d <= 5),
                float(hero.y > 16 * 18000 if side == 0 else hero.y < 16 * 18000),
                min(towers, default=40.), me.elixir_milli / 1000, min(tick // 1200, 3),
                1 if tick < 2400 else (2 if tick < 4800 else 3), me.crowns - foe.crowns]

    def queue_abilities(self, side: int, commands: list, delay: int) -> None:
        for button, cid, uid in commands:
            if not any(s == side and b == button for _, s, b, _, _ in self._ability_pending):
                self._ability_pending.append((self.tick + delay, side, button, cid, uid))
        self._ability_pending.sort()
        self._fire_abilities()

    def _fire_abilities(self) -> None:
        while self._ability_pending and self._ability_pending[0][0] <= self.tick:
            _, side, button, cid, uid = self._ability_pending.pop(0)
            # A delayed card can land after the board/elixir changed. Recheck the whole
            # rule, including unit identity, before submitting a press to the same act path.
            if not self.terminated and (button, cid, uid) in (
                    self.ability_commands(side) if self.ability_policy == "generic" else self._scan(side, self._v2_recheck)):
                r = self.eng.act(side=side, ability_button=button)
                if r["accepted"]:
                    self.ability_presses[side][self.names[cid]] += 1
                    if self.ability_policy == "v2":
                        info = self._ability_uid.setdefault((side, uid), {"dep": self.tick, "presses": 0, "last": None,
                                                              "card": self.names[cid]})
                        info["presses"] += 1
                        info["last"] = self.tick
                        if V2_KEYS.get(self.names[cid]) is None:
                            self.ability_fallback_generic[self.names[cid]] += 1
                    if self.feature_version >= 4:
                        self.own_ability_events.append(dict(tick=self.tick,side=side,card=self.names[cid],accepted=True,ability=True))
                    if getattr(self, 'behaviour_telemetry', None) is not None:
                        self.behaviour_telemetry.play(self.tick, side, self.names[cid], None, None, ability=True)

    # ---------------------------------------------------------------- state
    def raw(self) -> dict:
        """RoyaleSim ``BattleState`` -> the real engine's raw ``observe()`` dict (the shape ``from_engine`` reads)."""
        st = self.core.state()
        players = []
        for p in st.players:
            deck = self.deck_ids[p.team]
            players.append({"side": p.team, "elixir_exact": p.elixir_milli / 1000.0,
                            "hand": [{"hand_index": i, "name": self.names[c]} for i, c in enumerate(p.hand)
                                     if c != EMPTY_CARD],
                            "next_deck_index": deck.index(p.next_card) if p.next_card in deck else None})
        ents, towers = [], []
        for e in st.entities:
            if e.kind in (EntityKind.KING_TOWER, EntityKind.PRINCESS_TOWER):
                towers.append({"side": e.team, "type": "king" if e.kind == EntityKind.KING_TOWER else "princess",
                               "x": e.x / SCALE, "y": e.y / SCALE, "hp": e.hp, "max_hp": e.max_hp, "destroyed": e.hp <= 0})
            elif e.card_id != EMPTY_CARD:
                ents.append({"side": e.team, "x": e.x / SCALE, "y": e.y / SCALE, "name": self.names.get(e.card_id, str(e.card_id)),
                             "hp": e.hp, "max_hp": e.max_hp, "card_id": e.card_id, "entity_id": e.uid,
                             "kind": 12 if e.deploy_ticks > 0 else int(e.kind)})
                if self.feature_version >= 3:
                    ents[-1]["status_flags"] = int(e.status_flags)
        effects = [{"side": s.team, "x": s.x / SCALE, "y": s.y / SCALE, "name": self.names.get(s.card_id, str(s.card_id))}
                   for s in st.spells]
        out = {"tick": st.tick, "players": players, "entities": ents, "effects": effects,
               "episode": {"crown_towers": towers}}
        if self.feature_version >= 4:
            # py.rs Flight.delay_ticks is PRE-flight delay, NOT time to impact.
            # Only PULSING.delay_ticks is a remaining effect lifetime. Keep all
            # unexposed timings unknown instead of turning them into false zeroes.
            from .projectile_observation import sim_objects
            out.update(sim_objects(st, self.names, SCALE))
        return out

    # the real env's readouts ep._outcome uses
    @staticmethod
    def _tower_hp(state: dict) -> dict:
        return {(int(t["side"]), t["type"], t["x"]): int(t["hp"]) for t in state["episode"]["crown_towers"]}

    def _crowns(self, hp: dict) -> tuple[int, int]:
        st = self.core.state()
        return int(st.players[self.side].crowns), int(st.players[self.opp].crowns)

    def close(self) -> None:
        pass


class RoyaleSelfPlayEnv(RoyalePoolEnv):
    """Self-play (L68 league, T12a): ANY two 8-card decks, BOTH sides policy-driven, no ghost.

    ``reset(deck0, deck1, seed)``: a deck is 8 card names (engine spelling ``IceWizard``; a ``@evolution`` / ``@hero``
    suffix runs as the base card under forms_mode "base", as its form under "deck" -- module docstring) or pool deck items with a ``name``. Each side's deal is a SEEDED
    shuffle (``self.deal[side]``, reproducible per seed) fed to RoyaleSim's ShuffleMode.NONE cycle -- the same deal
    mechanics RoyalePoolEnv uses, with the order drawn instead of reconstructed. ``act`` / ``raw`` / warm-up /
    ``tail_cap`` / game-over handling are RoyalePoolEnv's own (inherited; with no ghosts ``_advance_to`` just steps).
    ``raw()`` is the full two-sided state; each side mirrors it as today: ``from_engine(obs, side, ...)``. Its
    ``next_deck_index`` indexes the CALLER's deck order (``self.decks[side]``)."""

    def reset(self, deck0, deck1, seed: int = 0) -> dict:
        decks = {s: [str(it["name"] if isinstance(it, dict) else it).split("@")[0] for it in d]
                 for s, d in ((0, deck0), (1, deck1))}
        deck_ids = {s: [self.card_id(n) for n in decks[s]] for s in (0, 1)}
        for s in (0, 1):                                          # validate BEFORE touching any state (T12b)
            if len(deck_ids[s]) != 8 or len(set(deck_ids[s])) != 8:
                raise UnsupportedDeck(f"side {s}: need 8 distinct cards (after subs), got {decks[s]}")
        wanted = None
        if self.forms_mode == "deck":
            wanted = {}
            for s, d in ((0, deck0), (1, deck1)):
                sfx = [str(it["name"] if isinstance(it, dict) else it).partition("@")[2] for it in d]
                if any(x not in FORM_OF for x in sfx):
                    raise UnsupportedDeck(f"side {s}: unknown form suffix in {list(d)}")
                wanted[s] = [FORM_OF[x] for x in sfx]
        self.decks, self.deck_ids, self.seed = decks, deck_ids, int(seed)
        self.side, self.opp, self._mirror = 0, 1, False          # inherited _crowns reads side 0's view
        orders = {s: list(range(8)) for s in (0, 1)}
        for s in (0, 1):
            random.Random(f"deal:{self.seed}:{s}").shuffle(orders[s])   # str seed: stable across processes
        self.deal = {s: [self.decks[s][i] for i in orders[s]] for s in (0, 1)}
        self.core.reset(self.seed, self._setup({s: [self.deck_ids[s][i] for i in orders[s]] for s in (0, 1)}, orders,
                                               wanted))
        self.public_plays = []
        self._ghosts, self._gi, self._pending = [], 0, []
        self.terminated, self.episode, self.eng.last_episode = False, {}, None
        self._reset_abilities()
        self.tick = int(self.core.state().tick)
        self._advance_to(self.warmup_ticks)
        return self.raw()

    def act(self, side: int, deck_index: int, x: int, y: int) -> dict:
        """Deploy ``self.decks[side][deck_index]`` at pool/real-engine units (x, y): RoyalePoolEnv's ``eng.act``."""
        return self.eng.act(side=side, deck_index=deck_index, x=x, y=y)

    def advance_to(self, tick: int) -> dict:
        self._advance_to(min(int(tick), self.tail_cap))
        return self.raw()

    observe = RoyalePoolEnv.raw

    def costs(self, side: int) -> list[int]:
        """Elixir cost of each of ``self.decks[side]`` (deck order), from RoyaleSim's catalogue."""
        if not hasattr(self, "_elixir"):
            self._elixir = {c.card_id: c.elixir for c in self.core.cards()}
        return [int(self._elixir[c]) for c in self.deck_ids[side]]

    @property
    def done(self) -> bool:
        """e1_eval's end rule: game over, or ``tail_cap`` reached."""
        return bool(self.terminated) or self.tick >= self.tail_cap

    def outcome(self, side: int) -> tuple[str, tuple[int, int]]:
        """engine_play._outcome for ``side``: the engine winner when game over, else crowns (at ``tail_cap``)."""
        st = self.core.state()
        cr = (int(st.players[side].crowns), int(st.players[1 - side].crowns))
        w = self.episode.get("winner", -1)
        if w is None or int(w) < 0:
            return ("draw" if cr[0] == cr[1] else "win" if cr[0] > cr[1] else "loss"), cr
        return ("win" if int(w) == side else "loss"), cr


assert BLUE == 0   # the pool's side 0 is RoyaleSim's Blue (both at low y) -- checked again by the smoke test
