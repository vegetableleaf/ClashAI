import io
p = 'rollout_search.py'
s = io.open(p, encoding='utf-8').read()
orig = s


def rep(old, new, n=1):
    global s
    c = s.count(old)
    assert c == n, f'expected {n} got {c} for: {old[:70]!r}'
    s = s.replace(old, new)


# 1. signature
rep("""                 force_policy=False, cells=1, force_play=False, reseed_opp=False):""",
    """                 force_policy=False, cells=1, force_play=False, reseed_opp=False,
                 phase_lo=None, phase_hi=None, jit_drop=0.0, jit_pos=0.0, jit_hp=0.0,
                 jit_play=False, dump_decisions=False):""")

# 2. counters + jitter state
rep("""        self.cands = 0
        self.rollout_s = 0.0
        self.margins = []""",
    """        self.cands = 0
        self.rollout_s = 0.0
        self.margins = []
        # -- MATCH-POSITION CONFOUND instrumentation -------------------------------
        # A rollout that reaches `eng.done` has OBSERVED the terminal outcome instead of
        # predicting it. Counted so the horizon curve can be read against how often that happens.
        self.phase_lo = phase_lo          # only search decisions with phase_lo <= eng.t < phase_hi
        self.phase_hi = phase_hi
        self.roll_total = 0
        self.roll_clamped = 0             # rollouts that hit eng.done before the horizon ran out
        self.dec_rows = []                # per-decision [t, ncand, nclamped, disagree, polplay, pickplay]
        self.dump_decisions = bool(dump_decisions)
        self._clamped_now = 0
        # -- LIVE-SEARCH PERCEPTION probe ------------------------------------------
        # Perturb the forked board the way the DETECTOR would mis-see it, then ask whether the
        # search still picks the same action. Grounded in this project's own measured detector
        # numbers (config observation.sim_detector_recall 0.823 / presence_recall 0.85).
        self.jit_drop = float(jit_drop)   # per-unit dropout probability
        self.jit_pos = float(jit_pos)     # gaussian sigma on x,y in TILES
        self.jit_hp = float(jit_hp)       # uniform +- fractional HP error
        self.jit_play = bool(jit_play)    # play the JITTERED choice (else play clean, just measure)
        self.jit_on = (self.jit_drop > 0 or self.jit_pos > 0 or self.jit_hp > 0)
        self._jit_active = False
        self._jit_plan = None
        self._jit_rng = random.Random(20260827)
        self.jit_dec = 0                  # decisions where both searches ran
        self.jit_agree = 0                # ...and they chose the SAME action
        self.jit_agree_card = 0           # ...same card (cell may differ)
        self.jit_dropped = 0
        self.jit_seen = 0""")

# 3. rollout: jitter + clamp detection
rep("""        eng, opp = copy.deepcopy((e.eng, e.opponent))
        if self.reseed_opp:""",
    """        eng, opp = copy.deepcopy((e.eng, e.opponent))
        if self._jit_active and self._jit_plan is not None:
            self._apply_jitter(eng)
        if self.reseed_opp:""")

rep("""        for _ in range(self.rollout_steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(self.subs):
                eng.advance(e.sub_dt)
                if eng.done:
                    break
        return self.scorer.score(s0, eng, spent)""",
    """        for _ in range(self.rollout_steps):
            if eng.done:
                break
            opp.act(eng)
            for _ in range(self.subs):
                eng.advance(e.sub_dt)
                if eng.done:
                    break
        self.roll_total += 1
        if eng.done:                      # the horizon ran past the END of the match
            self.roll_clamped += 1
            self._clamped_now += 1
        return self.scorer.score(s0, eng, spent)

    # -- perception jitter --------------------------------------------------
    def _plan_jitter(self, eng):
        '''One coherent misperception per DECISION, shared by every candidate at that decision.

        Keyed on `Unit.deploy_seq`, never `id()` (conflicts.md I10-FOLLOWUP: CPython recycles a
        dead body's address). Common random numbers across candidates, so the comparison between
        candidates stays fair and only the STARTING STATE is wrong -- which is the live case.
        '''
        r = self._jit_rng
        plan = {}
        for u in eng.units:
            drop = (r.random() < self.jit_drop) if self.jit_drop > 0 else False
            dx = r.gauss(0.0, self.jit_pos) if self.jit_pos > 0 else 0.0
            dy = r.gauss(0.0, self.jit_pos) if self.jit_pos > 0 else 0.0
            hm = (1.0 + r.uniform(-self.jit_hp, self.jit_hp)) if self.jit_hp > 0 else 1.0
            plan[u.deploy_seq] = (drop, dx, dy, hm)
            self.jit_seen += 1
            if drop:
                self.jit_dropped += 1
        self._jit_plan = plan

    def _apply_jitter(self, eng):
        plan = self._jit_plan
        keep, gone = [], set()
        for u in eng.units:
            pl = plan.get(u.deploy_seq)
            if pl is None:
                keep.append(u)
                continue
            drop, dx, dy, hm = pl
            if drop:
                gone.add(u.deploy_seq)
                continue
            if dx or dy:
                u.x += dx
                u.y += dy
            if hm != 1.0:
                u.hp = max(1.0, u.hp * hm)
            keep.append(u)
        if gone:
            eng.units = keep
            # a dropped body must not stay as someone's target -- the engine re-acquires on None
            for u in eng.units:
                t = getattr(u, 'target', None)
                if t is not None and getattr(t, 'deploy_seq', None) in gone:
                    u.target = None
            for team in (0, 1):
                for tw in eng.towers[team]:
                    t = getattr(tw, 'target', None)
                    if t is not None and getattr(t, 'deploy_seq', None) in gone:
                        tw.target = None""")

# 4. act(): phase gate + decision dump + jitter double-search
rep("""        pol, (cq_m, ceq, gq_m, playable) = self.greedy_action()
        if self.interval <= 0 or (step_i % self.interval) or self.env.eng.done:
            return pol, False""",
    """        pol, (cq_m, ceq, gq_m, playable) = self.greedy_action()
        if self.interval <= 0 or (step_i % self.interval) or self.env.eng.done:
            return pol, False
        tnow = float(self.env.eng.t)
        if self.phase_lo is not None and tnow < self.phase_lo:
            return pol, False
        if self.phase_hi is not None and tnow >= self.phase_hi:
            return pol, False""")

rep("""        self._rs_ctr += 1
        self._rs_seed = 1_000_003 * self._rs_ctr + 7
        t0 = time.perf_counter()
        scores = [self._rollout(a) for a in cands]
        self.rollout_s += time.perf_counter() - t0""",
    """        self._rs_ctr += 1
        self._rs_seed = 1_000_003 * self._rs_ctr + 7
        t0 = time.perf_counter()
        self._clamped_now = 0
        self._jit_active = False
        scores = [self._rollout(a) for a in cands]
        clean_pick = cands[int(np.argmax(scores))]
        if self.jit_on:
            # SAME decision, SAME candidates, a MISPERCEIVED starting board.
            self._plan_jitter(self.env.eng)
            self._jit_active = True
            jscores = [self._rollout(a) for a in cands]
            self._jit_active = False
            self._jit_plan = None
            jit_pick = cands[int(np.argmax(jscores))]
            self.jit_dec += 1
            if jit_pick == clean_pick:
                self.jit_agree += 1
            if (jit_pick[0] == clean_pick[0]) and (jit_pick[0] == 0 or jit_pick[1] == clean_pick[1]):
                self.jit_agree_card += 1
            if self.jit_play:
                scores = jscores
        self.rollout_s += time.perf_counter() - t0""")

rep("""        if pick != pol:
            self.disagree += 1
            if pick[0] == 0 and pol[0] == 1:""",
    """        if self.dump_decisions:
            self.dec_rows.append([round(tnow, 2), len(cands), self._clamped_now,
                                  1 if pick != pol else 0, int(pol[0]), int(pick[0])])
        if pick != pol:
            self.disagree += 1
            if pick[0] == 0 and pol[0] == 1:""")

# 5. main(): args
rep("""    ap.add_argument("--force-policy", action="store_true",""",
    """    ap.add_argument("--phase-lo", type=float, default=None,
                    help="only search decisions at game time >= this (MATCH-POSITION arm)")
    ap.add_argument("--phase-hi", type=float, default=None,
                    help="only search decisions at game time < this")
    ap.add_argument("--jit-drop", type=float, default=0.0,
                    help="fork-state dropout prob per unit (detector recall miss)")
    ap.add_argument("--jit-pos", type=float, default=0.0, help="fork-state x/y gaussian sigma, TILES")
    ap.add_argument("--jit-hp", type=float, default=0.0, help="fork-state +- fractional HP error")
    ap.add_argument("--jit-play", action="store_true",
                    help="PLAY the jittered choice (default: play the clean one, measure agreement)")
    ap.add_argument("--dump-decisions", action="store_true",
                    help="record [t, ncand, nclamped, disagree, polplay, pickplay] per decision")
    ap.add_argument("--force-policy", action="store_true",""")

rep("""                 gate_tau, force_policy=args.force_policy, cells=args.cells,
                 force_play=args.force_play, reseed_opp=args.reseed_opp)""",
    """                 gate_tau, force_policy=args.force_policy, cells=args.cells,
                 force_play=args.force_play, reseed_opp=args.reseed_opp,
                 phase_lo=args.phase_lo, phase_hi=args.phase_hi,
                 jit_drop=args.jit_drop, jit_pos=args.jit_pos, jit_hp=args.jit_hp,
                 jit_play=args.jit_play, dump_decisions=args.dump_decisions)""")

rep("""        "margin_mean": float(np.mean(s.margins)) if s.margins else 0.0,
        "records": recs,""",
    """        "margin_mean": float(np.mean(s.margins)) if s.margins else 0.0,
        "phase_lo": args.phase_lo, "phase_hi": args.phase_hi,
        "roll_total": s.roll_total, "roll_clamped": s.roll_clamped,
        "jit_drop": args.jit_drop, "jit_pos": args.jit_pos, "jit_hp": args.jit_hp,
        "jit_play": bool(args.jit_play),
        "jit_dec": s.jit_dec, "jit_agree": s.jit_agree, "jit_agree_card": s.jit_agree_card,
        "jit_seen": s.jit_seen, "jit_dropped": s.jit_dropped,
        "dec_rows": s.dec_rows,
        "records": recs,""")

io.open(p, 'w', encoding='utf-8').write(s)
print(f'patched OK, {len(orig)} -> {len(s)} chars')
