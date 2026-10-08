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

from .decision_options import BARREL_KEY, DecisionOptions, barrel_landings, choose_cells, choose_slot, gate_taus
from .decision_options import lethal_rocket_choice
from .live_mem import my_side_of


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

    def reset_match(self):
        super().reset_match()
        self.match_index += 1
        self.match_seed = int(np.random.SeedSequence([self.decision_seed, self.match_index]).generate_state(1)[0])
        self.rng_decisions = np.random.default_rng(self.match_seed)
        self._public_audit_snapshot = None

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
        return lethal_rocket_choice(options, info['bs'].t_sec, names, allowed, towers, side, self.grid)

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
        if not allowed.any():
            return self._audited(dict(play=False, no_affordable=True, p_play=p, hand_pos=-1, deck_index=-1, card=0,
                        form=FORM_PAD, bs=info['bs'], name=None, el_int=info['el_int'], stalled=stalled,
                        **lookahead))
        # tau_phase: the gate threshold of the phase of the board the model sees (bs.t_sec, tick + extrapolation),
        # as SIM's match_kwargs reads it from the prepared (extrapolated) BoardState.
        bs = info['bs']
        tau = (float(gate_taus(options, self.gate_tau, [bs.t_sec], 1)[0]) if options.tau_phase is not None
               else self.gate_tau)
        playing = p > tau or stalled                    # SIM decide_batch: (p > tau) | stalled
        lethal = self.lethal_rocket(frame, info, allowed)
        if lethal is not None:                          # SIM decide_batch: the same rule overrides gate, card and cell
            pos, cell, target = lethal
            card, form = info['hand'][pos]
            d = dict(play=True, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled, why='lethal_rocket',
                     lethal_rocket=target, deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs,
                     name=info['names'][info['hand_deck_indices'][pos]], xy=cell_xy(cell, self.grid), **lookahead)
            if options.tau_phase is not None:
                d['gate_tau'] = tau
            return self._audited(d)
        pos = choose_slot(out['card'][0], allowed, options, self.rng_decisions, playing=playing)
        card, form = info['hand'][pos]
        name = info['names'][info['hand_deck_indices'][pos]] if card > 0 else None
        d = dict(play=playing and card > 0, p_play=p, hand_pos=pos, no_affordable=False, stalled=stalled,
                 deck_index=info['hand_deck_indices'][pos], card=card, form=form, bs=bs, name=name, **lookahead)
        if options.tau_phase is not None:
            d['gate_tau'] = tau
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
