"""Public-audited live pilot with opt-in inference experiments.

The canonical manual live entry uses this pilot. Default decisions delegate to
live_gen.py exactly; sampling and area aim remain disabled until accepted.
"""
import numpy as np
import torch

from .live_gen import GenPilot as LegacyGenPilot, FORM_PAD
from .e1_eval import allowed_slots
from .model_v3 import cell_xy
from dataclasses import replace

from .decision_options import (BARREL_KEY, DecisionOptions, barrel_landings, choose_cells, decide, enemy_unit_count,
                               is_xbow, lethal_rocket_choice, tau_threat_state, threat_on, tower_threat,
                               xbow_dead_lane_cells, enemy_body_tiles, princess_dead_state, rocket_covers_king,
                               rocket_kills_king, log_air_board, log_air_ground_child_tiles, recently_hit,
                               barrel_goblin_tiles)
from .live_mem import my_side_of
from .decision_options import enemy_princess_hps, hp_after, record_hp

# W4 hazard gate decoding: game seconds one live decision may accrue. Live decides every reader frame (logged decisions
# ~10 ticks apart, SIM every 10); a CPU-starved loop reaches ~30 ticks (1.5 s). 2.0 s = the WAIT-row stride the gate was
# trained on: above the slowest normal cadence (so the hazard stays cadence-invariant) while a 1-3 s reader stall
# accrues at most 2 s on its one (possibly stale) frame instead of a near-certain play.
HAZARD_STEP_CAP_S = 2.0


def hazard_step_s(prev, tick):
    """Game seconds since the previous decision IF a play was possible there and none was made (the interval was
    play-possible waiting); else 0. ``prev`` = (tick, waited) of the previous decision this match, or None. A play
    (tap -> pending -> landing, during which live_play does not decide), a no-affordable decision or the first decision
    of a match accrue nothing: pending/lockout time never adds hazard. Ticks are the reader's game clock, never wall
    clock; capped at HAZARD_STEP_CAP_S."""
    if prev is None or not prev[1] or tick <= prev[0]:
        return 0.0
    return min(HAZARD_STEP_CAP_S, (tick - prev[0]) * 0.05)


def load_posture(ckpt, device):
    """C1 stage B: the checkpoint's trained posture head (rl_royale.load_posture_head: argmax, as search_s0) or None
    when it carries none (rl_royale is not even imported then). Refuses a head whose d_g is not the trunk's width."""
    st = torch.load(ckpt, map_location='cpu')
    rl = st.get('rl') or {}
    if 'posture_head' not in rl:
        return None
    if int(rl['posture']['d_g']) != int(st['args']['d']):
        raise ValueError(f"posture head d_g {rl['posture']['d_g']} != the model's d {st['args']['d']} ({ckpt})")
    from .rl_royale import load_posture_head
    return load_posture_head(ckpt, str(device))


def posture_summary(posture):
    """--check / start log: how a wiring check sees the head (None = no head)."""
    return None if posture is None else f"on (every {posture['every']}, dtau {posture['dtau']})"


class FollowUpPlanner:
    """--follow-up-taps (L74 latency2): the decision layer's way to ask for a SECOND play before the first is confirmed.
    A decision dict that wants one carries ``d['follow_ups'] = [self.plan_follow_up(frame, d, 'Tornado', xy, after_ticks=N)]``;
    live_play.py taps it N game ticks after the first decision (own affordability check, cancelled if the first is refused).
    Stateless: it only resolves the card in the CURRENT hand, so it changes no decision unless a caller uses it."""

    def plan_follow_up(self, frame, first, name, xy, after_ticks, within_ticks=20, afford_ticks=None, require_first=True):
        """-> a decision-shaped dict for card ``name`` at my-frame cell ``xy``, to be tapped ``after_ticks`` game ticks after
        ``first`` (the dict of the play it follows) and no later than ``within_ticks`` past that; None when the card is not in
        my hand outside ``first``'s slot (a card that only arrives in the slot ``first`` frees cannot be pipelined).
        ``afford_ticks``: elixir horizon of its affordability check (None = live_play.FOLLOW_AFFORD_TICKS);
        ``require_first``: cancel it when ``first`` is refused (default; False = play it regardless)."""
        from .live_mem import deck_of
        if after_ticks < 0 or within_ticks < 0 or not (0.0 <= xy[0] <= 1.0 and 0.0 <= xy[1] <= 1.0):
            raise ValueError(f'follow-up needs after_ticks/within_ticks >= 0 and xy in [0, 1]: {after_ticks}, {within_ticks}, {xy}')
        side = my_side_of(frame)
        me = next(p for p in frame['players'] if int(p['side']) == side)
        _, names = deck_of(frame, side)
        forms = list(me.get('deck_form_flags') or [0] * 8)
        for pos, di in enumerate(me['hand_deck_indices']):
            if di < 0 or pos == first['hand_pos'] or str(names[di]).lower() != str(name).lower():
                continue
            return dict(play=True, p_play=float(first['p_play']), hand_pos=pos, no_affordable=False, deck_index=int(di),
                        card=self._card(names[di]), form=int(forms[di]), name=names[di], xy=(float(xy[0]), float(xy[1])),
                        follow=dict(after_ticks=int(after_ticks), within_ticks=int(within_ticks), afford_ticks=afford_ticks,
                                    require_first=bool(require_first)))
        return None


class GenPilot(FollowUpPlanner, LegacyGenPilot):
    def __init__(self, *args, decision_options=None, decision_seed=0, public_audit=False, gate_sample=0.0,
                 gate_sample_step_ticks=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.gate_sample = float(gate_sample)   # live --gate-sample T (pilot 10-28): > 0 = the trainer's sampled gate at T
        if not (self.gate_sample >= 0 and np.isfinite(self.gate_sample)):
            raise ValueError('gate_sample must be finite and >= 0 (0 = off)')
        self.gate_seed, self.rng_gate, self.last_gate_draw = None, None, None
        self.gate_sample_step_ticks = int(gate_sample_step_ticks)   # GATE-SAMPLE 10-30: > 0 = per unit of time (gate_step)
        if self.gate_sample_step_ticks < 0 or (self.gate_sample_step_ticks and not self.gate_sample > 0):
            raise ValueError('gate_sample_step_ticks needs gate_sample > 0 (0 = one trainer draw per decision)')
        self._gate_prev = None                  # (game tick, sampled WAIT) of the previous decision this match
        self.decision_options = decision_options or DecisionOptions()
        if self.gate_sample > 0 and not self.decision_options.active:
            raise ValueError('gate_sample needs decision options active (the unified decide; tau_phase as the trainer)')
        if self.decision_options.rocket_tornado == 'rocket_only':
            raise ValueError('rocket_tornado rocket_only is a SIM measurement ablation, not a live mode')
        if self.decision_options.rocket_tornado != 'off' and not hasattr(self, 'plan_follow_up'):
            raise ValueError('rocket_tornado needs the pipelined follow-up tap (GenPilot.plan_follow_up, --follow-up-taps branch)')
        if self.decision_options.uses_barrels and getattr(self, 'feature_version', 1) < 4:
            raise ValueError('log_aim / log_air need a feature_version >= 4 checkpoint (public projectile tokens)')
        self.decision_seed = int(decision_seed)
        self.match_index = -1
        self.match_seed = self.decision_seed
        self.rng_decisions = np.random.default_rng(self.match_seed)
        self.public_audit = bool(public_audit)
        self._public_audit_snapshot = None
        self._hazard_prev = None                # (game tick, waited with a play possible) of the previous decision
        self._threat_state = None               # decision_options.tower_threat state of the previous decision
        self._princess_dead_state = None        # decision_options.princess_dead_state of the previous decision
        self._tau_threat_state = None           # decision_options.tau_threat_state of the previous decision
        self.rv_hist, self.rv_threat_state, self.rv_threatened = None, None, False   # rocket_value: lead history / tower-fire state
        self.posture = load_posture(args[0] if args else kwargs['ckpt'], self.dev)   # C1 stage B; None = no head
        if self.posture is not None and not self.decision_options.active:
            raise ValueError('a posture-head checkpoint needs decision options active (live applies dtau where SIM '
                             'decide_batch does: tau_delta after tau_phase / tau_threatened)')

    def reset_posture(self):
        """C1: forget the posture in force and the seen opponent cards (a new match chooses afresh)."""
        for k in ('_posture', '_posture_new', '_ctx_seen', 'posture_counts', 'posture_choices'):
            self.__dict__.pop(k, None)

    def _posture_dtau(self, frame, g):
        """C1 stage B: SIM's own e1_eval.posture_dtau (argmax head, chosen at the first decision and again once
        ``every`` game ticks passed, held in between) with this pilot as the one match -> the dtau in force."""
        from .e1_eval import posture_dtau
        tick = int(frame['game_tick'])
        if getattr(self, '_posture', None) is not None and tick < self._posture[1]:
            self.reset_posture()                        # the game clock went backwards: a new match without reset_match
        self._cur, self._ctx_frame = (tick,), frame
        return float(posture_dtau([self], {'g': g}, {'posture': self.posture})[0])

    def _ctx_row(self, tick):
        """e1_eval.ctx_row (= SIM Match._ctx_row) on this decision's RAW reader frame, my side's view: the public
        bodies (catalogued card ids only: SIM never names a body by a number) and the crown towers."""
        from .e1_eval import ctx_row
        from .live_mem import deck_of, to_observe
        from .reader_identity_aliases import dedupe_hero_bodies
        f = dedupe_hero_bodies(self._ctx_frame)
        side = my_side_of(f)
        state = to_observe(f, side, deck_of(f, side)[1])
        state['entities'] = [e for e in state['entities'] if int(e['card_id']) >= 0 and not str(e['name']).isdigit()]
        return ctx_row(state, side, tick, self.__dict__.setdefault('_ctx_seen', set()))

    def reset_match(self):
        super().reset_match()
        self.match_index += 1
        self.match_seed = int(np.random.SeedSequence([self.decision_seed, self.match_index]).generate_state(1)[0])
        self.rng_decisions = np.random.default_rng(self.match_seed)
        if getattr(self, "gate_sample", 0.0) > 0:                # its own per-match stream: rng_decisions' draws stay as without it
            self.gate_seed = int(np.random.SeedSequence([self.decision_seed, self.match_index, 0x6A7E]).generate_state(1)[0])
            self.rng_gate = np.random.default_rng(self.gate_seed)
            self._gate_prev = None
        self._public_audit_snapshot = None
        self._hazard_prev = None
        self._threat_state = None
        self._princess_dead_state = None
        self._lethal_hp_hist = None
        self._tau_threat_state = None
        self.rv_hist, self.rv_threat_state, self.rv_threatened = None, None, False   # rocket_value: lead history / tower-fire state
        self.reset_posture()

    def row(self, frame):
        b, info = super().row(frame)
        if getattr(self, 'public_audit', False):
            from .public_decision_audit import snapshot
            self._public_audit_snapshot = snapshot(frame, b, info, self)
        return b, info

    def _audited(self, decision):
        if getattr(self, 'public_audit', False):
            decision['public_audit'] = self._public_audit_snapshot
        if getattr(self, 'cue_log', None) is not None:   # step c (--cue-inputs on, cue model): this row's cue summary
            decision['cue'] = self.cue_log
        if getattr(self, 'posture', None) and getattr(self, '_posture', None) is not None:   # C1: the posture in force
            decision.update(posture=self._posture[0], posture_dtau=float(self.posture['dtau'][self._posture[0]]),
                            posture_new=self._posture_new is not None)
        return decision

    def _lethal_snapshot(self, frame, towers=None, side=None, names=None):
        """lethal_log: this decision's public enemy-princess HP into the per-match history (one entry per game tick),
        taken on EVERY decision, affordable or not, as SIM match_kwargs. -> the history."""
        tick = int(frame['game_tick'])
        if towers is None:
            from .live_mem import to_observe
            side = my_side_of(frame)
            towers = to_observe(frame, side, names)['episode']['crown_towers']
        self._lethal_hp_hist = record_hp(getattr(self, '_lethal_hp_hist', None), tick, enemy_princess_hps(towers, side))
        return self._lethal_hp_hist

    def _lethal_context(self, frame, info):
        """The finisher's per-row context for decision_options.decide: (raw crown towers, my side, a play pending, my
        plays in flight (lethal_log), the princesses something else is hitting (lethal_quiet)). The raw frame's absolute
        tower HP (public); live_play never decides with a card pending."""
        options = self.decision_options
        from .live_mem import to_observe
        side = my_side_of(frame)
        towers = to_observe(frame, side, info['names'])['episode']['crown_towers']
        own, skip = None, ()
        if getattr(options, 'lethal_log', 'off') == 'on' or getattr(options, 'lethal_quiet', 0.0) > 0:
            hist = self._lethal_snapshot(frame, towers, side)   # + the public tower HP each spell landed on
            if getattr(options, 'lethal_quiet', 0.0) > 0:       # owner 10-25: a princess something else is hitting: no finisher
                skip = recently_hit(hist, hist[-1][0], round(options.lethal_quiet / 0.05))
        if getattr(options, 'lethal_log', 'off') == 'on':   # my confirmed plays (card, model xy, landing t): in flight
            key = {v: k for k, v in getattr(self, 'gid', {}).items()}
            own = [(key.get(c), x, y, t, hp_after(hist, round(t / 0.05))) for c, f, x, y, t in getattr(self, 'past', [])[-8:]]
        return towers, side, bool(info.get('pending')), own, skip   # --pipeline-decisions: never fires with a play pending

    def lethal_rocket(self, frame, info, allowed):
        """decision_options.lethal_rocket_choice on the live frame (the decision board's time bs.t_sec, as tau_phase)."""
        if getattr(self.decision_options, 'lethal_rocket', 'off') == 'off':
            return None
        towers, side, pending, own, skip = self._lethal_context(frame, info)
        names = [info['names'][di] if di >= 0 else None for di in info['hand_deck_indices']]
        return lethal_rocket_choice(self.decision_options, info['bs'].t_sec, names, allowed, towers, side, self.grid,
                                    own=own, pending=pending, skip=skip)

    def _policy_forward(self, b):
        """ONE trunk pass per decision -> (the policy heads + g, cell(card, form) -> [1, N_CELLS] logits from that same
        encoding). A plain GenModel forward is exactly encode_gen -> heads_gen (+ cell_logits_gen), so this is
        bit-identical to calling the model twice (S1 SPEED.md a1: the second pass was ~85% of a live decide); any other
        model (an overridden forward, a test stub) keeps the two calls."""
        from .model_gen import GenModel
        m = self.model
        if isinstance(m, GenModel) and type(m).forward is GenModel.forward:
            enc = m.encode_gen(b)
            out = m.heads_gen(enc, b)
            out['g'] = enc['g']
            return out, lambda card, form: m.cell_logits_gen(enc, card, form)
        return m(b), lambda card, form: m(b, card=card, form=form)['cell']

    @torch.no_grad()
    def decide(self, frame):
        """decision_options.decide (plan1026 P1: the ONE decision of SIM eval, rollouts and live) on this reader frame:
        this method only builds the row's context and the live decision dict (+ its log-only tags)."""
        options = self.decision_options
        if not options.active:
            return self._audited(super().decide(frame))
        b, info = self.row(frame)
        lookahead = ({'public_lookahead_counts': info['public_lookahead_counts']}
                     if 'public_lookahead_counts' in info else {})
        if "mem_summary" in b:                           # memory v2 (S1c): the frozen lock head's P(lock), logged only
            from .match_memory import S, S1C_FIELDS, S_V2   # (live_gen.decide does the same; this path had dropped it)
            if b["mem_summary"].shape[-1] == S_V2:
                lookahead["xb_lock_p"] = round(float(b["mem_summary"][0, S + S1C_FIELDS.index("xb_lock_p")]), 4)
        out, cell_head = self._policy_forward(b)
        if getattr(self, 'ability', None) is not None:   # live_play --iw-press head (B6): this decision's trunk g
            self.last_g = (int(frame['game_tick']), out['g'])
        p = float(torch.sigmoid(out['gate'][0]))
        # C1: every decision, affordable or not (SIM posture_live runs before the decide): ctx seen-set + choice clock
        dtau = self._posture_dtau(frame, out['g']) if getattr(self, 'posture', None) else None
        stalled = self.stalled(frame, info['el_int'])
        allowed = allowed_slots(np.array([h[0] > 0 for h in info['hand']]), info['costs'],
                                info.get('el_afford', info['el_int']))     # --afford-ticks; default = el_int
        hazard_on = options.gate_decode != 'threshold'  # off: the frame / pilot state are not even read
        threatened = step = None
        if hazard_on:
            tick = int(frame['game_tick'])              # the reader's game clock; a frame without it raises
            step = hazard_step_s(getattr(self, '_hazard_prev', None), tick)
            if threat_on(options):                      # every decision (as SIM match_kwargs), affordable or not
                self._threat_state, threatened = tower_threat(options, getattr(self, '_threat_state', None),
                                                              info['bs'])
        if options.rocket_dead_target != 'allow':        # every decision (as SIM match_kwargs): reader-glitch filter
            self._princess_dead_state, self._princess_alive = princess_dead_state(
                getattr(self, '_princess_dead_state', None), info['bs'])
        tau_threat = None
        if options.tau_threatened is not None:          # every decision (as SIM match_kwargs), affordable or not
            self._tau_threat_state, tau_threat = tau_threat_state(getattr(self, '_tau_threat_state', None), info['bs'])
        if getattr(options, 'lethal_rocket', 'off') != 'off' and (getattr(options, 'lethal_log', 'off') == 'on'
                                                                  or getattr(options, 'lethal_quiet', 0.0) > 0):
            self._lethal_snapshot(frame, names=info['names'])  # every decision (as SIM match_kwargs), affordable or not
        bs = info['bs']
        delta = None
        if info.get('pending'):                         # --pipeline-decisions: cfg["pipeline_tau_delta"], only while a play is pending
            delta = float(getattr(self, 'pipeline_tau_delta', 0.0) or 0.0)
        if dtau is not None:                            # C1: SIM decide_batch's tau_delta = (pipeline delta or 0) + dtau
            delta = (delta or 0.0) + dtau
        names = [info['names'][di] if di >= 0 else None for di in info['hand_deck_indices']]
        hand = lambda pos: info['hand'][pos]            # noqa: E731 -- (card, form) at a hand position
        name_at = lambda pos: info['names'][info['hand_deck_indices'][pos]]   # noqa: E731

        def cell_logits(ids, slots):                    # the card-conditioned cell head on THIS decision's encoding
            card, form = hand(slots[0])
            return cell_head(torch.tensor([card], device=self.dev), torch.tensor([form], device=self.dev))
        notes = {}

        def guard(r, pos, logits):                      # the reader guards on a play's logits; their log keys kept
            d = dict(play=True, deck_index=info['hand_deck_indices'][pos], name=name_at(pos))
            logits = self.guard_cells(frame, d, logits)
            notes.clear()
            notes.update((k, v) for k, v in d.items() if k not in ('play', 'deck_index', 'name'))
            return logits

        def first_play(pos, why, cell, **kw):           # a rule's play dict
            card, form = hand(pos)
            return dict(play=True, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled, why=why, **kw,
                        deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs, name=name_at(pos),
                        xy=cell_xy(cell, self.grid), **lookahead)
        combo = {}

        def follow_up(r, first, second, cell, after, within, order, value):   # the pipelined second tap (plan_follow_up)
            combo['d'] = first_play(first, 'rocket_tornado', cell, rocket_value=round(value, 3))
            return self.plan_follow_up(frame, combo['d'], 'Tornado' if order == 'rocket' else 'Rocket', combo['d']['xy'],
                                       after_ticks=after, within_ticks=within)

        def kills_king():                               # as SIM match_kwargs: the raw king HP (a Rocket row only)
            from .live_mem import to_observe
            side = my_side_of(frame)
            towers = to_observe(frame, side, info['names'])['episode']['crown_towers']
            return (rocket_kills_king(towers, side, dict(options.card_levels)) if options.card_levels
                    else rocket_kills_king(towers, side))

        def log_air_row():                              # the raw bodies: an egg is ground whatever class it wears
            from .live_mem import to_observe
            side = my_side_of(frame)
            return log_air_board(bs, log_air_ground_child_tiles(to_observe(frame, side, info['names'])['entities'], side))
        ctx = dict(grid=self.grid, tau_threat=None if tau_threat is None else [tau_threat],
                   tau_delta=None if delta is None else [delta])
        if options.tau_phase is not None or getattr(options, 'lethal_rocket', 'off') != 'off':
            ctx['t_sec'] = [bs.t_sec]                   # the board the model sees (tick + extrapolation), as SIM
        if options.xbow_class != 'argmax' or options.xbow_dead_lane != 'allow' or options.rocket_dead_target != 'allow':
            ctx['enemy_alive'] = [tuple(bool(t.alive) for t in bs.towers[3:6])]   # enemy K, L, R alive, my board frame
        if hazard_on:
            ctx.update(step_s=[step], elixir=[bs.my_elixir], enemy_units=[enemy_unit_count(bs)], threatened=[threatened])
        if getattr(options, 'lethal_rocket', 'off') != 'off':
            ctx['lethal'] = [self._lethal_context(frame, info) if allowed.any() else None]
        if options.rocket_value > 0:                    # called at EVERY decision (the lead history), as SIM
            ctx['rocket_value'] = [(bs, False, self)]
        if options.rocket_dead_target != 'allow':       # glitch-filtered towers, the model board's bodies, the raw king HP
            ctx['rocket_boards'] = _Lazy(lambda: (self._princess_alive, enemy_body_tiles(bs), kills_king()))
        if options.uses_barrels:                        # the model's own projectile tokens, as SIM's match_kwargs
            ctx.update(projectiles=[b['projectiles'][0]], barrel_id=self.gid.get(BARREL_KEY))
        if getattr(options, 'barrel_lane', 'off') == 'on':   # owner 10-25: goblins on my half, as SIM's match_kwargs
            ctx['barrel_goblins'] = [barrel_goblin_tiles(bs)]
        if options.log_air != 'off':                    # the decision board's enemy units / towers (a Log row only)
            ctx['log_air_boards'] = _Lazy(log_air_row)
        trace = []
        gs = getattr(self, "gate_sample", 0.0)    # (a GenPilot built without __init__, e.g. tests: off)
        if gs > 0:                      # the gate logit + this match's gate stream (decide's gate_sample)
            if self.rng_gate is None:
                raise ValueError('gate_sample: reset_match() before the first decision (the per-match gate seed)')
            ctx.update(gate_sample=gs, gate_rngs=[self.rng_gate])
            if getattr(self, 'gate_sample_step_ticks', 0):   # per unit of time: k from this match's previous decision
                from .decision_options import gate_step
                ctx['gate_steps'] = [gate_step(getattr(self, '_gate_prev', None), int(frame['game_tick']),
                                               self.gate_sample_step_ticks)]
        res = decide({'card': out['card'], **({'gate': out['gate']} if gs > 0 else {})}, [p],
                     allowed[None], np.array([bool(stalled)]), tau=self.gate_tau,
                     options=options, rngs=[self.rng_decisions], cell_logits=cell_logits, card_names=[names],
                     cell_guard=guard, follow_up=follow_up, trace=trace, choose=choose_cells, **ctx)[0]
        tr = trace[0]
        self.last_gate_draw = tr.get('gate_sample')     # live_play logs it ('gate_draw' events); None = no draw
        if getattr(self, 'gate_sample_step_ticks', 0):
            self._gate_prev = (int(frame['game_tick']), self.last_gate_draw is not None and not self.last_gate_draw['fire'])
        if not allowed.any():
            if hazard_on:
                self._hazard_prev = (tick, False)
            return self._audited(dict(play=False, no_affordable=True, p_play=p, hand_pos=-1, deck_index=-1, card=0,
                        form=FORM_PAD, bs=bs, name=None, el_int=info['el_int'], stalled=stalled, **lookahead))
        pos = res['slot']
        card, form = hand(pos)
        d = dict(play=res['play'] and card > 0, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled,
                 deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs,
                 name=name_at(pos) if card > 0 else None, **lookahead)
        rule = tr.get('rule')
        if rule in ('lethal_rocket', 'lethal_log'):
            d = first_play(pos, rule, res['cell'], lethal_rocket=tr['target'])
        elif rule == 'rocket_value':
            d = first_play(pos, 'rocket_value', res['cell'], rocket_value=round(tr['value'], 3))
            d.update(notes)
        elif rule == 'rocket_tornado':
            d = combo['d']
            d.update(follow_ups=res['follow_ups'], rocket_tornado_window=tuple(tr['window']))
            if tr['order'] != 'rocket':
                d['rocket_tornado_order'] = tr['order']
        if options.tau_phase is not None or options.tau_threatened is not None:
            d['gate_tau'] = tr['tau']
        if tau_threat is not None:
            d['tau_threat'] = tau_threat
        if rule is not None:                            # a rule played: no hazard accrues over its landing
            if hazard_on:
                d.update(hazard_step_s=step, hazard_play=False)
                self._hazard_prev = (tick, False)
            return self._audited(d)
        if hazard_on:
            d.update(hazard_step_s=step, hazard_play=bool(tr['hazard'] and d['play']))
            if threatened is not None:
                d['threatened'] = threatened
            self._hazard_prev = (tick, not d['play'])
        if tr.get('dropped'):                           # the block that left an X-Bow / Rocket no cell
            d['why'] = tr['dropped']
        if card <= 0:
            return self._audited(d)
        if 'blocked_cell' in tr:                        # log_air block: WAIT (live log: the Log's plain aim)
            d.update(notes, why='log_air', xy=cell_xy(tr['blocked_cell'], self.grid))
            return self._audited(d)
        if not d['play']:                               # a WAIT's logged xy: the plain argmax aim, no RNG
            d['xy'] = cell_xy(tr['wait_cell'], self.grid)
            return self._audited(d)
        d.update(notes)
        cell, logits = res['cell'], tr['logits']
        if tr.get('moved'):
            d['why'] = 'log_air'                        # live log only: this Log was re-aimed by log_air
        if options.xbow_dead_lane == 'block' and is_xbow(d['name']) and xbow_dead_lane_cells(
                ctx['enemy_alive'][0], self.grid)[int(logits.reshape(-1).argmax())]:
            d['why'] = 'xbow_dead_lane'                 # the model's top X-Bow cell was blocked (live log only)
        if options.rocket_dead_target == 'block' and str(d['name']).lower() == 'rocket':   # live log only, no RNG
            plain = {k: ctx[k] for k in ('grid', 'enemy_alive', 'barrel_goblins') if k in ctx}
            if options.uses_barrels:
                plain['barrels'] = [barrel_landings(ctx['projectiles'][0], ctx['barrel_id'])]
            if cell != int(choose_cells(logits, [d['name']], replace(options, rocket_dead_target='allow'),
                                        rngs=[self.rng_decisions], **plain)[0]):
                d['why'] = 'rocket_dead_target'         # the usual Rocket aim was blocked and re-aimed
            elif ctx['rocket_boards'][0][2] and rocket_covers_king(cell, self.grid):
                d['why'] = 'rocket_king_lethal'         # the explicit never-the-king exception: this Rocket finishes it
        d['xy'] = cell_xy(cell, self.grid)
        return self._audited(d)


class _Lazy:
    """A one-row context list whose element is built on first use (decide reads it only for a Rocket / Log row)."""

    def __init__(self, build):
        self.build, self.value = build, None

    def __getitem__(self, i):
        if i != 0:
            raise IndexError(i)
        if self.value is None:
            self.value = self.build()
        return self.value
