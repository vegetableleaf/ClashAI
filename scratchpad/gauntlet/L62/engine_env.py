"""L62: EngineMatchEnv -- a PPO training environment whose WORLD is the real Clash Royale engine
(cr-native-sandbox), exposing the SAME interface the trainer already consumes from
`clashrl.sim.env.SimMatchEnv`:

    obs = env.reset()                       -> uint8 ndarray of env.obs_shape
    obs, reward, done, info = env.step((play, card_id, cell))
    env.hand_vec, env.next_vec, env.elixir_vec, env.threat_vec, env.n_cards, env.n_cells, env.threat_dim

WHAT IS REAL AND WHAT IS NOT
  * real: every unit, tower, projectile, spell, elixir bar, deploy rule, hitbox and clock is the engine's.
  * ghost opponent: the human opponent of one mined battle, replayed from their recorded 20 Hz command
    timeline (icebow/data/ghost_pool/pool_env_v0.jsonl). NON-REACTIVE by design -- they play what they played,
    whether or not it still makes sense. Every ghost play the engine REFUSES is counted; that count is
    the v0 diagnostic for how fast a ghost stops making sense once our policy diverges from the icebow
    player it replaces.
  * observation: L61's adapter, unchanged -- engine frame -> FakeEngine -> a real SimMatchEnv with
    `env.eng` swapped -> `env._update_vectors()`. The policy sees exactly the tensor it was trained on.
  * reward: engine state ONLY (tower-HP deltas, crowns, terminal outcome). UNSHAPED -- none of the sim's
    drill / gate / geometry / trade / bank terms are ported. See `reward_spec()`.

Requires BOTH import roots (they coexist in the icebow venv):
    icebow/src (clashrl)  +  research/ext/cr-native-sandbox (native_core)
"""
from __future__ import annotations

import collections
import importlib.util
import json
import random
import sys
import time
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
ICEBOW = ROOT / "icebow"
SANDBOX = ROOT / "research" / "ext" / "cr-native-sandbox"
for _p in (str(ICEBOW / "src"), str(SANDBOX), str(ROOT / "research" / "sandbox_tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from native_core.env import NativeRoyaleEnv                      # noqa: E402
from native_core.decks import build_replay                       # noqa: E402
import replay_drive as RD                                        # noqa: E402


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# THE ADAPTER, reused verbatim: init_worker() builds the SimMatchEnv, frame_to_engine() the FakeEngine,
# nearest_cell() the forward cell mapping.  Do not reimplement any of it here.
V2 = _load_module(ROOT / "scratchpad" / "gauntlet" / "L61" / "build_bc_v2.py", "l61_build_bc_v2")

TICK_S = 0.05
# OWNERSHIP: `pool.jsonl` belongs to the ghost-pool agent and uses a different schema. This env reads
# ONLY `pool_env_v0.jsonl`, written by scratchpad/gauntlet/L62/build_ghost_pool.py.
POOL_DEFAULT = ICEBOW / "data" / "ghost_pool" / "pool_env_v0.jsonl"
TEMPLATE = SANDBOX / "examples" / "full-card-bootstrap.json"
DEAL_CACHE = Path(__file__).resolve().parent / "deal_cache.json"
RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 13: "not_enough_elixir", 1014: "ability_exhausted",
                     1050: "not_enough_elixir"}   # 13 = this build's elixir refuse (measured L64d); 1050 = the documented one
SEED_DEFAULT = 424242
LEVEL_DEFAULT = 11


def load_pool(path=POOL_DEFAULT, *, require_commands: int = 1):
    """Ghost pool as written by scratchpad/gauntlet/L62/build_ghost_pool.py (schema in its docstring)."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if sum(1 for c in r["ghost_commands"] if not c.get("ability")) < require_commands:
            continue
        rows.append(r)
    return rows


def key_base(slug: str) -> str:
    return slug.replace("-ev1", "").replace("-hero", "").replace("-", "_")


class EngineMatchEnv:
    """One engine slot = one env. `port` is a running native worker service (38031/38032 = direct)."""

    # ---------------------------------------------------------------- construction
    def __init__(self, *, port: int = 38031, host: str = "127.0.0.1", pool=None,
                 decision_ticks: int = 10, elixir_slack: int = 40, tail_cap: int = 7200,
                 seed: int = 0, replay_seed: int = SEED_DEFAULT, level: int = LEVEL_DEFAULT,
                 timeout: float = 120.0, deal_cache: bool = True, warmup_ticks: int = 90,
                 w_hp: float = 1.0, w_crown: float = 1.0, w_outcome: float = 3.0):
        if not V2._W:
            V2.init_worker()
        self.sim = V2._W["env"]                       # a real SimMatchEnv; only its OBS pipeline is used
        self.db = V2._W["db"]
        self.spec_of = V2._W["spec_of"]
        self.slot_of_base = V2._W["slot_of_base"]
        self.actions = self.sim.actions
        self.gw = self.actions.gw
        # --- the SimMatchEnv-compatible surface --------------------------------------------------
        self.n_cards = int(self.sim.n_cards)
        self.n_cells = int(self.sim.n_cells)
        self.threat_dim = int(self.sim.threat_dim)
        self.obs_shape = self.sim.obs_shape
        self.deck_keys = list(self.sim.deck_keys)
        self.anywhere_ids = set(self.sim.anywhere_ids)
        self.agent_dt = decision_ticks * TICK_S

        self.eng = NativeRoyaleEnv(host=host, port=port, timeout=timeout)
        self.port = port
        self.pool = pool if pool is not None else load_pool()
        self.decision_ticks = int(decision_ticks)
        self.elixir_slack = int(elixir_slack)
        self.tail_cap = int(tail_cap)
        self.replay_seed = int(replay_seed)
        self.level = int(level)
        # MEASURED on this box: the engine refuses EVERY deploy with result_code 22 ("native_rejected",
        # placement_valid true) until tick 90 = 4.5 s -- the pre-battle countdown. replay_drive never
        # saw it because the earliest human play in the whole crawl is tick 102. Starting the episode
        # at tick 90 costs the policy nothing and saves ~9 forced-illegal decisions per match.
        self.warmup_ticks = int(warmup_ticks)
        self.w_hp, self.w_crown, self.w_outcome = float(w_hp), float(w_crown), float(w_outcome)
        self.rng = random.Random(seed)
        self.template = json.loads(TEMPLATE.read_text(encoding="utf-8-sig"))
        self._stats = {"names": collections.Counter(), "unmapped": collections.Counter()}
        self._use_cache = bool(deal_cache)
        self._deal_cache = {}
        if self._use_cache and DEAL_CACHE.exists():
            try:
                self._deal_cache = json.loads(DEAL_CACHE.read_text(encoding="utf-8"))
            except Exception:
                self._deal_cache = {}
        self.entry = None
        self.tick = 0
        self.resets_used = 0

    # ---------------------------------------------------------------- reward contract
    @staticmethod
    def reward_spec():
        return ("r_t = w_hp * (their_tower_hp_lost - our_tower_hp_lost) / princess_max_hp"
                " + w_crown * (d_our_crowns - d_their_crowns)"
                " + [terminal] w_outcome * (+1 win / -1 loss / 0 draw).  UNSHAPED.")

    # ---------------------------------------------------------------- coordinate mapping
    # FORWARD (engine -> policy cell) is exactly build_bc_v2.frame_to_engine + nearest_cell:
    #   icebow_side == 1  =>  mirror:  X,Y = 18000-x, 32000-y ;  nx = X/18000,  ny = 1 - Y/32000
    # INVERSE (policy cell -> engine x,y) is the algebraic inverse of that same pair.
    def cell_to_engine(self, cell: int, mirror: bool | None = None):
        mirror = self._mirror if mirror is None else mirror
        nx, ny = self.actions.cell_center(int(cell) % self.gw, int(cell) // self.gw)
        X = nx * 18000.0
        Y = (1.0 - ny) * 32000.0
        if mirror:
            X, Y = 18000.0 - X, 32000.0 - Y
        return int(round(X)), int(round(Y))

    def engine_to_cell(self, x: int, y: int, mirror: bool | None = None):
        mirror = self._mirror if mirror is None else mirror
        X, Y = (18000 - int(x), 32000 - int(y)) if mirror else (int(x), int(y))
        nx, ny = X / 18000.0, 1.0 - Y / 32000.0
        cell, dist = V2.nearest_cell(nx, ny)
        return cell, dist

    # ---------------------------------------------------------------- engine frame -> adapter frame
    @staticmethod
    def _frame_of(state: dict) -> dict:
        """The exact dict shape build_bc_v2.frame_to_engine reads (== replay_drive's record_full snapshot)."""
        players = {int(p["side"]): p for p in state["players"]}
        return {
            "tick": int(state["tick"]),
            "elixir": [players[0].get("elixir_exact", players[0].get("elixir")),
                       players[1].get("elixir_exact", players[1].get("elixir"))],
            "entities": [[int(e["side"]), int(e["x"]), int(e["y"]), e.get("name", str(e.get("card_id"))),
                          int(e["hp"]), int(e["max_hp"]), int(e.get("kind", -1))]
                         for e in state.get("entities", [])],
            "towers": [[int(t["side"]), t.get("type"), t.get("lane"), int(t["x"]), int(t["y"]), int(t["hp"]),
                        int(t["max_hp"])] for t in state["episode"].get("crown_towers", [])],
        }

    @staticmethod
    def _tower_hp(state: dict):
        """{(side, type, lane): hp}; a tower ABSENT from the engine's list is destroyed -> 0."""
        return {(int(t["side"]), t.get("type"), t.get("lane")): int(t["hp"])
                for t in state["episode"].get("crown_towers", [])}

    def _hp_sums(self, hp: dict):
        ours = sum(hp.get(k, 0) for k in self._tower_keys if k[0] == self.side)
        theirs = sum(hp.get(k, 0) for k in self._tower_keys if k[0] == self.opp)
        return float(ours), float(theirs)

    def _crowns(self, hp: dict):
        """(our crowns, their crowns) = enemy / own crown towers at 0 hp (or gone from the list)."""
        ours = sum(1 for k in self._tower_keys if k[0] == self.opp and hp.get(k, 0) <= 0)
        theirs = sum(1 for k in self._tower_keys if k[0] == self.side and hp.get(k, 0) <= 0)
        return ours, theirs

    # ---------------------------------------------------------------- deck / deal resolution
    def _side_plays(self, entry, side):
        cmds = entry["icebow_commands"] if side == entry["icebow_side"] else entry["ghost_commands"]
        return [c for c in cmds if not c.get("ability")]

    def _resolve_decks(self, entry):
        """Return {side: [deck item...]} in the FINAL order the engine is given, so that deck_index i
        carries the card the real player held at position i of their inferred cycle.

        Exactly replay_drive.drive()'s procedure: probe the engine's dealt positions for this deck at
        this seed, then sp_order_for() the inferred (hand, queue) onto those positions.  The result is
        cached per tag on disk (deal_cache.json) so a repeat episode of the same tag costs one reset
        instead of two.
        """
        decks = {int(entry["icebow_side"]): list(entry["icebow_deck"]),
                 int(entry["ghost_side"]): list(entry["ghost_deck"])}
        cached = self._deal_cache.get(entry["tag"]) if self._use_cache else None
        if cached:
            by_id = {s: {int(it["card_id"]): it for it in decks[s]} for s in (0, 1)}
            try:
                return {s: [by_id[s][int(cid)] for cid in cached[str(s)]] for s in (0, 1)}, True
            except KeyError:
                pass
        deals = {}
        for s in (0, 1):
            ids = [int(it["card_id"]) for it in decks[s]]
            seq = [int(c["card_id"]) if "card_id" in c else
                   next(int(it["card_id"]) for it in decks[s] if it["slug"] == c["card"])
                   for c in self._side_plays(entry, s)]
            found = RD.infer_deals(seq, ids)
            if not found:
                raise RuntimeError(f"{entry['tag']}: side {s} has no consistent (hand, queue)")
            deals[s] = found[0]
        state = self.eng.reset(build_replay(self.template,
                                            self._deck_spec(decks[0]), self._deck_spec(decks[1]),
                                            seed=self.replay_seed), warmup_steps=0)
        self.resets_used += 1
        final = {}
        for s in (0, 1):
            p = next(q for q in state["players"] if int(q["side"]) == s)
            final[s] = RD.sp_order_for(decks[s], list(p["hand_deck_indices"]), list(p["cycle_deck_indices"]),
                                       deals[s])
        if self._use_cache:
            self._deal_cache[entry["tag"]] = {str(s): [int(it["card_id"]) for it in final[s]] for s in (0, 1)}
        return final, False

    def _deck_spec(self, order):
        return [{"card_id": int(it["card_id"]), "form": it["form"], "level": self.level} for it in order]

    def save_deal_cache(self):
        if self._use_cache:
            DEAL_CACHE.write_text(json.dumps(self._deal_cache), encoding="utf-8")

    # ---------------------------------------------------------------- sim-side bookkeeping
    def _sync_cycle(self, state: dict):
        """env.cycle straight from the ENGINE's own hand/queue (hand first) -- not from a cycle model."""
        me = next(p for p in state["players"] if int(p["side"]) == self.side)
        order = list(me["hand_deck_indices"]) + list(me["cycle_deck_indices"])
        try:
            cyc = [self.slot_of_base[self._base_of_index[i]] for i in order]
        except (KeyError, IndexError):
            return False
        if len(set(cyc)) == self.sim.n_slots:
            self.sim.cycle = cyc
            return True
        return False

    def _render(self, state: dict):
        frame = self._frame_of(state)
        eng, n_unmapped, _n_deploying = V2.frame_to_engine(frame, self.side, self.spec_of, self._stats)
        self.sim.eng = eng
        self.sim.agent_dt = self.agent_dt if self._last_upd is None else max(0.05, eng.t - self._last_upd)
        self.sim._update_vectors()
        self._last_upd = eng.t
        self._n_unmapped += n_unmapped
        self.hand_vec = self.sim.hand_vec
        self.next_vec = self.sim.next_vec
        self.elixir_vec = self.sim.elixir_vec
        self.threat_vec = self.sim.threat_vec
        self._last_obs = self.sim._last_obs
        return self._last_obs

    # ---------------------------------------------------------------- episode lifecycle
    def reset(self, entry=None, *, index: int | None = None) -> np.ndarray:
        if entry is None:
            entry = self.pool[index % len(self.pool)] if index is not None else self.rng.choice(self.pool)
        self.entry = entry
        self.side = int(entry["icebow_side"])
        self.opp = int(entry["ghost_side"])
        self._mirror = (self.side == 1)

        t_deal = time.perf_counter()
        final, cache_hit = self._resolve_decks(entry)
        self.deal_seconds = time.perf_counter() - t_deal
        self.deal_cache_hit = cache_hit
        self._base_of_index = [key_base(it["slug"]) for it in final[self.side]]
        self._index_of_base = {b: i for i, b in enumerate(self._base_of_index)}
        idx_ghost = {it["slug"]: i for i, it in enumerate(final[self.opp])}

        replay = build_replay(self.template, self._deck_spec(final[0]), self._deck_spec(final[1]),
                              seed=self.replay_seed)
        state = self.eng.reset(replay, warmup_steps=0)
        self.resets_used += 1
        self.tick = int(state["tick"])
        self._tower_keys = sorted(self._tower_hp(state))
        if len(self._tower_keys) != 6:
            raise RuntimeError(f"expected 6 crown towers at reset, got {self._tower_keys}")
        self._hp_prev = self._hp_sums(self._tower_hp(state))
        self._crowns_prev = (0, 0)
        self._princess_max = float(min(t["max_hp"] for t in state["episode"]["crown_towers"]
                                       if t.get("type") != "king"))
        self.opening_hash = state.get("state_hash")

        self._ghosts = [{"tick": int(c["tick"]), "sched": int(c["tick"]), "deck_index": idx_ghost[c["card"]],
                         "x": int(c["x"]), "y": int(c["y"]), "card": c["card"]}
                        for c in self._side_plays(entry, self.opp)]
        self._ghosts.sort(key=lambda g: g["tick"])
        self._gi = 0
        self._pending = []
        self.ghost_ok = 0
        self.ghost_rejected = 0
        self.ghost_reject_reasons = {}
        self.ghost_events = []            # (tick, accepted 0/1, reason) for every ghost play attempted
        self.our_plays = 0
        self.our_rejected = 0
        self.our_reject_reasons = {}
        self.our_reject_events = []
        self._n_unmapped = 0
        self._last_upd = None
        self.done = False
        self.steps = 0
        self.terminated = False
        self.episode = {}
        self.ep_reward = 0.0

        # deterministic sim-side RNG (the obs pipeline draws from env.rng for detection / recall)
        self.sim.rng.seed(zlib.crc32(f"{entry['tag']}:{self.replay_seed}".encode()))
        self.sim.domain_rand.enabled = False
        self.sim.domain_rand.resample()
        self.sim._canvas_stack.reset()
        self.sim._reset_vectors()
        self.sim._tid_unlit_t = None
        self.sim._threat_credits = 0
        self.sim.evo_charge = [0] * self.sim.n_slots
        if self.warmup_ticks > self.tick:
            self._advance_to(self.warmup_ticks)
            state = self.eng.observe()
            self._hp_prev = self._hp_sums(self._tower_hp(state))
        self.cycle_from_engine = self._sync_cycle(state)
        if not self.cycle_from_engine:
            self.sim.cycle = list(range(self.sim.n_slots))
        return self._render(state)

    # ---------------------------------------------------------------- ghost driving
    def _fire_ghosts_at(self, tick: int):
        """Issue every ghost play whose tick has arrived.  Same elixir-slack policy as replay_drive:
        a `not_enough_elixir` refusal is retried on the next tick, up to `elixir_slack` ticks late."""
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
                continue
            code = int(r["result_code"])
            if code in (13, 1050) and (tick - g["tick"]) < self.elixir_slack:
                g["sched"] = tick + 1
                still.append(g)
                continue
            self.ghost_rejected += 1
            name = RESULT_CODE_NAMES.get(code, f"native_{code}")
            if r.get("placement_valid") is False:
                name = f"{name}/{r.get('placement_reason')}"
            self.ghost_reject_reasons[name] = self.ghost_reject_reasons.get(name, 0) + 1
            self.ghost_events.append((g["tick"], 0, name))
        self._pending = still

    def _next_ghost_tick(self):
        cands = [g["sched"] for g in self._pending]
        if self._gi < len(self._ghosts):
            cands.append(self._ghosts[self._gi]["tick"])
        return min(cands) if cands else None

    def _advance_to(self, target: int):
        """Step to `target`, stopping EXACTLY on every ghost tick on the way.  A step RPC costs the same
        for 1 tick as for 20 (L61: 1.7 vs 2.0 ms), so exact-tick ghosts are nearly free and keep the
        ghost faithful to replay_drive's own timing."""
        while self.tick < target:
            nxt = self._next_ghost_tick()
            stop = target if (nxt is None or nxt > target) else max(min(nxt, target), self.tick + 1)
            step = self.eng.step(stop - self.tick)
            self.tick = int(step["tick_after"])
            if step["episode"].get("terminated") or int(step.get("stepped", 1)) == 0:
                self.terminated = bool(step["episode"].get("terminated"))
                self.episode = step["episode"]
                return
            self._fire_ghosts_at(self.tick)

    # ---------------------------------------------------------------- the RL step
    def step(self, action):
        play, card_id, cell = action
        info_play = None
        if play and 0 <= int(card_id) < self.n_cards:
            base = self.deck_keys[int(card_id)]
            base = base[:-4] if base.endswith("_evo") else base
            di = self._index_of_base.get(base)
            if di is not None:
                cell = self.actions.deploy_clamp(int(card_id) in self.anywhere_ids, int(cell))
                x, y = self.cell_to_engine(int(cell))
                r = self.eng.act(side=self.side, deck_index=di, x=x, y=y)
                acc = bool(r["accepted"])
                if acc:
                    self.our_plays += 1
                    self.sim._play_slot(int(card_id))     # sim-side Evolution-charge bookkeeping only
                else:
                    self.our_rejected += 1
                    nm = RESULT_CODE_NAMES.get(int(r["result_code"]), f"native_{r['result_code']}")
                    if r.get("placement_valid") is False:
                        nm = f"{nm}/{r.get('placement_reason')}"
                    self.our_reject_reasons[nm] = self.our_reject_reasons.get(nm, 0) + 1
                    self.our_reject_events.append((self.tick, nm))
                info_play = {"card_id": int(card_id), "cell": int(cell), "deck_index": di,
                             "x": x, "y": y, "accepted": acc, "result_code": int(r["result_code"])}

        self._advance_to(min(self.tick + self.decision_ticks, self.tail_cap))
        self.steps += 1

        state = self.eng.observe()
        hp = self._tower_hp(state)
        ours, theirs = self._hp_sums(hp)
        d_ours = max(0.0, self._hp_prev[0] - ours)         # HP WE lost this step
        d_theirs = max(0.0, self._hp_prev[1] - theirs)     # HP THEY lost this step
        self._hp_prev = (ours, theirs)
        cr = self._crowns(hp)
        d_cr = (cr[0] - self._crowns_prev[0], cr[1] - self._crowns_prev[1])
        self._crowns_prev = cr

        reward = self.w_hp * (d_theirs - d_ours) / self._princess_max
        reward += self.w_crown * float(d_cr[0] - d_cr[1])

        done = bool(self.terminated) or self.tick >= self.tail_cap
        outcome = None
        if done:
            last = self.eng.last_episode or self.episode or (state.get("episode") or {})
            crowns = last.get("crowns")
            if crowns is not None and len(crowns) == 2:
                cr = (int(crowns[self.side]), int(crowns[self.opp]))
            winner = last.get("winner")
            if winner is None or int(winner) < 0:
                outcome = "draw" if cr[0] == cr[1] else ("win" if cr[0] > cr[1] else "loss")
            else:
                outcome = "win" if int(winner) == self.side else "loss"
            reward += self.w_outcome * (1.0 if outcome == "win" else -1.0 if outcome == "loss" else 0.0)
            self.done = True
            self.outcome = outcome
            self.final_crowns = cr

        if self.cycle_from_engine:
            self._sync_cycle(state)
        obs = self._render(state)
        self.ep_reward += float(reward)
        info = {"tick": self.tick, "outcome": outcome, "crowns": cr,
                "terminated": bool(self.terminated), "tail_capped": (not self.terminated) and done,
                "termination_reason": (self.eng.last_episode or {}).get("termination_reason") if done else None,
                "ghost_ok": self.ghost_ok, "ghost_rejected": self.ghost_rejected,
                "ghost_pending": len(self._pending), "ghost_left": len(self._ghosts) - self._gi,
                "our_plays": self.our_plays, "our_rejected": self.our_rejected,
                "play": info_play, "tag": self.entry["tag"]}
        return obs, float(reward), done, info

    # ---------------------------------------------------------------- misc
    def state_hash(self):
        return self.eng.observe().get("state_hash")

    def episode_summary(self):
        st = self.eng.observe()
        hp = self._tower_hp(st)
        return {"tag": self.entry["tag"], "tick": self.tick, "seconds": round(self.tick * TICK_S, 1),
                "steps": self.steps, "terminated": bool(self.terminated),
                "termination_reason": (self.eng.last_episode or {}).get("termination_reason"),
                "winner": (self.eng.last_episode or {}).get("winner"),
                "outcome": getattr(self, "outcome", None), "crowns": getattr(self, "final_crowns", self._crowns(hp)),
                "reward": round(self.ep_reward, 4), "state_hash": st.get("state_hash"),
                "ghost_ok": self.ghost_ok, "ghost_rejected": self.ghost_rejected,
                "ghost_total": len(self._ghosts), "ghost_undelivered": len(self._ghosts) - self._gi,
                "ghost_reject_reasons": dict(self.ghost_reject_reasons),
                "ghost_events": list(self.ghost_events),
                "our_plays": self.our_plays, "our_rejected": self.our_rejected,
                "our_reject_reasons": dict(self.our_reject_reasons),
                "our_reject_events": list(self.our_reject_events),
                "unmapped_entities": self._n_unmapped,
                "expected_result": self.entry.get("result"), "expected_crowns": self.entry.get("final_crowns")}

    def close(self):
        self.save_deal_cache()
        self.eng.close()
