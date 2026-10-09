"""L74 runover: PRO answers to skeleton swarms / Skeleton Barrels (training rows, X-Bow+Tesla decks), same episode rules
as swarm_live.py as far as the rows allow: rows are snapshots (every 40 ticks + play windows), so an episode starts at
the first row with the condition (>= 4 enemy 'skeletons'/'skeleton_army' tokens, or an enemy 'skeleton_barrel' token,
on my half = model y > 0.5), a new one after 5 s without; the answer = play rows (y_gate 1) in -1..+6 s.
Run from the MAIN checkout. Streams tok/sc out of the npz; below-normal priority.
"""
import os, sys, json, zipfile, collections, statistics as st
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
sys.path.insert(0, '.')
from pipeline import vocab

HERE = os.path.dirname(os.path.abspath(__file__))
NPZ = 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'
CV = json.load(open(NPZ.replace('.npz', '.json')))['card_vocab']; CI = {n: i for i, n in enumerate(CV)}
z = np.load(NPZ)
deck = z['deck_card']; N = len(deck)
xb = (deck == CI['x-bow']).any(1) & (deck == CI['tesla']).any(1)
y_gate, y_card, tick, rep, side, off = z['y_gate'], z['y_card'], z['tick'], z['rep'], z['side'], z['off']
hand_card = z['hand_card']
row_of = np.repeat(np.arange(N, dtype=np.int32), np.diff(off).astype(np.int64))


def stream(member, cols, fn):
    fh = zipfile.ZipFile(NPZ).open(member)
    ver = np.lib.format.read_magic(fh)
    shape, _, dt = (np.lib.format.read_array_header_1_0 if ver == (1, 0) else np.lib.format.read_array_header_2_0)(fh)
    done = 0
    while done < shape[0]:
        k = min(1_000_000, shape[0] - done)
        fn(done, np.frombuffer(fh.read(k * cols * dt.itemsize), dtype=dt).reshape(k, cols))
        done += k


SK = np.array([vocab.unit_id('skeletons'), vocab.unit_id('skeleton_army')]); BAR = vocab.unit_id('skeleton_barrel')
nsk = np.zeros(N, np.int32); nbar = np.zeros(N, np.int32)
def tokfn(o, a):
    r = row_of[o:o + len(a)]
    m = (a[:, 2] > 0.5) & (a[:, 5] > 0.5) & (a[:, 13] < 0.5)
    c = a[:, 0].astype(np.int32)
    np.add.at(nsk, r[m & np.isin(c, SK)], 1)
    np.add.at(nbar, r[m & (c == BAR)], 1)
stream('tok.npy', 14, tokfn)
el = np.zeros(N, np.float32)
def scfn(o, a): el[o:o + len(a)] = a[:, 3] * 10.0
stream('sc.npy', 70, scfn)

SPLASH = {CI[n] for n in ('the-log', 'tesla', 'ice-wizard', 'tornado')}
out = []
idx = np.nonzero(xb)[0]
order = idx[np.lexsort((tick[idx], side[idx], rep[idx]))]
for kind, cond in (('barrel', nbar > 0), ('swarm', nsk >= 4)):
    R = []
    g0 = 0
    keys = rep[order].astype(np.int64) * 2 + side[order]
    bounds = np.nonzero(np.diff(keys))[0] + 1
    for g in np.split(order, bounds):
        T = tick[g]; C = cond[g]; last = -10 ** 9
        plays = [(int(t), int(c)) for t, c, yg in zip(T, y_card[g], y_gate[g]) if yg == 1]
        for j in np.nonzero(C)[0]:
            t = int(T[j])
            if t - last > 100:
                pc = [c for (tp, c) in plays if t - 20 <= tp <= t + 120]
                seen = []
                for c in pc:
                    if c not in seen: seen.append(c)
                R.append((float(el[g[j]]), seen))
            last = t
    n = len(R)
    out.append(f'\n=== PRO {kind} episodes on my half (X-Bow+Tesla deck rows): n={n}')
    out.append(f'  elixir at start: median {st.median([r[0] for r in R]):.1f}; < 2: {sum(r[0] < 2 for r in R)}; < 3: {sum(r[0] < 3 for r in R)}')
    out.append(f'  any play within -1..+6 s: {sum(bool(r[1]) for r in R)}/{n} ({100 * sum(bool(r[1]) for r in R) / n:.0f}%); a splash answer '
               f'(Log/Tesla/IW/Tornado): {sum(any(c in SPLASH for c in r[1]) for r in R)}/{n} ({100 * sum(any(c in SPLASH for c in r[1]) for r in R) / n:.0f}%)')
    out.append('  cards played: ' + str(dict(collections.Counter(CV[c] for r in R for c in r[1]).most_common(10))))
    out.append('  first card: ' + str(dict(collections.Counter(CV[r[1][0]] if r[1] else '(none)' for r in R).most_common(10))))
open(os.path.join(HERE, 'pro_swarm.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
