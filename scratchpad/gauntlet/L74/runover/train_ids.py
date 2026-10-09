"""L74 runover Q2/Q3 (training side): what the training rows of gen_dataset_v32_fv5 carry.

Q3: Tesla's evolved form in the rows' own deck/hand/plays and as a body token (form 1), for X-Bow+Tesla decks.
Q2: per-row counts of spawner classes on one side (a unique unit seen > 1x in one row = children labelled as the parent).
Streams tok.npy out of the compressed npz in chunks (no 900 MB load). Run from the MAIN checkout. Below-normal priority.
"""
import os, sys, json, zipfile, collections
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception:
    pass
import numpy as np
sys.path.insert(0, '.')
from pipeline import vocab

NPZ = 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'
META = json.load(open(NPZ.replace('.npz', '.json')))
CV = META['card_vocab']; CI = {n: i for i, n in enumerate(CV)}
z = np.load(NPZ)
deck_card, deck_form = z['deck_card'], z['deck_form']
hand_card, hand_form = z['hand_card'], z['hand_form']
y_gate, y_card, y_pos, side, rep, off = z['y_gate'], z['y_card'], z['y_hand_pos'], z['side'], z['rep'], z['off']
unit_form = z['unit_form']
tags = z['tags']
N = len(y_gate)
T, X, I = CI['tesla'], CI['x-bow'], CI['ice-wizard']
icebow = (deck_card == X).any(1) & (deck_card == T).any(1)
iw_deck = icebow & (deck_card == I).any(1)
print(f'rows {N}; X-Bow+Tesla deck rows {icebow.sum()} ({icebow.mean():.1%}); +Ice Wizard {iw_deck.sum()}; replays {len(np.unique(rep[icebow]))}')
tes_form = np.where(deck_card == T, deck_form, -1).max(1)
print('Tesla deck_form among X-Bow+Tesla rows:', collections.Counter(tes_form[icebow].tolist()))
print('Tesla deck_form among ALL rows with Tesla in deck:', collections.Counter(tes_form[tes_form >= 0].tolist()))
reps_evo = np.unique(rep[icebow & (tes_form == 1)])
print('replays with evo Tesla in the X-Bow deck:', len(reps_evo))
play = y_gate == 1
pf = hand_form[np.arange(N), np.clip(y_pos, 0, 3)]
tp = play & (y_card == T)
print('Tesla plays (rows):', tp.sum(), 'by played form:', collections.Counter(pf[tp].tolist()),
      '| in X-Bow decks:', collections.Counter(pf[tp & icebow].tolist()))
hf = np.where(hand_card == T, hand_form, -1).max(1)
print('rows with Tesla in hand, X-Bow decks, by form:', collections.Counter(hf[icebow & (hf >= 0)].tolist()))
for t in sorted(collections.Counter(tags.tolist()).items(), key=lambda x: -x[1])[:5]: print('tag', t)

# ---- stream tok
zf = zipfile.ZipFile(NPZ)
fh = zf.open('tok.npy')
ver = np.lib.format.read_magic(fh)
shape, fortran, dt = (np.lib.format.read_array_header_1_0 if ver == (1, 0) else np.lib.format.read_array_header_2_0)(fh)
assert not fortran and shape[1] == 14, shape
row_of = np.repeat(np.arange(N, dtype=np.int32), np.diff(off).astype(np.int64))
TES = vocab.unit_id('tesla'); TES_EVO = vocab.unit_id('tesla_evo')
WATCH = ['skeleton_king', 'skeleton_barrel', 'witch', 'night_witch', 'tombstone', 'goblin_hut', 'furnace', 'barbarian_hut',
         'goblin_drill', 'phoenix', 'mother_witch', 'skeleton_army', 'suspicious_bush', 'goblin_gang', 'graveyard', 'goblin_barrel',
         'skeletons', 'bats', 'goblins', 'spear_goblins', 'barbarians', 'golem', 'golemite', 'lava_hound', 'lava_pups',
         'elixir_golem', 'royal_recruits', 'royal_recruit', 'goblin_giant', 'goblin_cage', 'guards', 'minion_horde', 'minions']
WID = {vocab.unit_id(n): n for n in WATCH}
cls_count = collections.Counter()
tesla_tok = collections.Counter()      # (mine?, form, icebow row?) for cls tesla / tesla_evo
per_row = {n: collections.Counter() for n in WATCH}   # rows by max per-side count
rows_k = 1_000_000
done = 0
while done < shape[0]:
    k = min(rows_k, shape[0] - done)
    a = np.frombuffer(fh.read(k * 14 * dt.itemsize), dtype=dt).reshape(k, 14)
    cls = a[:, 0].astype(np.int32); mine = a[:, 1] > 0.5; spell = a[:, 13] > 0.5
    r = row_of[done:done + k]; uf = unit_form[done:done + k]
    cls_count.update(dict(zip(*np.unique(cls[~spell], return_counts=True))))
    m = ((cls == TES) | (cls == TES_EVO)) & ~spell
    for cl, mi, fo, ib in zip(cls[m], mine[m], uf[m], icebow[r[m]]):
        tesla_tok[(vocab.UNIT_VOCAB[cl], 'mine' if mi else 'enemy', int(fo), 'xbow_deck_row' if ib else 'other_row')] += 1
    for cid, n in WID.items():
        mm = (cls == cid) & ~spell
        if not mm.any(): continue
        key = r[mm].astype(np.int64) * 2 + mine[mm]
        u, c = np.unique(key, return_counts=True)
        per_row[n].update(c.tolist())     # counts per (row, side) chunk-local; rows straddling a chunk edge split (negligible)
    done += k
print('\nTesla body tokens (cls, side, form, row):')
for k_, v in sorted(tesla_tok.items()): print(' ', k_, v)
print('\nbody tokens by class (top 60):')
for c, v in sorted(cls_count.items(), key=lambda x: -x[1])[:60]: print(f'  {vocab.UNIT_VOCAB[c]:22s} {v}')
print('\nper (row, side): how many bodies of the class (distribution; a unique unit > 1 = children named as parent)')
for n in WATCH:
    d = per_row[n]; tot = sum(d.values())
    if not tot: print(f'  {n:18s} none'); continue
    big = sum(v for c, v in d.items() if c >= 3)
    print(f'  {n:18s} row-sides {tot:8d}  max {max(d):3d}  1:{d[1]} 2:{d[2]} 3+:{big} ({big / tot:.1%})')
