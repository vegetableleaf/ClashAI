"""Rollout search at LIVE decision time -- the last of the four blockers, with its safety rails.

Pipeline, per decision:

    frame + tracks -> live_bridge.build_engine   (what we think the board is)
                   -> live_opponent.sync         (what we think they hold)
                   -> rollout_search.Searcher    (roll it forward, pick an action)

THE POLICY'S ACTION IS ALWAYS COMPUTED FIRST AND IS ALWAYS THE FALLBACK. `decide()` returns None
to mean "keep what the policy chose". Search can only ever REPLACE a decision, never be the only
one available -- so every failure path below degrades to today's behaviour rather than to nothing.

WHY THE RAILS ARE THE INTERESTING PART
--------------------------------------
A confidently wrong search is WORSE than an uncertain policy. The policy hedges; search commits to
a plan built on a reconstructed world. Every guard here exists because a specific thing is known to
go wrong:

  timeout        live is real-time. Search measured ~24 ms/decision into ~230 ms of slack, but the
                 bridge adds detection and reconstruction on top. Overrun -> keep the policy.
  confidence     `OpponentCycle.confidence()` below the bar means we are guessing at their hand,
                 and the rollout opponent would be fiction. Keep the policy.
                 WARNING: its ceiling IS NOT 1.0. The deck is learned from bodies APPEARING, and spells
                 leave no body -- so a deck with two spells caps at 6/8 = 0.75. Setting
                 min_confidence above the reachable ceiling silently disables the whole feature,
                 which is exactly how the first cut shipped dead.
  freshness      a stale frame means search plans from a past board. Keep the policy.
  min_bodies     with nothing detected there is nothing to search over, and the bridge would hand
                 the searcher an empty arena it will happily "win".

/!\\ MEASURED CEILING, and it is poorly determined. Degraded search retained 13-27% of the clean
gain across four arms at n=30, and the ordering was INCOHERENT (the least-degraded arm scored
worst), which means n=30 cannot resolve them. All arms sat BELOW the 38% previously quoted. Treat
any live gain as unproven until measured over many matches.

OFF BY DEFAULT. `enabled` must be set explicitly.
"""
from __future__ import annotations

import time
from typing import Any, Optional, Sequence, Tuple

from . import live_bridge as LB
from .live_opponent import LiveOpponent
from .opponent_cycle import OpponentCycle


class LiveSearch:
    """Guarded live-search decision maker. `decide()` returns None to keep the policy's action."""

    WAIT = "WAIT"

    def __init__(self, cfg, db, rng, net, device, actions,
                 horizon: float = 12.0, cells: int = 3, topk: int = 4,
                 gate_tau: float = 0.25,
                 timeout_ms: float = 120.0,
                 min_confidence: float = 0.5,
                 min_bodies: int = 1,
                 max_frame_age_s: float = 0.6,
                 enabled: bool = False):
        self.cfg, self.db, self.rng = cfg, db, rng
        self.net, self.device, self.actions = net, device, actions
        self.horizon, self.cells, self.topk = float(horizon), int(cells), int(topk)
        self.gate_tau = float(gate_tau)
        self.timeout_ms = float(timeout_ms)
        self.min_confidence = float(min_confidence)
        self.min_bodies = int(min_bodies)
        self.max_frame_age_s = float(max_frame_age_s)
        self.enabled = bool(enabled)
        self.opp = OpponentCycle()
        # SELF-FEEDING. Nothing outside this class calls record_enemy_play(), which is how the
        # first cut shipped a feature that could NEVER fire: confidence() stayed 0.0, every
        # decision hit the confidence guard, and no counter was ever printed to say so. The plays
        # are inferred here instead, from bodies APPEARING on the board.
        self._seen_counts: dict = {}
        self._report_every = 25
        # WHY tracks were rejected, not just that they were. "bodies 124/125" says the bridge got
        # nothing; it does NOT say whether the detector saw nothing or the bridge threw everything
        # away, and those need opposite fixes.
        self.drops: dict = {}
        self._env = None            # a real SimMatchEnv, built lazily and reused
        self.errors: dict = {}      # exception type+message -> count, so "error N" is diagnosable
        # counters -- every skip reason is recorded, because a live feature that quietly never
        # fires looks exactly like one that fires and does nothing.
        self.stats = {"asked": 0, "ran": 0, "kept_policy": 0, "changed": 0, "waited": 0,
                      "skip_disabled": 0, "skip_conf": 0, "skip_bodies": 0,
                      "skip_stale": 0, "skip_timeout": 0, "skip_error": 0}
        # LAST in __init__, deliberately: the check touches `_env`, `stats` and `device`, and the
        # first version ran it beside `self.opp` -- before `_env` existed -- so it reported the
        # contract broken when the contract was fine. It caught its own author, which is the
        # behaviour wanted, but the call belongs after everything it reads.
        if self.enabled and net is not None:
            self._selftest()

    def _selftest(self) -> None:
        """Prove the net answers the searcher's call ONCE, AT STARTUP, before any match.

        Every live-search failure this feature has had was a contract mismatch that only showed up
        as a per-decision exception counter mid-match: a stub missing `db`, a track tuple of the
        wrong length, a net returning three values where five were unpacked. Each cost a run to
        find, and the last one printed `error 9` nine times while saying nothing about why.

        A mismatch is a PROPERTY OF THE WIRING, not of any particular board -- so it can be caught
        deterministically here, and a feature that cannot work is DISABLED LOUDLY instead of
        failing quietly sixty times a match.
        """
        try:
            import torch
            from .env import SimMatchEnv
            if self._env is None:
                self._env = SimMatchEnv(self.cfg)
            e = self._env
            e.reset()
            obs = (torch.from_numpy(e._last_obs).float().permute(2, 0, 1)
                   .unsqueeze(0).to(self.device) / 255.0)

            def v(a):
                import numpy as np
                return torch.from_numpy(np.asarray(a, np.float32)).unsqueeze(0).to(self.device)

            with torch.no_grad():
                out = self.net(obs, v(e.hand_vec), v(e.next_vec), v(e.elixir_vec), v(e.threat_vec))
            n = len(out)
            if n < 3:
                raise ValueError("net returned %d outputs; the searcher needs at least 3 "
                                 "(cards, cells, gate)" % n)
        except Exception as _e:                                # noqa: BLE001
            self.enabled = False
            print("[live-search] DISABLED at startup -- the network does not satisfy the "
                  "searcher's contract: %s: %s" % (type(_e).__name__, _e), flush=True)
            return
        print("[live-search] net contract OK (%d outputs); search is live" % n, flush=True)

    # ------------------------------------------------------------------ observation feed
    def record_enemy_play(self, card_key: str) -> None:
        """Feed an observed opponent play so the hand estimate stays in step."""
        self.opp.record_play(card_key)

    def reset(self) -> None:
        self.opp.reset()
        self._seen_counts.clear()

    def note_bodies(self, bodies) -> int:
        """Infer opponent plays from enemy bodies appearing on the board.

        A card entering play shows up as a NEW body. Counting per key and recording only the
        INCREASE handles multi-body cards (a Skeleton Army is one play, not fifteen) and avoids
        re-counting a unit that merely persists between frames.

        WARNING: it cannot see spells, and a body that leaves detection and returns will be counted
        twice. Both corrupt the cycle -- and `OpponentCycle` self-heals only on the NEXT genuine
        sighting of that card. This is the weakest link in the live chain; treat the hand as an
        estimate, which is what `min_confidence` is guarding.
        """
        counts: dict = {}
        for b in bodies:
            if int(b.get("team", 1)) == 1:                     # enemy side only
                counts[b["key"]] = counts.get(b["key"], 0) + 1
        added = 0
        for key, n in counts.items():
            prev = self._seen_counts.get(key, 0)
            if n > prev:
                self.opp.record_play(key)                      # one play, however many bodies
                added += 1
            self._seen_counts[key] = n
        for key in list(self._seen_counts):
            if key not in counts:
                self._seen_counts[key] = 0                     # gone -> next sighting is new
        return added

    # ------------------------------------------------------------------ the decision
    def decide(self, tracks: Sequence[Any], hand_ids: Sequence[int], elixir: float,
               policy_action: Tuple[int, int], frame=None, frame_t: Optional[float] = None,
               opp_elixir: float = 5.0, match_t: float = 0.0,
               towers_alive=None, tower_hp=None) -> Optional[Any]:
        """Return (card_id, cell), LiveSearch.WAIT, or None to keep the policy's action."""
        self.stats["asked"] += 1
        # REPORT ON `asked`, BEFORE ANY SKIP CAN RETURN. The first cut printed after
        # `stats["ran"] += 1`, i.e. only when search DID run -- so a feature that skipped every
        # decision printed nothing at all, which is precisely the state the counters exist to
        # reveal. Visibility must never be gated on the thing whose absence you are debugging.
        if self._report_every and self.stats["asked"] % self._report_every == 0:
            print("[live-search] " + self.summary(), flush=True)
        if not self.enabled:
            self.stats["skip_disabled"] += 1
            return None
        if frame_t is not None and (time.time() - float(frame_t)) > self.max_frame_age_s:
            self.stats["skip_stale"] += 1
            return None
        t0 = time.time()
        try:
            bodies = LB.tracks_to_bodies(self.db, tracks, self.actions,
                                         frame=frame, cfg=self.cfg, drops=self.drops)
            self.note_bodies(bodies)                          # learn their deck from what appears
            if len(bodies) < self.min_bodies:
                self.stats["skip_bodies"] += 1
                return None
            # CHECKED AFTER note_bodies, not before: the confidence gate reads a deck that only
            # this call populates, so testing it first made it permanently 0.0.
            if self.opp.confidence() < self.min_confidence:
                self.stats["skip_conf"] += 1
                return None
            eng = LB.build_engine(self.cfg, self.db, self.rng, bodies,
                                  elixir=(float(elixir), float(opp_elixir)),
                                  t=float(match_t), towers_alive=towers_alive,
                                  tower_hp=tower_hp)
            opp = LiveOpponent(self.cfg, self.db, self.rng, self.opp.known_deck())
            opp.sync(self.opp, opp_elixir, eng)
            action = self._search(eng, opp)
        except Exception as _e:                                # noqa: BLE001
            # A live feature must never take the match down -- but it must SAY WHAT WENT WRONG.
            # "error 17" told the owner nothing, which is the third time a bare counter has cost a
            # run to diagnose. The type and message are recorded and printed with the summary.
            self.stats["skip_error"] += 1
            key = "%s: %s" % (type(_e).__name__, str(_e)[:60])
            self.errors[key] = self.errors.get(key, 0) + 1
            return None
        if (time.time() - t0) * 1000.0 > self.timeout_ms:
            # The answer arrived, but too late to describe the board any more.
            self.stats["skip_timeout"] += 1
            return None
        self.stats["ran"] += 1
        if action is None:
            self.stats["kept_policy"] += 1
            return None
        if action == self.WAIT:
            self.stats["waited"] += 1
            return self.WAIT
        if tuple(action) == tuple(policy_action):
            self.stats["kept_policy"] += 1
            return None
        self.stats["changed"] += 1
        return action

    # ------------------------------------------------------------------ internals
    def _search(self, eng, opp):
        """Run the searcher over a reconstructed engine. Split out so tests can stub it."""
        from . import rollout_search as RS

        # A REAL SimMatchEnv WITH ITS ENGINE SWAPPED, not a hand-rolled stub. My first version
        # passed an object carrying only `eng` and `opp`, and Searcher/Scorer also read env.db,
        # env.actions, env.n_cells and env.specs -- so every decision died with
        #     AttributeError: '_Env' object has no attribute 'db'
        # 19 times out of 25, and the bare error counter could not say so until it was taught to
        # name exceptions. Enumerating that surface by hand is exactly the guesswork that failed;
        # the real env HAS the surface by construction, and it is built ONCE here rather than
        # per decision.
        if self._env is None:
            from .env import SimMatchEnv
            self._env = SimMatchEnv(self.cfg)
        self._env.eng = eng
        self._env.opp = opp

        searcher = RS.Searcher(self._env, self.net, self.device, self.horizon, 1,
                               self.topk, 1.0, self.gate_tau, cells=self.cells)
        act, searched = searcher.act(0)
        if not searched or act is None:
            return None
        gate, card, cell = int(act[0]), int(act[1]), int(act[2])
        return self.WAIT if gate == 0 else (card, cell)

    def summary(self) -> str:
        s = self.stats
        base = ("live-search: asked %d, ran %d, changed %d, waited %d | skipped "
                "disabled %d conf %d bodies %d stale %d timeout %d error %d"
                % (s["asked"], s["ran"], s["changed"], s["waited"], s["skip_disabled"],
                   s["skip_conf"], s["skip_bodies"], s["skip_stale"], s["skip_timeout"],
                   s["skip_error"]))
        if s.get("skip_unaffordable"):
            base += " | UNAFFORDABLE picks rejected: %d" % s["skip_unaffordable"]
        if self.drops:
            top = sorted(self.drops.items(), key=lambda kv: -kv[1])[:6]
            base += " | tracks: " + ", ".join(f"{k}={v}" for k, v in top)
        if self.errors:
            top = sorted(self.errors.items(), key=lambda kv: -kv[1])[:3]
            base += " | errors: " + "; ".join(f"{k} x{v}" for k, v in top)
        return base
