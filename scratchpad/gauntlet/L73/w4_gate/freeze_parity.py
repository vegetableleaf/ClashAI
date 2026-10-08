"""W4 live-wiring parity: the logged decision stream of a live match driven through the WIRED live decision code
(live_gen_v2.GenPilot.decide, the pilot live_play.py loads) with --gate-decode hazard_below_tau
--gate-hazard-min-elixir 9 (+ the deployed tau_phase). Offline, from the recorded log only.

The log does not hold full reader frames (no hand / deck block), so the pilot's row() is replaced by the logged public
record of each decision (own hand + costs, model elixir, model tick, enemy bodies) and the model by the logged p_play
and the logged card argmax; everything after that -- the step rule, the scope, the hazard draw, the RNG, the play
flag -- is the live code.
  python freeze_parity.py <live_play_*.jsonl> T0 T1 [N]"""
import json, os, sys
from types import SimpleNamespace

import numpy as np
import torch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../..")))
from pipeline import live_gen_v2                                     # noqa: E402
from pipeline.decision_options import DecisionOptions               # noqa: E402

OPTS = DecisionOptions(tau_phase=(.35, .45, .55), gate_decode='hazard_below_tau', gate_hazard_min_elixir=9.0)


class Logged:
    """Model stub: gate = the logged p_play; card head = the logged argmax hand position; flat cell logits."""
    def __init__(self):
        self.p, self.pos = .0, 0

    def __call__(self, b, card=None, form=None):
        if card is not None:
            return {'cell': torch.zeros(1, 2304)}
        logits = torch.full((1, 4), -9.0); logits[0, self.pos] = 9.0
        return {'gate': torch.logit(torch.tensor([self.p], dtype=torch.float64)).float(), 'card': logits}


class ReplayPilot(live_gen_v2.GenPilot):
    def row(self, frame):
        return None, frame['_info']

    def guard_cells(self, frame, d, logits):
        return logits


def records(path, t0, t1):
    out = []
    for line in open(path):
        d = json.loads(line)
        if d.get('event') != 'decision':
            continue
        out.append(d)
    keep = [d for d in out if t0 <= d['tick'] <= t1]
    prev = [d for d in out if d['tick'] < t0]
    return ([prev[-1]] if prev else []) + keep            # one earlier decision: the first in-window step is a real one


def info_of(d):
    pub, dc = d['public'], d['decision']
    hand = pub['own_hand']; me = pub['observer_side']
    names = [''] * 8
    for h in hand:
        names[h['deck_index']] = h['name']
    enemy = [SimpleNamespace(side=1) for b in pub.get('raw_bodies', []) if b['side'] != me and b['card_id'] != -1]
    bs = SimpleNamespace(t_sec=pub['model_tick'] * 0.05, my_elixir=pub['model_own_elixir'], units=enemy, towers=[])
    el = pub['model_own_elixir']
    return dict(hand=[(h['card'], h['form']) for h in hand], costs=[h['cost'] for h in hand], el_int=int(el),
                names=names, hand_deck_indices=[h['deck_index'] for h in hand], bs=bs)


def run(path, t0, t1, n):
    R = records(path, t0, t1)
    frames = [dict(game_tick=d['tick'], _info=info_of(d)) for d in R]
    first, cards = [], {}
    for seed in range(n):
        p = object.__new__(ReplayPilot)
        p.model, p.dev, p.grid, p.gate_tau, p.public_audit = Logged(), torch.device('cpu'), 'lattice', .35, False
        p.decision_options, p.rng_decisions, p._hazard_prev = OPTS, np.random.default_rng(seed), None
        p.last_play_tick = None
        hit = None
        for d, f in zip(R, frames):
            p.model.p, p.model.pos = float(d['decision']['p_play']), max(int(d['decision'].get('hand_pos', 0)), 0)
            out = p.decide(f)
            if out['play'] and d['tick'] >= t0:
                hit = (d['tick'], out['name'], out.get('hazard_play')); break
        first.append((hit[0] - t0) / 20 if hit else np.inf)
        if hit:
            cards[hit[1]] = cards.get(hit[1], 0) + 1
            assert hit[2], 'every play in this window must be a hazard play (the logged p never crossed tau)'
    first = np.array(first)
    print(f"{len(R)} decisions, {n} runs; WIRED live hazard_below_tau min-elixir 9 from tick {t0}: "
          f"P(play) within 5 s {np.mean(first <= 5):.3f}, 10 s {np.mean(first <= 10):.3f}, 20 s {np.mean(first <= 20):.3f}, "
          f"ever {np.mean(np.isfinite(first)):.3f}; median {np.median(first):.1f} s")
    print("card:", {k: round(v / n, 3) for k, v in sorted(cards.items(), key=lambda kv: -kv[1])})


if __name__ == '__main__':
    run(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else 3000)
