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
                               gate_taus, hazard_draw)

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


class GenPilot(LegacyGenPilot):
    def __init__(self, *args, decision_options=None, decision_seed=0, public_audit=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.decision_options = decision_options or DecisionOptions()
        if self.decision_options.log_aim != 'argmax' and getattr(self, 'feature_version', 1) < 4:
            raise ValueError('log_aim needs a feature_version >= 4 checkpoint (public projectile tokens)')
        self.decision_seed = int(decision_seed)
        self.match_index = -1
        self.match_seed = self.decision_seed
        self.rng_decisions = np.random.default_rng(self.match_seed)
        self.public_audit = bool(public_audit)
        self._public_audit_snapshot = None
        self._hazard_prev = None                # (game tick, waited with a play possible) of the previous decision

    def reset_match(self):
        super().reset_match()
        self.match_index += 1
        self.match_seed = int(np.random.SeedSequence([self.decision_seed, self.match_index]).generate_state(1)[0])
        self.rng_decisions = np.random.default_rng(self.match_seed)
        self._public_audit_snapshot = None
        self._hazard_prev = None

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
        allowed = allowed_slots(np.array([h[0] > 0 for h in info['hand']]), info['costs'], info['el_int'])
        tick = int(frame['game_tick'])
        step = hazard_step_s(getattr(self, '_hazard_prev', None), tick)
        if not allowed.any():
            self._hazard_prev = (tick, False)
            return self._audited(dict(play=False, no_affordable=True, p_play=p, hand_pos=-1, deck_index=-1, card=0,
                        form=FORM_PAD, bs=info['bs'], name=None, el_int=info['el_int'], stalled=stalled,
                        **lookahead))
        # tau_phase: the gate threshold of the phase of the board the model sees (bs.t_sec, tick + extrapolation),
        # as SIM's match_kwargs reads it from the prepared (extrapolated) BoardState.
        bs = info['bs']
        tau = (float(gate_taus(options, self.gate_tau, [bs.t_sec], 1)[0]) if options.tau_phase is not None
               else self.gate_tau)
        playing = p > tau or stalled                    # SIM decide_batch: (p > tau) | stalled
        hazard = None
        if options.gate_decode != 'threshold':          # SIM decide_batch: the same hazard_draw on the same context
            if options.gate_decode == 'hazard':
                playing = bool(stalled)
            if not playing:
                playing = hazard = hazard_draw(options, p, step, self.rng_decisions, elixir=bs.my_elixir,
                                               enemy_units=enemy_unit_count(bs))
        pos = choose_slot(out['card'][0], allowed, options, self.rng_decisions, playing=playing)
        card, form = info['hand'][pos]
        name = info['names'][info['hand_deck_indices'][pos]] if card > 0 else None
        d = dict(play=playing and card > 0, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled,
                 deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs, name=name, **lookahead)
        if options.tau_phase is not None:
            d['gate_tau'] = tau
        if options.gate_decode != 'threshold':
            d.update(hazard_step_s=step, hazard_play=bool(hazard and d['play']))
        self._hazard_prev = (tick, not d['play'])
        if card > 0:
            logits = self.model(b, card=torch.tensor([card], device=self.dev),
                                form=torch.tensor([form], device=self.dev))['cell']
            # SIM aims only playing rows: a WAIT's logged xy keeps the plain X-Bow argmax and draws no RNG.
            cell_options = options if d['play'] else replace(options, xbow_class='argmax')
            context = {}
            if cell_options.xbow_class != 'argmax':     # enemy K, L, R alive in my board frame, as SIM's match_kwargs
                context = dict(rngs=[self.rng_decisions], grid=self.grid,
                               enemy_alive=[tuple(bool(t.alive) for t in bs.towers[3:6])])
            if cell_options.log_aim != 'argmax':       # the model's own projectile tokens, as SIM's match_kwargs
                context.update(grid=self.grid, barrels=[barrel_landings(b['projectiles'][0], self.gid.get(BARREL_KEY))])
            logits = self.guard_cells(frame, d, logits)
            d['xy'] = cell_xy(int(choose_cells(logits, [name], cell_options, **context)[0]), self.grid)
        return self._audited(d)
