"""RoyaleSim (research/ext/Royale, the owner's friend's Rust engine) behind the interface ``e1_eval.run_match`` drives,
so the S1 policy, the live deploy rule and the ghost pool run on it UNCHANGED. L68.

Mirrors ``scratchpad/gauntlet/L62/engine_env.py`` + ``e1_pool.PoolV1Mixin``: ghosts fire at their recorded tick, a
not-enough-elixir refusal is retried each tick for up to ``elixir_slack`` ticks, the episode starts at
``warmup_ticks`` (90: the real engine refuses every deploy before 4.5 s; RoyaleSim's LOGIC_BATTLE_START_COOLDOWN_MS is
the same 4,500 ms). Coordinates: side 0 / Blue at low y in both, but RoyaleSim is 18,000 units per tile against the
pool's 1,000 (arena 324,000 x 576,000; kings at (162000, 54000) = tile (9, 3), measured L68) -- hence ``SCALE``.
Overtime: RoyaleSim ships 60 s (2018 locations.csv); the 2026 corpus runs to 5,979 ticks = 120 s. Build the engine
with ``match.OVERTIME_S`` = 120 (L68 local patch) or 62% of pool matches end a minute early.

What the engine cannot play is a DECK problem, not a runtime one: ``reset`` refuses an entry whose decks name a card
the catalogue lacks, unless ``subs`` maps it to one it has (e.g. {"Tornado": "Arrows"} while Tornado is unimplemented).
Evolution / hero forms run as the base card -- RoyaleSim has no forms.

Needs ``royalesim`` + ``royalegym`` importable (the Royale stack venv, or both installed into the caller's venv).
"""
from __future__ import annotations

from collections import Counter
from typing import Optional

from royalegym.protocol import (BLUE, EMPTY_CARD, DeployCommand, DeployStatus, EntityKind, MatchSetup, ShuffleMode,
                                Winner)
from royalegym.rust_engine import RustEngine

from pipeline.e1_pool import ours

SCALE = 18                      # RoyaleSim units per pool/real-engine unit (18,000 vs 1,000 per tile)
NOT_ENOUGH_ELIXIR = 13         # the real engine's code, so e1_eval / the ghost retry read it unchanged
NOT_IN_HAND = 1003              # deck_index names a card that is not in the hand right now
REFUSED_BASE = 2000             # 2000 + DeployStatus for every other refusal
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

    def act(self, *, side: int, deck_index: int, x: int, y: int) -> dict:
        env = self.env
        cid = env.deck_ids[side][deck_index]
        hand = env.core.state().players[side].hand
        if cid not in hand:
            return {"accepted": False, "result_code": NOT_IN_HAND}
        (r,) = env.core.step([DeployCommand(side, hand.index(cid), int(x) * SCALE, int(y) * SCALE)], 0)
        if r.status == DeployStatus.OK:
            return {"accepted": True, "result_code": 0}
        code = NOT_ENOUGH_ELIXIR if r.status == DeployStatus.NOT_ENOUGH_ELIXIR else REFUSED_BASE + int(r.status)
        return {"accepted": False, "result_code": code}

    def observe(self) -> dict:
        return self.env.raw()


class RoyalePoolEnv:
    def __init__(self, *, decision_ticks: int = 10, elixir_slack: int = 40, tail_cap: int = 7200,
                 warmup_ticks: int = 90, seed: int = 0, subs: Optional[dict[str, str]] = None, **_ignored):
        self.core = RustEngine()
        self.ids = {c.name: c.card_id for c in self.core.cards()}
        self.names = {v: k for k, v in self.ids.items()}
        self.decision_ticks, self.elixir_slack, self.tail_cap = int(decision_ticks), int(elixir_slack), int(tail_cap)
        self.warmup_ticks, self.seed, self.subs = int(warmup_ticks), int(seed), dict(subs or {})
        self.eng = _Core(self)
        self._code_names = RESULT_CODE_NAMES

    # ---------------------------------------------------------------- decks
    def card_id(self, name: str) -> int:
        n = self.subs.get(name, name)
        if n not in self.ids:
            raise UnsupportedDeck(name)
        return self.ids[n]

    # ---------------------------------------------------------------- episode
    def reset(self, entry: dict, *, index=None) -> dict:
        self.entry = entry
        self.side, self.opp = int(ours(entry, "side")), int(entry["ghost_side"])
        self._mirror = self.side == 1
        self.final_decks = {self.side: list(ours(entry, "deck")), self.opp: list(entry["ghost_deck"])}
        self.deck_ids = {s: [self.card_id(it["name"]) for it in self.final_decks[s]] for s in (0, 1)}
        deal = {}
        for s, cmds in ((self.side, ours(entry, "commands")), (self.opp, entry["ghost_commands"])):
            slugs = [it["slug"] for it in self.final_decks[s]]
            order = deal_order(slugs, [c["card"] for c in cmds if not c.get("ability") and c.get("corpus_accepted", True)])
            if order is None:
                raise UnsupportedDeck(f"{entry['tag']}: no deal fits side {s}'s recorded plays")
            deal[s] = [self.deck_ids[s][i] for i in order]
        self.core.reset(self.seed, MatchSetup(decks=[deal[0], deal[1]], shuffle=ShuffleMode.NONE))
        idx = {it["slug"]: i for i, it in enumerate(self.final_decks[self.opp])}
        self._ghosts = sorted(({"tick": int(c["tick"]), "sched": int(c["tick"]), "deck_index": idx[c["card"]],
                                "x": int(c["x"]), "y": int(c["y"]), "card": c["card"]}
                               for c in entry["ghost_commands"] if not c.get("ability")), key=lambda g: g["tick"])
        self._gi, self._pending = 0, []
        self.ghost_ok = self.ghost_rejected = 0
        self.ghost_reject_reasons, self.ghost_events, self.ghost_cards_delivered = {}, [], Counter()
        self.terminated, self.episode, self.eng.last_episode = False, {}, None
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
            nxt = self._next_ghost_tick()
            stop = target if (nxt is None or nxt > target) else max(min(nxt, target), self.tick + 1)
            self.core.step([], stop - self.tick)
            st = self.core.state()
            self.tick = int(st.tick)
            if st.game_over:
                self.terminated = True
                c = [p.crowns for p in st.players]
                w = {Winner.BLUE: 0, Winner.RED: 1}.get(Winner(st.winner), -1)
                self.episode = self.eng.last_episode = {"winner": w, "crowns": c, "termination_reason": "game_over"}
                return
            self._fire_ghosts_at(self.tick)

    def ghost_undelivered(self) -> int:
        return len(self._ghosts) - self._gi + len(self._pending)

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
        effects = [{"side": s.team, "x": s.x / SCALE, "y": s.y / SCALE, "name": self.names.get(s.card_id, str(s.card_id))}
                   for s in st.spells]
        return {"tick": st.tick, "players": players, "entities": ents, "effects": effects,
                "episode": {"crown_towers": towers}}

    # the real env's readouts ep._outcome uses
    @staticmethod
    def _tower_hp(state: dict) -> dict:
        return {(int(t["side"]), t["type"], t["x"]): int(t["hp"]) for t in state["episode"]["crown_towers"]}

    def _crowns(self, hp: dict) -> tuple[int, int]:
        st = self.core.state()
        return int(st.players[self.side].crowns), int(st.players[self.opp].crowns)

    def close(self) -> None:
        pass


assert BLUE == 0   # the pool's side 0 is RoyaleSim's Blue (both at low y) -- checked again by the smoke test
