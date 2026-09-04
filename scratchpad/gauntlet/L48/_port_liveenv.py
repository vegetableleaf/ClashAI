p='hogeq/src/clashrl/env.py'
s=open(p,encoding='utf-8').read()
def rep(old,new):
    global s
    assert s.count(old)==1,(old[:70],s.count(old)); s=s.replace(old,new)

rep('''_RIVER_BOARD_Y = 0.5            # board-true river (the canonical render is drawn in board space)
''','''_RIVER_BOARD_Y = 0.5            # board-true river (the canonical render is drawn in board space)
# Tower anchors in BOARD space, copied from the sim engine's tower coordinates through
# `sim/view.to_local` (team 0): princess (0.19, 0.80)/(0.81, 0.80), king (0.50, 0.91), mirrored
# for the enemy. Order L, R, king -- the same order as `env.my_towers` and `TowerTracker.*_alive`.
# The frame-space `env.my_towers` (y 0.615/0.72) drew our towers 17-18 rows too high in the
# board-space canonical render (5cs.6); the enemy king's warp saturates to y 0.0, so the
# enemy side is copied from the sim too rather than warped.
_SIM_TOWERS_BOARD = ([(7 / 36, 51 / 64), (29 / 36, 51 / 64), (0.5, 29 / 32)],      # exact: int() rounding
                     [(7 / 36, 13 / 64), (29 / 36, 13 / 64), (0.5, 3 / 32)])       # must match the sim's
''')

rep('''        self.tornado_time = float(cfg.get("env", "tornado_time", default=1.2))
        self.royal_delivery_time = float(cfg.get("env", "royal_delivery_time", default=3.0))
''','''        self.tornado_time = float(cfg.get("env", "tornado_time", default=1.2))
        # CAST DELAY (owner, 2026-09-03): ~1 s passes between the tap and the spell actually
        # appearing on the board, on top of a rocket's flight. Every lead is scaled by it.
        self.spell_cast_delay = float(cfg.get("env", "spell_cast_delay_s", default=1.0))
        self.royal_delivery_time = float(cfg.get("env", "royal_delivery_time", default=3.0))
''')

rep('''        self._opp_elixir = OpponentElixirEstimator(db)   # live estimate from mirrored spend accounting
''','''        self._opp_elixir = OpponentElixirEstimator(db)   # live estimate from mirrored spend accounting
        # SIM/LIVE PARITY of opponent-memory slot 5 (2026-09-03, HANDOFF 5cr.8). The sim writes OUR
        # elixir there (sim/env.py mem[5] = eng.elixir[0]/10 since 3bc1d45); live wrote the OPPONENT
        # estimate. MEASURED on the live obs dump (s2, 425 decisions): the PPO gate reads that slot as
        # its own elixir -- with the live value (~0.03) p(play)>0.25 at >=9 elixir on 1.7% of states;
        # with own elixir in the slot, 96.9%. "own_elixir" = what the policy was trained on;
        # "opp_estimate" = the legacy live value. The estimate itself is still computed either way
        # (the trade potential reads self._opp_est).
        self._mem5_source = str(cfg.get("env", "opp_mem_slot5", default="opp_estimate"))
        if self._mem5_source not in ("opp_estimate", "own_elixir"):
            raise ValueError("env.opp_mem_slot5 must be 'opp_estimate' or 'own_elixir', got %r" % self._mem5_source)
        print("[env] opp-memory slot 5 source: %s" % self._mem5_source)
''')

rep('''        mem[5] = self._opp_elixir.update(self.elixir, dets, now)
        self._opp_est = float(mem[5])                    # the trade potential reads the same estimate
''','''        self._opp_est = float(self._opp_elixir.update(self.elixir, dets, now))   # the trade potential reads this estimate
        mem[5] = self._opp_est if self._mem5_source == "opp_estimate" else float(self.elixir_vec[0])
''')

rep('''            img = replay_bc.canonical_render(dets, self.cfg, int(oh), int(ow), _RIVER_BOARD_Y)
''','''            # Towers at the sim's board-true rows, dead ones not drawn (5cs.6: frame-space
            # anchors put our towers where the sim shows our deployed buildings -> gate idle).
            _al = (list(getattr(self.tower, "mine_alive", []) or []) or None,
                   list(getattr(self.tower, "enemy_alive", []) or []) or None)
            img = replay_bc.canonical_render(dets, self.cfg, int(oh), int(ow), _RIVER_BOARD_Y,
                                             anchors=_SIM_TOWERS_BOARD, alive=_al)
''')

rep('''        cx, cy = self.actions.cell_center(gx, gy)
        tracks = self._enemy_tracks_now()
        base = card_threat.base_key(self.vision.deck_keys[card_id]) if 0 <= card_id < self.n_cards else ""
        kb = self.db.get(base) or {}
        if base == "the_log":
            # A ROLL, NOT A BLAST. The circular test below passes for a Log dropped just forward
            # of a troop -- the troop is a tile away, well inside the radius -- so this function
            # used to return early and the corridor correction never ran, which is precisely the
            # "log played too high, hits nothing, scores a hit" report (2026-08-20). Ask the real
            # question instead: would the roll touch anything?
            if log_hits(cx, cy, tracks, self.log_half_w, self.log_roll, self.air_bases):
''','''        cx, cy = self.actions.cell_center(gx, gy)
        # with_base=True: lead_velocity's KB walking-speed fallback needs the card name, and a
        # track under 0.5 s old reports ZERO velocity without it. Called without the base until
        # 2026-09-03, so the lead below was a no-op on exactly the fresh tracks that need it most.
        tracks = self._enemy_tracks_now(with_base=True)
        base = card_threat.base_key(self.vision.deck_keys[card_id]) if 0 <= card_id < self.n_cards else ""
        kb = self.db.get(base) or {}
        # LEAD BEFORE YOU JUDGE (owner, 2026-09-03: "it plays the log perfectly 1-2 tiles too far
        # forward ... fails to consider the cast time"). The gates below used to ask "does the
        # model's aim cover something NOW?" on the CURRENT positions, pass for an aim drawn
        # through the push where it stands, and return the model's cell untouched -- so the lead
        # six lines further down never ran on the one cast that needed it. A medium troop walks 1
        # tile and a hog 2 in the ~1 s cast delay, which is exactly the observed miss. Every test
        # and every correction here now runs on where the enemies WILL BE when the spell lands.
        eta = self._impact_time(cx, cy, is_rocket=False, is_log=(base == "the_log"))
        led = []
        for t in tracks:
            vx, vy = lead_velocity(t, self.db)
            led.append((t[0] + vx * eta, t[1] + vy * eta) + tuple(t[2:]))
        tracks = led or tracks
        if base == "the_log":
            # A ROLL, NOT A BLAST. The circular test below passes for a Log dropped just forward
            # of a troop -- the troop is a tile away, well inside the radius -- so this function
            # used to return early and the corridor correction never ran, which is precisely the
            # "log played too high, hits nothing, scores a hit" report (2026-08-20). Ask the real
            # question instead: would the roll touch anything -- at the PREDICTED positions?
            if log_hits(cx, cy, tracks, self.log_half_w, self.log_roll, self.air_bases):
''')

rep('''            # corridor through the predicted positions.
            eta = self._impact_time(cx, cy, is_rocket=False)
            led = []
            for t in tracks:
                vx, vy = lead_velocity(t, self.db)
                led.append((t[0] + vx * eta, t[1] + vy * eta) + tuple(t[2:]))
            got = log_corridor_cell(cx, cy, led or tracks, self.actions)
''','''            # corridor through the predicted positions (tracks are ALREADY led above).
            got = log_corridor_cell(cx, cy, tracks, self.actions)
''')

rep('''    def _impact_time(self, cx: float, cy: float, is_rocket: bool, is_rd: bool = False) -> float:
        """Seconds from cast to effect. A rocket's flight time grows ~linearly with the
        distance from its launch point to the target; a tornado activates almost immediately;
        Royal Delivery lands after a long fixed delay."""
        if is_rd:
            return self.royal_delivery_time
        if not is_rocket:
            return self.tornado_time
''','''    def _impact_time(self, cx: float, cy: float, is_rocket: bool, is_rd: bool = False,
                     is_log: bool = False) -> float:
        """Seconds from cast to effect. Every spell first pays the CAST DELAY (tap -> it exists on
        the board, owner-observed ~1 s, `env.spell_cast_delay_s`); a rocket then flies, growing
        ~linearly with the distance from its launch point; a tornado activates after tornado_time
        (or the cast delay, whichever is longer); a Log starts rolling right after the delay, its
        own travel being what the corridor length covers; Royal Delivery lands after a long fixed
        delay."""
        if is_rd:
            return self.royal_delivery_time
        if is_log:
            return self.spell_cast_delay
        if not is_rocket:
            return max(self.tornado_time, self.spell_cast_delay)
''')

rep('''        return min(max(self.rocket_base_time + d_tiles / self.rocket_speed_tiles, 0.6),
                   self.spell_eval_time)
''','''        # cast delay (tap -> rocket appears, owner-observed ~1 s) THEN the flight; the old 0.3 s
        # rocket_base_time was the only pre-flight term and is now the floor, not an addend.
        return min(max(max(self.rocket_base_time, self.spell_cast_delay) + d_tiles / self.rocket_speed_tiles, 0.6),
                   self.spell_eval_time)
''')

rep('''        self.controller.tap(*self.play_again)
        time.sleep(self.menu_delay)
        detail = {"crowns": (blue_c, red_c), "scoreboard": (sb_blue, sb_red), "towers": (t_blue, t_red)}
''','''        # UNLESS a stop is already requested: re-queueing then throws a ladder match nobody
        # will play (the session ends before reset() runs; 5cr.8 -- one thrown match per session).
        if self.stop_requested is None or not self.stop_requested():
            self.controller.tap(*self.play_again)
            time.sleep(self.menu_delay)
        detail = {"crowns": (blue_c, red_c), "scoreboard": (sb_blue, sb_red), "towers": (t_blue, t_red)}
''')
open(p,'w',encoding='utf-8').write(s); print("live env patched")

# ---- train_rl.py: the greedy gate rule tau
p='hogeq/src/clashrl/train_rl.py'
s=open(p,encoding='utf-8').read()
rep('''    wait_prob = float(cfg.get("train", "explore_wait_prob", default=0.4))
''','''    wait_prob = float(cfg.get("train", "explore_wait_prob", default=0.4))
    _rl_gate_tau = cfg.get("train", "rl_gate_tau", default=None)          # None = legacy 0.5 rule (5cr)
    _rl_gate_tau = None if _rl_gate_tau is None else float(_rl_gate_tau)
    print("[train-rl] greedy gate rule: %s" % ("WAIT iff p(play) <= %.2f (sim parity)" % _rl_gate_tau
                                                if _rl_gate_tau is not None else "WAIT iff Q(wait) >= Q(play) (legacy, = tau 0.5)"))
''')
rep('''        _pol = (0, 0, 0) if wait_val >= play_val else (1, card_id, int(ceq.argmax()))
''','''        # SIM/LIVE GATE-RULE PARITY (2026-09-03, HANDOFF 5cr). The sim's greedy rule
        # (train_sim_ppo.choose_greedy, play.py) is WAIT iff sigmoid(play - wait) <= ppo_gate_threshold
        # (0.25); the comparison above is the same test at 0.5. MEASURED on gatec2_m10k over 5,371
        # sim decisions: p(play) 99th percentile 0.358, so the 0.5 rule keeps 0.1% of the plays the
        # 0.25 rule makes (99% lost) -- at epsilon 0 the PPO policy essentially never played live,
        # and every live play came from exploration or the leak-guard wheel. `train.rl_gate_tau`
        # unset keeps the old rule (so the baseline stays measurable); set it to the sim's tau.
        if _rl_gate_tau is not None:
            _wait = bool(torch.sigmoid(play_val - wait_val) <= _rl_gate_tau)
        else:
            _wait = bool(wait_val >= play_val)
        _pol = (0, 0, 0) if _wait else (1, card_id, int(ceq.argmax()))
''')
open(p,'w',encoding='utf-8').write(s); print("train_rl patched")
