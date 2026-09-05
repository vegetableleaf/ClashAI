from pathlib import Path
p = Path("C:/Users/benpe/ClashBot/icebow/src/clashrl/sim/env.py")
s = p.read_text(encoding="utf-8")

def rep(old, new):
    global s
    assert s.count(old) == 1, (s.count(old), old[:80])
    s = s.replace(old, new)

# 0. import
rep('''from .. import detect_obs
from .. import interactions
''', '''from .. import detect_obs
from .. import geometry_reward as GR      # L59 arm G: radius-graded placement terms (sim only)
from .. import interactions
''')

# 1. config reads (after the xbow block)
rep('''        self.xbow_lane_frac = float(cfg.get("rewards", "xbow_lane_frac", default=0.35))
''', '''        self.xbow_lane_frac = float(cfg.get("rewards", "xbow_lane_frac", default=0.35))
        # L59 arm G -- RADIUS-GRADED PLACEMENT GEOMETRY (research/RADIUS_REWARD_PROPOSALS.md, gate verdicts
        # HANDOFF 5cs.29). OFF by default: with `enabled` false every branch below is byte-identical to the
        # pre-L59 code (tests/test_geometry_wiring.py pins the per-step reward sequence). When ON, the
        # binary geometry/timing tests inside _threat_response (deep_ok, the 0.50..0.80 building band, the
        # same-lane `intercept` for a role-valid counter) and the flat offensive X-Bow credit are replaced
        # by the module's graded terms; every NON-geometry gate (quiet board, triage, budget, counter
        # table, spell exemptions, the binary misread) stays exactly as it is.
        _geo = lambda k, d: cfg.get("env", "geometry", k, default=d)   # noqa: E731
        self.geo_enabled = bool(_geo("enabled", False))
        self.geo_w_geom = float(_geo("w_geom", 2.0))
        self.geo_w_time = float(_geo("w_time", 1.0))
        self.geo_pre_place_s = float(_geo("pre_place_s", 3.0))
        self.geo_p7_enabled = bool(_geo("p7_enabled", False))
        self.geo_log_all = bool(_geo("log_all_terms", True))
        self._geo_board = None        # (engine.t, Board): board_from_engine at most once per step
        self._geo_cache = None        # (key, terms): score_placement at most once per accepted placement
        self._geo_used = False        # a paying branch read the terms this step (ledger when log_all is off)
''')

# 2. helpers before _threat_response
rep('''    def _threat_response(self, card_id: int, nx: float, ny: float) -> float:
''', '''    # ------------------------------------------------------------------------------------------
    # L59 arm G: graded placement geometry (sim only; see the config block in __init__)
    # ------------------------------------------------------------------------------------------
    def _geo_threat_obj(self, board):
        """The env's assessed threat as a module BoardObj: the SAME unit `_threat_pos()` returns (max
        (danger, y) enemy troop on our half), matched by its exact engine coordinates. None when no enemy
        is on our half (then the module's own `pick_threat` is used and `geo_threat_module` logs 1)."""
        tx, ty = self._threat_pos()
        best = None
        for o in board.enemy():
            if o.kind == "troop" and abs(o.x - tx) < 1e-9 and abs(o.y - ty) < 1e-9:
                best = o
                break
        return best

    def _geo_terms(self, card_id: int, nx: float, ny: float):
        """`score_placement` ONCE per accepted placement (cached on (card, cell)); `board_from_engine`
        ONCE per step (cached on engine.t -- the deploy is still PENDING (action latency) when the reward
        block runs, so the board is the pre-placement board). The placement is scored at the SNAPPED
        landing tile the engine recorded in `last_deploy` (the tile the tap lands in), not the cell centre."""
        key = (int(card_id), float(nx), float(ny))
        if self._geo_cache is not None and self._geo_cache[0] == key:
            return self._geo_cache[1]
        t = float(self.eng.t)
        if self._geo_board is None or self._geo_board[0] != t:
            self._geo_board = (t, GR.board_from_engine(self.eng, 0))
        board = self._geo_board[1]
        spec = self.specs[card_id]
        ld = self.eng.last_deploy.get(0)
        px, py = (float(ld[1]), float(ld[2])) if (ld is not None and float(ld[3]) == t) else (float(nx), float(ny))
        placement = GR.placement_from_spec(
            spec, px, py, siege_sight=float(getattr(self.eng, "siege_sight", GR.DEFAULT_SIEGE_SIGHT)),
            tower_range=float(getattr(self.eng, "tower_range", GR.DEFAULT_TOWER_RANGE)),
            king_range=float(getattr(self.eng, "king_range", GR.DEFAULT_KING_RANGE)), db=self.db)
        threat = self._geo_threat_obj(board)
        terms = GR.score_placement(board, placement, threat=threat)
        terms["threat_module"] = 0.0 if threat is not None else 1.0
        terms["gate"] = self._geo_gate(terms)
        self._geo_cache = (key, terms)
        return terms

    def _geo_gate(self, terms) -> float:
        """TIMING gate on the placement part: 1.0 when t_cross - pre_place_s <= t_resp <= t_hit + 1.0,
        else the band value of the same edges with w = 1.5 s (linear to 0 over 1.5 s outside either edge).
        `t_resp` = deploy time (+ travel to the intercept for a troop), `t_cross` = the threat's time to
        the bridge, `t_hit` = its time to the tower's reach. 1.0 when the module computed no window (a
        bridge-block case, a standing threat, or no march path) -- the placement part is then ungated."""
        if "t_resp" not in terms:
            return 1.0
        return float(GR.band(float(terms["t_resp"]), float(terms["t_cross"]) - self.geo_pre_place_s,
                             float(terms["t_hit"]) + 1.0, 1.5))

    def _geo_credit(self, terms, kind: str) -> float:
        """w_time * timing_credit + w_geom * placement_credit(kind) * gate (only the PLACEMENT part is gated)."""
        place = GR.placement_credit(terms, kind, p7_enabled=self.geo_p7_enabled)
        credit = (self.geo_w_time * GR.timing_credit(terms)
                  + self.geo_w_geom * place * float(terms.get("gate", 1.0)))
        terms["credit"] = credit
        self._geo_used = True
        return credit

    def _geo_ledger(self, terms) -> None:
        """RECORD-ONLY ledger of the graded terms (RewardTerms.add records; it never touches the episode
        reward -- the caller's `reward +=` does, and none of these are added there). Raw term values so the
        per-match sums read in [0, 1] units; the fire counters (`geo_bridge_*`, `geo_threat_module`) log 1."""
        g = lambda k: float(terms.get(k, 0.0) or 0.0)   # noqa: E731
        add = self.rw_stats.add
        add("geo_p1", g("p1_pull_band")); add("geo_p2", g("p2_cover")); add("geo_p3", g("p3_intercept"))
        add("geo_p5", g("p5_timing")); add("geo_p6", g("p6_siege")); add("geo_p1_close", g("p1_close_penalty"))
        add("geo_p4", g("p4_spell_frac")); add("geo_p4_nado", g("p4_nado")); add("geo_p4_king", g("p4_king_activation"))
        add("geo_p7", g("p7_fragility"))
        add("geo_bridge_detected", 1.0 if g("bridge_block_detected") > 0.0 else 0.0)
        add("geo_bridge_case", 1.0 if g("bridge_block_case") > 0.0 else 0.0)
        add("geo_threat_module", g("threat_module"))
        add("geo_p1_snapshot", g("p1_snapshot")); add("geo_gate", g("gate")); add("geo_credit", g("credit"))

    def _threat_response(self, card_id: int, nx: float, ny: float) -> float:
''')

# 3. building branch
rep('''            if not (card_threat.counters(prof, tid) and 0.50 <= ny <= 0.80 and deep_ok and budget_ok):
                return 0.0                # right role but wrong geometry/timing, or budget spent
            self._threat_credits += 1
            return self.w_threat_response
''', '''            if self.geo_enabled:
                # L59 arm G: the binary band/depth test -> graded terms. Role and budget gates unchanged.
                if not (card_threat.counters(prof, tid) and budget_ok):
                    return 0.0
                credit = self._geo_credit(self._geo_terms(card_id, nx, ny), "building")
                if credit > 0.0:
                    self._threat_credits += 1     # a credit is CONSUMED only by a paid placement
                return credit
            if not (card_threat.counters(prof, tid) and 0.50 <= ny <= 0.80 and deep_ok and budget_ok):
                return 0.0                # right role but wrong geometry/timing, or budget spent
            self._threat_credits += 1
            return self.w_threat_response
''')

# 4. troop counter branch
rep('''        if card_threat.counters(prof, tid):
            if not (intercept and deep_ok and budget_ok):
                return 0.0
            self._threat_credits += 1
            return self.w_threat_response                                # right counter, placed AND timed right
''', '''        if card_threat.counters(prof, tid):
            if self.geo_enabled:
                # L59 arm G: `intercept and deep_ok` -> w_time * P5 + w_geom * P3 (P7 only if enabled) x gate.
                if not budget_ok:
                    return 0.0
                credit = self._geo_credit(self._geo_terms(card_id, nx, ny), "troop")
                if credit > 0.0:
                    self._threat_credits += 1
                return credit
            if not (intercept and deep_ok and budget_ok):
                return 0.0
            self._threat_credits += 1
            return self.w_threat_response                                # right counter, placed AND timed right
''')

# 5. X-Bow offensive branch
rep('''            elif d <= self.xbow_range:                        # OFFENSIVE: forward, in tower range = win condition set
                val = self.w_wincon
                if self.eng.t < 30.0:
''', '''            elif d <= self.xbow_range:                        # OFFENSIVE: forward, in tower range = win condition set
                val = self.w_wincon
                if self.geo_enabled:
                    # L59 arm G: the flat offensive credit -> w_geom * P6 (the siege band: bow-to-tower gap
                    # in [r_sight - 2, r_sight], dead towers off the board, enemy buildings soften). The
                    # DEFENSIVE credits (`frac` in the _defensive / out-of-range branches, xbow_deep_frac,
                    # xbow_lane_frac, w_wincon_mis) are untouched -- P6 is 0 for a centre bow by design.
                    # The first-play / split-push / hostile-deck multipliers below still apply.
                    val = self.geo_w_geom * float(self._geo_terms(card_id, nx, ny).get("p6_siege", 0.0))
                    self._geo_used = True
                if self.eng.t < 30.0:
''')

# 6. step(): invalidate the caches, log the ledger
rep('''    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        placed_id = -1
''', '''    def step(self, action: Action):
        play, card_id, cell = action
        reward = 0.0
        placed_id = -1
        self._geo_board = None; self._geo_cache = None; self._geo_used = False   # L59: per-step caches
''')
rep('''                reward += self.rw_stats.add("wincon_exec", self._bonus(self._wincon_exec(card_id, nx, ny)))           # (3) win-condition executed right
''', '''                reward += self.rw_stats.add("wincon_exec", self._bonus(self._wincon_exec(card_id, nx, ny)))           # (3) win-condition executed right
                if self.geo_enabled and (self.geo_log_all or self._geo_used):
                    # L59: record-only ledger of the graded terms for THIS placement (cached terms when a
                    # paying branch scored it; with log_all_terms every accepted placement is scored once)
                    self._geo_ledger(self._geo_terms(card_id, nx, ny))
''')

p.write_text(s, encoding="utf-8")
print("env patched")
