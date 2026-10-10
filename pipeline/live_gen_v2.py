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

from .decision_options import (BARREL_KEY, DecisionOptions, barrel_landings, choose_cells, choose_slot, enemy_unit_count,
                               gate_taus, hazard_draw, is_xbow, lethal_rocket_choice, tau_threat_state,
                               threat_on, threat_taus, tower_threat, xbow_dead_lane_cells, enemy_body_tiles,
                               princess_dead_state, rocket_covers_king, rocket_kills_king, log_air_board, LOG_AIR_BLOCKED,
                               log_air_ground_child_tiles, is_log)
from .decision_options import rocket_tornado_choice, rocket_tornado_timing, rocket_value_cell, rocket_value_choice
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
    def __init__(self, *args, decision_options=None, decision_seed=0, public_audit=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.decision_options = decision_options or DecisionOptions()
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

    def reset_match(self):
        super().reset_match()
        self.match_index += 1
        self.match_seed = int(np.random.SeedSequence([self.decision_seed, self.match_index]).generate_state(1)[0])
        self.rng_decisions = np.random.default_rng(self.match_seed)
        self._public_audit_snapshot = None
        self._hazard_prev = None
        self._threat_state = None
        self._princess_dead_state = None
        self._lethal_hp_hist = None
        self._tau_threat_state = None
        self.rv_hist, self.rv_threat_state, self.rv_threatened = None, None, False   # rocket_value: lead history / tower-fire state

    def row(self, frame):
        b, info = super().row(frame)
        if getattr(self, 'public_audit', False):
            from .public_decision_audit import snapshot
            self._public_audit_snapshot = snapshot(frame, b, info, self)
        return b, info

    def _audited(self, decision):
        if getattr(self, 'public_audit', False):
            decision['public_audit'] = self._public_audit_snapshot
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

    def lethal_rocket(self, frame, info, allowed):
        """decision_options.lethal_rocket_choice on the live frame: the decision board's time (bs.t_sec, as tau_phase),
        the raw frame's absolute tower HP (public), my hand by position. live_play never decides with a card pending."""
        options = self.decision_options
        if getattr(options, 'lethal_rocket', 'off') == 'off':
            return None
        from .live_mem import to_observe
        side = my_side_of(frame)
        towers = to_observe(frame, side, info['names'])['episode']['crown_towers']
        names = [info['names'][di] if di >= 0 else None for di in info['hand_deck_indices']]
        own = None
        if getattr(options, 'lethal_log', 'off') == 'on':   # my confirmed plays (card, model xy, landing t): in flight
            hist = self._lethal_snapshot(frame, towers, side)   # + the public tower HP each spell landed on
            key = {v: k for k, v in getattr(self, 'gid', {}).items()}
            own = [(key.get(c), x, y, t, hp_after(hist, round(t / 0.05))) for c, f, x, y, t in getattr(self, 'past', [])[-8:]]
        return lethal_rocket_choice(options, info['bs'].t_sec, names, allowed, towers, side, self.grid, own=own,
                                    pending=bool(info.get('pending')))   # --pipeline-decisions: never fires with a play pending

    def rocket_value(self, info, allowed, playing=False):
        """decision_options.rocket_value_choice on the live board (info['bs']: the reader's bodies with hp_frac; live_play never
        decides with a card pending) -> (hand position, eligible cells, value) or None. Called at EVERY decision when on (the
        lead history), as SIM decide_batch."""
        options = self.decision_options
        if getattr(options, 'rocket_value', 0.0) <= 0:
            return None
        names = [info['names'][di] if di >= 0 else None for di in info['hand_deck_indices']]
        hit = rocket_value_choice(options, names, allowed, info['bs'], self.grid, holder=self, playing=bool(playing))
        return None if options.rocket_tornado == 'only' else hit      # 'only': the combo without the lone rule (state still kept above)

    def rocket_tornado(self, info, allowed, playing=False):
        """decision_options.rocket_tornado_choice on the live board -> (Rocket hand position, cell, (earliest, latest), value) or None.
        The lone rule has priority (the caller asks it first); idle / threat gates as the lone rule (threat from the state it kept)."""
        options = self.decision_options
        if options.rocket_tornado == 'off' or (options.rocket_value_idle == 'on' and playing):
            return None
        if options.rocket_value_threat == 'on' and not getattr(self, 'rv_threatened', False):
            return None
        names = [info['names'][di] if di >= 0 else None for di in info['hand_deck_indices']]
        hit = rocket_tornado_choice(options, names, allowed, info['bs'], self.grid)
        return None if hit is None else (hit[0], hit[2], hit[3], hit[4])

    @torch.no_grad()
    def decide(self, frame):
        options = self.decision_options
        if not options.active:
            return self._audited(super().decide(frame))
        b, info = self.row(frame)
        lookahead = ({'public_lookahead_counts': info['public_lookahead_counts']}
                     if 'public_lookahead_counts' in info else {})
        out = self.model(b)
        p = float(torch.sigmoid(out['gate'][0]))
        stalled = self.stalled(frame, info['el_int'])
        allowed = allowed_slots(np.array([h[0] > 0 for h in info['hand']]), info['costs'],
                                info.get('el_afford', info['el_int']))     # --afford-ticks; default = el_int
        hazard_on = options.gate_decode != 'threshold'  # off: the frame / pilot state are not even read
        if hazard_on:
            tick = int(frame['game_tick'])              # the reader's game clock; a frame without it raises
            step = hazard_step_s(getattr(self, '_hazard_prev', None), tick)
            threatened = None
            if threat_on(options):                      # every decision (as SIM match_kwargs), affordable or not
                self._threat_state, threatened = tower_threat(options, getattr(self, '_threat_state', None),
                                                              info['bs'])
        if options.rocket_dead_target != 'allow':        # every decision (as SIM match_kwargs): reader-glitch filter
            self._princess_dead_state, self._princess_alive = princess_dead_state(
                getattr(self, '_princess_dead_state', None), info['bs'])
        tau_threat = None
        if options.tau_threatened is not None:          # every decision (as SIM match_kwargs), affordable or not
            self._tau_threat_state, tau_threat = tau_threat_state(getattr(self, '_tau_threat_state', None), info['bs'])
        if getattr(options, 'lethal_rocket', 'off') != 'off' and getattr(options, 'lethal_log', 'off') == 'on':
            self._lethal_snapshot(frame, names=info['names'])  # every decision (as SIM match_kwargs), affordable or not
        if not allowed.any():
            self.rocket_value(info, allowed)        # nothing affordable: only the per-match state the rule keeps (SIM decide_batch sees it too)
            if hazard_on:
                self._hazard_prev = (tick, False)
            return self._audited(dict(play=False, no_affordable=True, p_play=p, hand_pos=-1, deck_index=-1, card=0,
                        form=FORM_PAD, bs=info['bs'], name=None, el_int=info['el_int'], stalled=stalled,
                        **lookahead))
        # tau_phase: the gate threshold of the phase of the board the model sees (bs.t_sec, tick + extrapolation),
        # as SIM's match_kwargs reads it from the prepared (extrapolated) BoardState.
        bs = info['bs']
        tau = (float(gate_taus(options, self.gate_tau, [bs.t_sec], 1)[0]) if options.tau_phase is not None
               else self.gate_tau)
        tau = float(threat_taus(options, tau, tau_threat))   # tau_threatened: X while threatened, else unchanged
        if info.get('pending'):                         # --pipeline-decisions: cfg["pipeline_tau_delta"], only while a play is pending
            tau += float(getattr(self, 'pipeline_tau_delta', 0.0) or 0.0)
        playing = p > tau or stalled                    # SIM decide_batch: (p > tau) | stalled
        hazard = None
        if hazard_on:                                   # SIM decide_batch: the same hazard_draw on the same context
            if options.gate_decode == 'hazard':
                playing = bool(stalled)
            if not playing:
                playing = hazard = hazard_draw(options, p, step, self.rng_decisions, elixir=bs.my_elixir,
                                               enemy_units=enemy_unit_count(bs), threatened=threatened)
        lethal = self.lethal_rocket(frame, info, allowed)
        if lethal is not None:                          # SIM decide_batch: the same rule overrides gate, card and cell
            pos, cell, target = lethal
            card, form = info['hand'][pos]
            why = 'lethal_log' if target.get('card') == 'Log' else 'lethal_rocket'
            d = dict(play=True, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled, why=why,
                     lethal_rocket=target, deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs,
                     name=info['names'][info['hand_deck_indices'][pos]], xy=cell_xy(cell, self.grid), **lookahead)
            if options.tau_phase is not None or options.tau_threatened is not None:
                d['gate_tau'] = tau
            if tau_threat is not None:
                d['tau_threat'] = tau_threat
            if hazard_on:                               # a play was made: no hazard accrues over its landing
                d.update(hazard_step_s=step, hazard_play=False)
                self._hazard_prev = (tick, False)
            return self._audited(d)
        rocket = self.rocket_value(info, allowed, playing)
        if rocket is not None:                          # SIM decide_batch: the same rule, below the lethal rule
            pos, eligible, value = rocket
            card, form = info['hand'][pos]
            d = dict(play=True, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled, why='rocket_value',
                     rocket_value=round(value, 3), deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs,
                     name=info['names'][info['hand_deck_indices'][pos]], **lookahead)
            logits = self.guard_cells(frame, d, self.model(b, card=torch.tensor([card], device=self.dev),
                                                           form=torch.tensor([form], device=self.dev))['cell'])
            d['xy'] = cell_xy(rocket_value_cell(logits, eligible), self.grid)
            if options.tau_phase is not None or options.tau_threatened is not None:
                d['gate_tau'] = tau
            if tau_threat is not None:
                d['tau_threat'] = tau_threat
            if hazard_on:                               # a play was made: no hazard accrues over its landing
                d.update(hazard_step_s=step, hazard_play=False)
                self._hazard_prev = (tick, False)
            return self._audited(d)
        combo = self.rocket_tornado(info, allowed, playing)
        if combo is not None:                           # not in the SIM (decide_batch refuses it): the pipelined second tap is live only
            pos, cell, (lo, hi), value = combo
            card, form = info['hand'][pos]
            xy = cell_xy(cell, self.grid)
            d = dict(play=True, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled, why='rocket_tornado',
                     rocket_value=round(value, 3), deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs,
                     name=info['names'][info['hand_deck_indices'][pos]], xy=xy, **lookahead)
            after, within = rocket_tornado_timing((lo, hi))     # the middle of the window (SIM decide_batch asks for the same timing)
            follow = self.plan_follow_up(frame, d, 'Tornado', xy, after_ticks=after, within_ticks=within)
            if follow is not None:                      # the Tornado left the hand since: no combo, fall through to the model
                d['follow_ups'] = [follow]
                d['rocket_tornado_window'] = (lo, hi)
                if options.tau_phase is not None or options.tau_threatened is not None:
                    d['gate_tau'] = tau
                if tau_threat is not None:
                    d['tau_threat'] = tau_threat
                if hazard_on:
                    d.update(hazard_step_s=step, hazard_play=False)
                    self._hazard_prev = (tick, False)
                return self._audited(d)
        pos = choose_slot(out['card'][0], allowed, options, self.rng_decisions, playing=playing)
        dropped = None                                  # the block that left an X-Bow / Rocket no cell (SIM decide_batch)
        while True:
            card, form = info['hand'][pos]
            name = info['names'][info['hand_deck_indices'][pos]] if card > 0 else None
            d = dict(play=playing and card > 0, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled,
                     deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs, name=name, **lookahead)
            if options.tau_phase is not None or options.tau_threatened is not None:
                d['gate_tau'] = tau
            if tau_threat is not None:
                d['tau_threat'] = tau_threat
            if hazard_on:
                d.update(hazard_step_s=step, hazard_play=bool(hazard and d['play']))
                if threatened is not None:
                    d['threatened'] = threatened
                self._hazard_prev = (tick, not d['play'])
            if dropped:
                d['why'] = dropped
            if card <= 0:
                break
            logits = self.model(b, card=torch.tensor([card], device=self.dev),
                                form=torch.tensor([form], device=self.dev))['cell']
            # SIM aims only playing rows: a WAIT's logged xy keeps the plain X-Bow argmax and draws no RNG.
            cell_options = options if d['play'] else replace(options, xbow_class='argmax', xbow_dead_lane='allow',
                                                             rocket_dead_target='allow', log_air='off')
            context = {}
            if (cell_options.xbow_class != 'argmax' or cell_options.xbow_dead_lane != 'allow'
                    or cell_options.rocket_dead_target != 'allow'):
                # enemy K, L, R alive in my board frame, as SIM's match_kwargs
                context = dict(rngs=[self.rng_decisions], grid=self.grid,
                               enemy_alive=[tuple(bool(t.alive) for t in bs.towers[3:6])])
                if cell_options.rocket_dead_target != 'allow':      # as SIM match_kwargs: glitch-filtered towers,
                    kills_king = False                              # the model board's bodies, the raw king HP
                    if str(name).lower() == 'rocket':
                        from .live_mem import to_observe
                        side = my_side_of(frame)
                        towers = to_observe(frame, side, info['names'])['episode']['crown_towers']
                        kills_king = (rocket_kills_king(towers, side, dict(options.card_levels)) if options.card_levels
                                      else rocket_kills_king(towers, side))
                    context['rocket_boards'] = [(self._princess_alive, enemy_body_tiles(bs), kills_king)]
            if cell_options.uses_barrels:              # the model's own projectile tokens, as SIM's match_kwargs
                context.update(grid=self.grid, barrels=[barrel_landings(b['projectiles'][0], self.gid.get(BARREL_KEY))])
            if cell_options.log_air != 'off' and is_log(name):   # the decision board's enemy units / towers, as SIM's match_kwargs
                from .live_mem import to_observe        # the raw bodies: an egg is ground whatever class it wears
                side = my_side_of(frame)
                context.update(grid=self.grid, log_air_boards=[log_air_board(
                    bs, log_air_ground_child_tiles(to_observe(frame, side, info['names'])['entities'], side))])
            logits = self.guard_cells(frame, d, logits)
            moved = []
            cell = int(choose_cells(logits, [name], cell_options, log_air_moved=moved, **context)[0])
            if moved:
                d['why'] = 'log_air'                    # live log only: this Log was re-aimed (or blocked) by log_air
            if cell == LOG_AIR_BLOCKED:                 # block: WAIT (as SIM decide_batch), never another card
                d['play'] = False
                if hazard_on:
                    d['hazard_play'] = False
                    self._hazard_prev = (tick, True)
                cell = int(choose_cells(logits, [name], replace(cell_options, log_air='off'), **context)[0])
            if cell < 0:                                # SIM decide_batch: next card by the model's ranking, else WAIT
                allowed = allowed.copy()
                dropped = 'xbow_dead_lane' if is_xbow(name) else 'rocket_dead_target'
                allowed[pos] = False
                nxt = choose_slot(out['card'][0], allowed, options, self.rng_decisions, playing=True)
                if nxt < 0:
                    playing = False                     # nothing else affordable: wait (never forced)
                else:
                    pos = nxt
                continue
            if cell_options.xbow_dead_lane == 'block' and is_xbow(name) and xbow_dead_lane_cells(
                    context['enemy_alive'][0], self.grid)[int(logits.reshape(-1).argmax())]:
                d['why'] = 'xbow_dead_lane'             # the model's top X-Bow cell was blocked (live log only)
            if cell_options.rocket_dead_target == 'block' and str(name).lower() == 'rocket':   # live log only, no RNG
                if cell != int(choose_cells(logits, [name], replace(cell_options, rocket_dead_target='allow'),
                                            **context)[0]):
                    d['why'] = 'rocket_dead_target'     # the usual Rocket aim was blocked and re-aimed
                elif kills_king and rocket_covers_king(cell, self.grid):
                    d['why'] = 'rocket_king_lethal'     # the explicit never-the-king exception: this Rocket finishes it
            d['xy'] = cell_xy(cell, self.grid)
            break
        return self._audited(d)
