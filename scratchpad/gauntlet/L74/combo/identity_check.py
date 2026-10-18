"""L74 combo (10-17): BEFORE/AFTER proof that the new combo options leave the old rule byte-identical when they are off.
HEAD's pipeline/decision_options.py (git show) is loaded as a second module next to the working tree's; both decide the same random
boards under the old option sets (defaults, the deployed live combo stack, 'on' mode, min_y 21, lead drift, river on/off) and every
output must be EQUAL (cells, slots, values to the bit, eligible masks, decision dicts incl. follow_ups).
    PYTHONPATH=. python scratchpad/gauntlet/L74/combo/identity_check.py [N_BOARDS] [REV]"""
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch

from pipeline import decision_options as NEW
from pipeline import vocab
from pipeline.obs_contract import Tower, Unit

N = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
REV = sys.argv[2] if len(sys.argv) > 2 else 'HEAD'
src = subprocess.run(['git', 'show', f'{REV}:pipeline/decision_options.py'], capture_output=True, check=True).stdout
tmp = Path(tempfile.mkdtemp()) / 'decision_options_head.py'
tmp.write_bytes(src)
spec = importlib.util.spec_from_file_location('pipeline._decision_options_head', tmp)
OLD = importlib.util.module_from_spec(spec)
OLD.__package__ = 'pipeline'
sys.modules[spec.name] = OLD
spec.loader.exec_module(OLD)

KINDS = ['knight', 'wizard', 'musketeer', 'giant', 'minions', 'skeletons', 'lava_pups', 'mega_knight', 'ram_rider', 'tesla', 'goblins',
         'baby_dragon', 'valkyrie', 'hog_rider', 'tombstone', 'archers', 'golem', 'balloon']
DECK = ['knight', 'rocket', 'the-log', 'tornado', 'x-bow', 'ice-wizard', 'skeletons', 'tesla']
BASE = dict(rocket_value=9.0, rocket_value_mode='damage', rocket_value_hitbox='edge')
SETS = {'lone': dict(BASE), 'live': dict(BASE, rocket_tornado='only', tornado_river='on'), 'on': dict(BASE, rocket_tornado='on'),
        'on_cost': dict(rocket_value=7.0, rocket_tornado='on'), 'miny21': dict(BASE, rocket_tornado='on', rocket_value_min_y=21.0),
        'drift': dict(BASE, rocket_tornado='only', rocket_value_lead='drift'), 'rocket_only': dict(BASE, rocket_tornado='rocket_only'),
        'off': {}}


class Model:
    def cell_logits(self, enc, slot):
        g = torch.Generator().manual_seed(int(enc['g'][0, 0]) * 7 + int(slot[0]))
        return torch.randn(len(slot), 2304, generator=g)


def towers(rng):
    a = rng.random(6) > 0.15
    return tuple(Tower(int(i >= 3), 'king' if i % 3 == 0 else 'princess', None if i % 3 == 0 else 'LR'[i % 3 - 1],
                       float(rng.uniform(.2, 1)), bool(a[i]) or i % 3 == 0) for i in range(6))


def random_board(rng):
    units = []
    for _ in range(int(rng.integers(0, 11))):
        k = KINDS[int(rng.integers(len(KINDS)))]
        x, y = rng.uniform(0.3, 17.7), rng.choice([rng.uniform(12, 31), rng.uniform(1, 31)])
        n = int(rng.integers(1, 4)) if k in ('skeletons', 'goblins', 'minions', 'lava_pups', 'archers') else 1
        for j in range(n):
            units.append(Unit(vocab.unit_id(k), int(rng.random() > .05), (x + .3 * j) / 18.0, (y + .2 * j) / 32.0,
                              None if rng.random() < .1 else float(rng.uniform(.1, 1)), None, None, 1.0))
    hand = rng.permutation([vocab.unit_id(c) for c in ('rocket', 'tornado', 'knight', 'the_log', 'x_bow', 'skeletons')])[:4]
    bs = SimpleNamespace(units=tuple(units), t_sec=float(rng.uniform(5, 200)), my_elixir=float(rng.uniform(4, 10)), towers=towers(rng),
                         double_elixir=bool(rng.random() < .3), overtime=bool(rng.random() < .1), my_hand=tuple(int(h) for h in hand))
    return bs


def same(a, b):
    if isinstance(a, np.ndarray) or isinstance(b, np.ndarray):
        return isinstance(a, np.ndarray) and isinstance(b, np.ndarray) and a.shape == b.shape and bool((a == b).all())
    if isinstance(a, (tuple, list)) and isinstance(b, (tuple, list)):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    return a == b and type(a) is type(b) or (isinstance(a, float) and isinstance(b, float) and np.isnan(a) and np.isnan(b))


rng = np.random.default_rng(20261017)
counts = {k: 0 for k in ('boards', 'clump', 'centre', 'lone_fire', 'combo_fire', 'decide', 'combo_decide')}
for i in range(N):
    bs = random_board(rng)
    allowed = rng.random(8) > .2
    for mode in ('cost', 'damage', 'kill'):
        b_old, b_new = OLD.rocket_bodies(bs, mode), NEW.rocket_bodies(bs, mode)
        assert same(b_old, b_new), ('bodies', i)
        for hb in ('centre', 'edge'):
            for min_y in (16.0, 21.0):
                o = OLD.best_rocket_clump(b_old, 'lattice', hb, None, min_y, True)
                n = NEW.best_rocket_clump(b_new, 'lattice', hb, None, min_y, True)
                assert same(o, n), ('clump', i, mode, hb, min_y)
                counts['clump'] += o[1] is not None
                for river in (False, True):
                    o = OLD.best_tornado_centre(b_old, 'lattice', hb, min_y, river=river)
                    n = NEW.best_tornado_centre(b_new, 'lattice', hb, min_y, river=river)
                    assert same(o, n), ('centre', i, mode, hb, min_y, river)
                    counts['centre'] += o[1] is not None
    for name, kw in SETS.items():
        opt_o, opt_n = OLD.DecisionOptions(**kw), NEW.DecisionOptions(**kw)
        if kw:
            ho, hn = SimpleNamespace(), SimpleNamespace()
            o = OLD.rocket_value_choice(opt_o, DECK, allowed, bs, 'lattice', holder=ho)
            n = NEW.rocket_value_choice(opt_n, DECK, allowed, bs, 'lattice', holder=hn)
            assert same(o, n), ('lone', name, i)
            counts['lone_fire'] += o is not None
            for pending in (False, True):
                o = OLD.rocket_tornado_choice(opt_o, DECK, allowed, bs, 'lattice', pending)
                n = NEW.rocket_tornado_choice(opt_n, DECK, allowed, bs, 'lattice', pending)
                assert (o is None and n is None) or (n is not None and same(tuple(o), tuple(n[:5])) and n[5] == 'rocket'), \
                    ('combo', name, i, o, n)
                counts['combo_fire'] += o is not None
        a = dict(enc={'g': torch.full((1, 2), float(i))}, heads={'card': torch.tensor([rng.normal(size=8)], dtype=torch.float32)},
                 p=np.array([rng.random()]), allowed=allowed[None].copy(), stalled=np.zeros(1, bool))
        kws = dict(tau=.35, device='cpu', rngs=[None], card_names=[DECK], grid='lattice')
        if kw:
            kws['rocket_value'] = None
        if opt_o.active:
            do = OLD.decide_batch(Model(), **a, options=opt_o, **dict(kws, rocket_value=[(bs, False, SimpleNamespace())]) if kw else kws)
            dn = NEW.decide_batch(Model(), **a, options=opt_n, **dict(kws, rocket_value=[(bs, False, SimpleNamespace())]) if kw else kws)
            assert same(do, dn), ('decide', name, i, do, dn)
            counts['decide'] += 1
            counts['combo_decide'] += do[0].get('why') == 'rocket_tornado'
    counts['boards'] += 1
print('IDENTICAL on every output:', counts)
