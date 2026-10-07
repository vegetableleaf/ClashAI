"""Model counterfactual on pro states around a Skeleton Barrel drop (CPU, read-only, no training).

Rows: BC-corpus rows of the DEFENDING side whose (replay tag, side, tick) falls in a native Skeleton Barrel episode
(native_results.json, measured by native_sb.py: balloon last seen, skeletons first seen), with the Log in hand.
Bins: d = row tick - skeleton spawn tick (row tick = the pro's command tick; a Log rolls ~9 ticks later).
Per bin: pro rate of 'Log now' (y_gate=1 & y_card=Log) vs the model's P(play) * P(Log | play).
Interventions on balloon-phase rows with exactly one enemy Skeleton Barrel parent token:
  hp_low   -- the balloon token's hp_frac -> 0.05 (about to die)
  to_skel  -- the balloon token replaced by 7 skeleton tokens on the 1.3-tile ring (fv4: class skeleton_barrel,
              the class its skeletons carry in fv4; fv5: class skeletons)
  removed  -- the balloon token deleted
Intervention on drop-phase rows (balloon gone, skeletons not yet seen):
  drop_to_skel -- 7 skeleton tokens added on the ring at the drop point (a look-ahead that simulated the fall)
Usage: cf_sb.py --data <npz> --ckpt name=path [--ckpt ...] --out <json>
"""
import json, math, os, sys
from collections import defaultdict
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from common import ROOT
sys.path.insert(0, ROOT)
import torch
from pipeline.train_rocket_curriculum import load_subset
from pipeline.eval_gen import GenRows
from pipeline.model_gen import load_model
from pipeline import vocab

torch.set_num_threads(4)
a = sys.argv[1:]
DATA = os.path.join(ROOT, a[a.index('--data') + 1])
OUT = os.path.join(os.path.dirname(__file__), a[a.index('--out') + 1])
CKPTS = dict(a[i + 1].split('=', 1) for i, x in enumerate(a) if x == '--ckpt')
SB, SKEL = vocab.unit_id('skeleton_barrel'), vocab.unit_id('skeletons')
BINS = [(-999, -60), (-60, -40), (-40, -20), (-20, 0), (0, 20), (20, 40), (40, 61)]

nat = json.load(open(os.path.join(os.path.dirname(__file__), 'native_results.json')))
eps = defaultdict(list)
for e in nat['episodes']:
    if e.get('spawn_hi') is not None and e['n_skel'] > 0:
        eps[(e['file'][len('replay_'):-len('.json')], int(e['side']))].append(e)

with np.load(DATA) as z:
    meta = json.loads(str(z['meta']))
    tags, rep, side, tick = z['tags'], z['rep'], z['side'], z['tick']
    y_gate, y_card, hand = z['y_gate'], z['y_card'], z['hand_card']
LOG = meta['card_vocab'].index('the-log')
fv = int(meta['feature_version'])
want = {i for i, t in enumerate(tags) if (str(t), 0) in eps or (str(t), 1) in eps}
cand = np.flatnonzero(np.isin(rep, list(want)) & (hand == LOG).any(1))
ids, info = [], []
for i in cand:
    t = int(tick[i])
    best = None
    for e in eps.get((str(tags[rep[i]]), int(side[i])), ()):
        if e['first_seen'] <= t <= e['spawn_hi'] + 60:
            if best is None or abs(t - e['spawn_hi']) < abs(t - best['spawn_hi']):
                best = e
    if best is None:
        continue
    d = t - best['spawn_hi']
    phase = 'balloon' if t <= best['last_seen'] else 'drop' if t < best['spawn_hi'] else 'skeletons'
    ids.append(int(i))
    bx, by = best['last_pos']
    own = (bx / 18000, 1 - by / 32000) if int(side[i]) == 0 else (1 - bx / 18000, by / 32000)
    info.append((d, phase, own))
ids = np.asarray(ids)
print('rows', len(ids), 'feature_version', fv, flush=True)
sub, _ = load_subset(DATA, ids)
n = len(ids)
d_arr = np.array([x[0] for x in info])
phase = np.array([x[1] for x in info])
drop_xy = np.array([x[2] for x in info])
pro_log = (sub['y_gate'] == 1) & (sub['y_card'] == LOG)


def balloon_token(sub, r):
    lo, hi = sub['off'][r], sub['off'][r + 1]
    t = sub['tok'][lo:hi]
    hit = np.flatnonzero((np.rint(t[:, 0]) == SB) & (t[:, 2] == 1))
    return lo + hit[0] if len(hit) == 1 else None


def edited(kind):
    """A copy of sub with the balloon token edited on the eligible balloon rows (others unchanged)."""
    tok, uf, off = sub['tok'], sub['unit_form'], sub['off']
    toks, ufs, lens = [], [], []
    for r in range(n):
        lo, hi = off[r], off[r + 1]
        t, f = tok[lo:hi].copy(), uf[lo:hi].copy()
        j = balloon_token(sub, r) if phase[r] == 'balloon' else None
        if kind == 'drop_to_skel' and phase[r] == 'drop':
            # what a look-ahead that simulated the 12-tick fall would show: the 7 skeletons on the ring at the drop
            q0 = np.zeros(t.shape[1], t.dtype)
            q0[0], q0[2], q0[6], q0[7], q0[12] = (SB if fv < 5 else SKEL), 1, 1, 1, 1
            ring = []
            for k in range(7):
                q = q0.copy()
                q[4] = min(max(drop_xy[r][0] + 1.3 / 18 * math.cos(2 * math.pi * k / 7), 0), 1)
                q[5] = min(max(drop_xy[r][1] + 1.3 / 32 * math.sin(2 * math.pi * k / 7), 0), 1)
                ring.append(q)
            t = np.concatenate([t, np.stack(ring)])[:64]
            f = np.concatenate([f, np.zeros(7, f.dtype)])[:64]
        if j is not None and kind != 'drop_to_skel':
            j -= lo
            if kind == 'hp_low':
                t[j, 6] = 0.05
            elif kind == 'removed':
                t, f = np.delete(t, j, 0), np.delete(f, j, 0)
            elif kind == 'to_skel':
                base = t[j].copy()
                ring = []
                for k in range(7):
                    q = base.copy()
                    q[0] = SB if fv < 5 else SKEL
                    q[4] = min(max(base[4] + 1.3 / 18 * math.cos(2 * math.pi * k / 7), 0), 1)
                    q[5] = min(max(base[5] + 1.3 / 32 * math.sin(2 * math.pi * k / 7), 0), 1)
                    q[6], q[7] = 1.0, 1.0
                    ring.append(q)
                t = np.concatenate([np.delete(t, j, 0), np.stack(ring)])[:64]
                f = np.concatenate([np.delete(f, j, 0), np.zeros(7, f.dtype)])[:64]
        toks.append(t); ufs.append(f); lens.append(len(t))
    return dict(sub, tok=np.concatenate(toks), unit_form=np.concatenate(ufs),
                off=np.r_[0, np.cumsum(lens)].astype(np.int64))


elig = np.array([phase[r] == 'balloon' and balloon_token(sub, r) is not None for r in range(n)])
variants = dict(real=sub, hp_low=edited('hp_low'), to_skel=edited('to_skel'), removed=edited('removed'),
                drop_to_skel=edited('drop_to_skel'))


def probs(model, arrs):
    rows = GenRows(arrs, np.arange(n), 'cpu')
    out = np.zeros((n, 3), np.float32)
    with torch.no_grad():
        for lo in range(0, n, 256):
            ix = np.arange(lo, min(lo + 256, n))
            b = rows.batch(ix)
            h = model.heads_gen(model.encode_gen(b), b)
            pp = torch.sigmoid(h['gate'])
            pc = torch.softmax(h['card'], -1)
            pl = (pc * (b['hand_card'] == LOG)).sum(-1)
            out[ix] = torch.stack([pp, pl, pp * pl], -1).numpy()
    return out


res = dict(data=os.path.relpath(DATA, ROOT), feature_version=fv, rows=int(n), eligible_balloon_rows=int(elig.sum()),
           bins={}, models={})
for lo, hi in BINS:
    m = (d_arr >= lo) & (d_arr < hi)
    res['bins'][f'{lo}..{hi}'] = dict(n=int(m.sum()), phases={p: int((m & (phase == p)).sum()) for p in ('balloon', 'drop', 'skeletons')},
                                      pro_log_rate=round(float(pro_log[m].mean()), 4) if m.any() else None)
for name, path in CKPTS.items():
    model, _ = load_model(os.path.join(ROOT, path), 'cpu')
    model.eval()
    if model.feature_version != fv:
        raise SystemExit(f'{name}: model fv {model.feature_version} != data fv {fv}')
    P = {k: probs(model, v) for k, v in variants.items()}
    r = dict(bins={})
    for lo, hi in BINS:
        m = (d_arr >= lo) & (d_arr < hi)
        if m.any():
            r['bins'][f'{lo}..{hi}'] = dict(p_play=round(float(P['real'][m, 0].mean()), 4),
                                            p_log_given_play=round(float(P['real'][m, 1].mean()), 4),
                                            p_log_now=round(float(P['real'][m, 2].mean()), 4))
    r['interventions_on_eligible_balloon_rows'] = {
        k: dict(p_play=round(float(P[k][elig, 0].mean()), 4), p_log_given_play=round(float(P[k][elig, 1].mean()), 4),
                p_log_now=round(float(P[k][elig, 2].mean()), 4)) for k in variants}
    # balloon rows split by time to spawn: does the model's Log rise as the drop approaches?
    for lo, hi in ((-999, -40), (-40, -14), (-14, 0)):
        m = elig & (d_arr >= lo) & (d_arr < hi)
        r[f'balloon_rows_d{lo}..{hi}'] = dict(n=int(m.sum()), pro_log_rate=round(float(pro_log[m].mean()), 4) if m.any() else None,
                                              p_log_now=round(float(P['real'][m, 2].mean()), 4) if m.any() else None,
                                              p_log_now_to_skel=round(float(P['to_skel'][m, 2].mean()), 4) if m.any() else None)
    r['by_phase'] = {}
    for ph in ('balloon', 'drop', 'skeletons'):
        m = phase == ph
        r['by_phase'][ph] = dict(n=int(m.sum()), pro_log_rate=round(float(pro_log[m].mean()), 4),
                                 **{f'p_log_now_{k}': round(float(P[k][m, 2].mean()), 4) for k in ('real', 'drop_to_skel')},
                                 p_play_real=round(float(P['real'][m, 0].mean()), 4))
    res['models'][name] = r
    print(name, json.dumps(r), flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
