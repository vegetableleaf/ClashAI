"""Training-data convention check (native pro replays, gen_dataset_v31_public = the fv4 BC corpus).

If the projectile target columns and the action label y_xy share one frame, pros who Log a barrel in flight
put the Log in the target's lane far above chance. A frame mismatch (e.g. target x mirrored vs action x)
would show as a strong OPPOSITE-lane majority. Split by observer side. Streams only the Log-play rows.
"""
import json, os, sys
from zipfile import ZipFile
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, ROOT)
from pipeline.train_rocket_curriculum import take

DATA = os.path.join(ROOT, 'icebow/data/pipeline/gen_dataset_v31_public.npz')
meta = json.load(open(DATA.replace('.npz', '.json')))
cv = meta['card_vocab']
GB, LOG = cv.index('goblin-barrel'), cv.index('the-log')
with np.load(DATA) as z:
    y_gate, y_card, side = z['y_gate'], z['y_card'], z['side']
ids = np.flatnonzero((y_gate == 1) & (y_card == LOG))
with np.load(DATA) as z, ZipFile(DATA) as ar:
    shots = take(ar, 'projectiles', ids)
    y_xy = take(ar, 'y_xy', ids)
s = side[ids]
enemy = (shots[:, :, 0] == GB) & (shots[:, :, 1] == 1) & (shots[:, :, 4] >= 0)
one = enemy.sum(1) == 1
first = enemy.argmax(1)
tgt = shots[np.arange(len(ids)), first, 4:6]
pos = shots[np.arange(len(ids)), first, 2:4]
noncenter = np.abs(tgt[:, 0] - .5) > 1.5/18
own_half = tgt[:, 1] > .5          # barrel aimed at the observer's half (own edge y=1)
sel = one & noncenter & own_half
same = (y_xy[:, 0] < .5) == (tgt[:, 0] < .5)
dx = np.abs(y_xy[:, 0] - tgt[:, 0]) * 18
out = dict(dataset=os.path.relpath(DATA, ROOT), log_plays=int(len(ids)), with_one_enemy_barrel_target_known=int(one.sum()),
           selected_noncenter_own_half=int(sel.sum()),
           pro_log_same_lane_as_target=dict(n=int(sel.sum()), same=int((same & sel).sum()),
                                            rate=round(float((same & sel).sum()/max(1, sel.sum())), 3)),
           by_side={int(k): dict(n=int((sel & (s == k)).sum()), same=int((same & sel & (s == k)).sum()))
                    for k in (0, 1)},
           median_dx_tiles=round(float(np.median(dx[sel])), 2) if sel.any() else None,
           target_x_hist_own=np.histogram(tgt[sel, 0], bins=[0, .25, .5, .75, 1])[0].tolist(),
           target_y_own_median=round(float(np.median(tgt[sel, 1])), 3) if sel.any() else None)
print(json.dumps(out, indent=1))
json.dump(out, open(os.path.join(os.path.dirname(__file__), 'native_results.json'), 'w'), indent=1)
