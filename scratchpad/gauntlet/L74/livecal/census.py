"""Weekend mk_weighted_decks.py algorithm, made callable without pipeline imports.

Source: cb_weekend/scratchpad/gauntlet/L74/weekend/{archetypes,mk_weighted_decks}.py.
Only the six owner-named archetypes are boosted (weak_other is not).
"""
import copy
import re
import numpy as np


def unfavorable(names):
    alias = {'assassin': 'bandit', 'ghost': 'royalghost', 'blowdartgoblin': 'dartgoblin'}
    s = {re.sub('[^a-z0-9]', '', n.split('@')[0].lower()) for n in names}
    s = {alias.get(n, n) for n in s}
    bait = {'goblinbarrel', 'skeletonarmy', 'goblingang', 'princess', 'dartgoblin', 'rascals', 'minionhorde', 'bats'}
    tank = {'golem', 'lavahound', 'giant', 'royalgiant', 'pekka', 'electrogiant', 'goblingiant', 'giantskeleton', 'elixirgolem'}
    return bool(s & {'royalgiant', 'lavahound', 'golem'} or
                ('pekka' in s and s & {'bandit', 'battleram', 'royalghost', 'magicarcher'}) or
                (len(s & bait) >= 3 and not s & tank))


def weighted(data):
    data = copy.deepcopy(data)
    if 'weighted_archetypes' in data:
        raise ValueError('input census is already weighted')
    sides = np.array([float(d['sides']) for d in data['decks']])
    mask = np.array([unfavorable(d['engine']) for d in data['decks']])
    if not mask.any() or mask.all() or (sides <= 0).any():
        raise ValueError('census needs positive frequencies and both archetype classes')
    def probs(s):
        w = np.sqrt(s)
        w = np.maximum(w, .5*w.mean())
        return w/w.sum()
    natural = float(probs(sides)[mask].sum())
    target = min(.6, max(3*natural, .5))
    lo, hi = 1., 1e6
    for _ in range(80):
        mid = (lo*hi)**.5
        if probs(np.where(mask, sides*mid, sides))[mask].sum() < target:
            lo = mid
        else:
            hi = mid
    for row, val in zip(data['decks'], np.where(mask, sides*hi, sides)):
        row['sides'] = int(round(val))
    data['weighted_archetypes'] = dict(alpha=.5, floor=.5, natural_share=natural, target=target, multiplier=hi,
                                      achieved=float(probs(np.array([d['sides'] for d in data['decks']]))[mask].sum()))
    return data
