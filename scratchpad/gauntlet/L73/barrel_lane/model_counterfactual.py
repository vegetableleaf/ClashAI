"""Does R1e's Log aim follow the barrel's target lane? (CPU, native pro states, read-only.)

Rows: the gen_v3.1 (fv4) pro rows where the pro cast the Log with exactly one enemy Goblin Barrel in flight,
target known, non-centre, aimed at the observer's half (the native_convention.py selection, n=1405).
For each row: R1e's Log cell argmax (card forced to the Log, as eval_expert_context does) on
  A) the real tokens,  B) the barrel's x AND target_x mirrored (1-x) -- nothing else changed,
  C) the barrel row removed.
If the model reads the barrel's target, A agrees with the target lane and B flips with it.
"""
import json, os, sys
import numpy as np
import torch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
sys.path.insert(0, ROOT)
from pipeline.train_rocket_curriculum import load_subset
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model

# default: R1e on its own fv4 corpus. --v6: positive control, the fv6 target-residual checkpoints on fv5 data.
if '--v6' in sys.argv:
    DATA = os.path.join(ROOT, 'icebow/data/bench/spawner_identity_20261005/gen_dataset_v5_public.npz')
    CKPTS = {k: f'icebow/data/bench/expert_context_20261005/{k}/candidate.pt' for k in ('v5_rocket_barrel', 'v6_rocket_barrel')}
    OUT = 'model_counterfactual_v6.json'
else:
    DATA = os.path.join(ROOT, 'icebow/data/pipeline/gen_dataset_v31_public.npz')
    CKPTS = {'R1e_u0155': 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0155.pt',
             'R1e_u0000': 'icebow/data/bench/rl_royale/rseries_r1e31/rseries_r1e31_u0000.pt'}
    OUT = 'model_counterfactual.json'
# lead L73: --data X --out Y --ckpt name=path [--ckpt ...] overrides the presets (e.g. gen_v3.2 vs gen_v3.2+branch)
_a = sys.argv[1:]
if '--data' in _a:
    DATA = os.path.join(ROOT, _a[_a.index('--data') + 1])
if '--out' in _a:
    OUT = _a[_a.index('--out') + 1]
if '--ckpt' in _a:
    CKPTS = dict(_a[i + 1].split('=', 1) for i, x in enumerate(_a) if x == '--ckpt')
with np.load(DATA) as z:
    cv = json.loads(str(z['meta']))['card_vocab']
GB, LOG = cv.index('goblin-barrel'), cv.index('the-log')
torch.set_num_threads(2)

with np.load(DATA) as z:
    ids = np.flatnonzero((z['y_gate'] == 1) & (z['y_card'] == LOG))
sub, _ = load_subset(DATA, ids)
shots = sub['projectiles']
enemy = (shots[:, :, 0] == GB) & (shots[:, :, 1] == 1) & (shots[:, :, 4] >= 0)
first = enemy.argmax(1)
tgt = shots[np.arange(len(ids)), first, 4:6]
sel = (enemy.sum(1) == 1) & (np.abs(tgt[:, 0] - .5) > 1.5/18) & (tgt[:, 1] > .5)
keep = np.flatnonzero(sel)
sub = {k: (v[keep] if k not in ('tok', 'unit_form', 'off') else v) for k, v in sub.items()}
# re-slice the ragged unit tokens to the kept rows
def ragged(full_sub_off, tok, uf, rows):
    starts, ends = full_sub_off[rows], full_sub_off[rows + 1]
    gather = np.concatenate([np.arange(a, b) for a, b in zip(starts, ends)])
    return tok[gather], uf[gather], np.r_[0, np.cumsum(ends - starts)].astype(np.int64)


sub['tok'], sub['unit_form'], sub['off'] = ragged(sub['off'], sub['tok'], sub['unit_form'], keep)
first, tgt = first[keep], tgt[keep]
n = len(keep)
y_lane = sub['y_xy'][:, 0] < .5
t_lane = tgt[:, 0] < .5

variants = {}
A = sub['projectiles'].copy()
B = A.copy(); B[np.arange(n), first, 2] = 1 - B[np.arange(n), first, 2]; B[np.arange(n), first, 4] = 1 - B[np.arange(n), first, 4]
C = A.copy(); C[np.arange(n), first] = 0
variants = dict(A_real=A, B_barrel_x_mirrored=B, C_barrel_removed=C)

out = dict(rows=int(n), pro_same_lane=int((y_lane == t_lane).sum()))
for name, path in CKPTS.items():
    model, st = load_model(os.path.join(ROOT, path), 'cpu'); model.eval()
    res = {}
    for vname, proj in variants.items():
        rows = GenRows(dict(sub, projectiles=proj), np.arange(n), 'cpu')
        cells = np.empty(n, np.int64)
        with torch.no_grad():
            for lo in range(0, n, 128):
                ix = np.arange(lo, min(lo + 128, n)); b = rows.batch(ix)
                enc = model.encode_gen(b)
                card = torch.full_like(b['card'], LOG)
                cells[ix] = model.cell_logits_gen(enc, card, torch.zeros_like(card)).argmax(-1).numpy()
        lx = cells % 36 / 36
        res[vname] = dict(log_lane_eq_real_target=int(((lx < .5) == t_lane).sum()),
                          log_lane_eq_pro=int(((lx < .5) == y_lane).sum()), log_x=lx)
    flip = (res['A_real']['log_x'] < .5) != (res['B_barrel_x_mirrored']['log_x'] < .5)
    flips = int(flip.sum())
    val = sub['split'] == 1          # held-out (validation) rows only: in-sample fit cannot explain these
    res['val_only'] = dict(rows=int(val.sum()),
                           A_log_lane_eq_target=int((((res['A_real']['log_x'] < .5) == t_lane) & val).sum()),
                           flips_when_barrel_mirrored=int((flip & val).sum()))
    for v in res.values():
        v.pop('log_x', None)
    out[name] = dict(feature_version=model.feature_version, **res, lane_flips_when_barrel_mirrored=flips)
    print(name, json.dumps(out[name]), flush=True)
json.dump(out, open(os.path.join(os.path.dirname(__file__), OUT), 'w'), indent=1)
print(json.dumps(out, indent=1))
