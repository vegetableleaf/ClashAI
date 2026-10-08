"""Model counterfactual, round 2: the audit's drop-phase intervention (cf_sb.py `drop_to_skel`, 7 hand-placed tokens on a
1.3-tile ring) vs the REAL look-ahead code path.

Rows = the audit's: BC-corpus rows of the defending side inside a native Skeleton Barrel episode with the Log in hand
(native_results.json, parent dir). On the DROP-phase rows (balloon gone, skeletons not yet seen; pro Log rate 51%) the
`extrap` variant adds the children that ``pipeline.extrapolate`` produces: the replay's native frames up to the first
frame that no longer shows the balloon (``gone_by``) are fed to ``DropTracker`` (10-tick frames, as a SIM decision
stream), ``extrapolate(frame_gone_by, previous frame, 26, side, drops=pending)`` builds the look-ahead, and
``obs_contract.from_engine(feature_version=fv)`` + ``body_only_board`` turn it into units; the units that appear only with
the drops are spliced into the row's tokens (``_token`` / ``unit_form``). Everything else in the row is the dataset's.
Variants: real (dataset row), hand (cf_sb drop_to_skel), extrap (real code path), extrap_nodrops (same path, no drops:
must equal real on the added units = none).
Usage: cf_real_extrapolate.py --data <npz rel. to repo> --ckpt name=path [...] --out <json in this dir>
"""
import glob, json, math, os, sys
from collections import Counter, defaultdict
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from common import ROOT                                           # noqa: E402  (4 threads, below-normal priority)
sys.path.insert(0, ROOT)
import torch                                                      # noqa: E402
from pipeline.train_rocket_curriculum import load_subset          # noqa: E402
from pipeline.eval_gen import GenRows                             # noqa: E402
from pipeline.model_gen import load_model                         # noqa: E402
from pipeline import vocab, extrapolate as X, obs_contract as oc  # noqa: E402
from pipeline.public_observation import body_only_board           # noqa: E402

MAIN = r'C:\Users\benpe\ClashBot'
torch.set_num_threads(4)
a = sys.argv[1:]
DATA = os.path.join(ROOT, a[a.index('--data') + 1])
OUT = os.path.join(HERE, a[a.index('--out') + 1])
CKPTS = dict(a[i + 1].split('=', 1) for i, x in enumerate(a) if x == '--ckpt')
SB, SKEL = vocab.unit_id('skeleton_barrel'), vocab.unit_id('skeletons')
BINS = [(-999, -60), (-60, -40), (-40, -20), (-20, 0), (0, 20), (20, 40), (40, 61)]
H = 26

nat = json.load(open(os.path.join(HERE, '..', 'native_results.json')))
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
    info.append((d, phase, own, best, int(side[i])))
ids = np.asarray(ids)
print('rows', len(ids), 'feature_version', fv, flush=True)
sub, _ = load_subset(DATA, ids)
n = len(ids)
d_arr = np.array([x[0] for x in info])
phase = np.array([x[1] for x in info])
drop_xy = np.array([x[2] for x in info])
pro_log = (sub['y_gate'] == 1) & (sub['y_card'] == LOG)

# ---- the real look-ahead path for the drop-phase rows ---------------------------------------------------------------
paths = {}
for c in json.load(open(os.path.join(ROOT, 'icebow/data/pipeline/' + os.path.basename(DATA)[:-4] + '.json')))['corpora']:
    for f in glob.glob(os.path.join(MAIN, c, 'j*', 'replay_*.json')):
        paths[os.path.basename(f)] = f
DECK = oc.load_deck('icebow')


def native_obs(f):
    ents = [dict(side=e[0], x=e[1], y=e[2], name=e[3], hp=e[4], max_hp=e[5], kind=e[6], card_id=e[7], entity_id=e[8])
            for e in f['entities']]
    towers = [dict(side=t[0], type=t[1], lane=t[2], x=t[3], y=t[4], hp=t[5], max_hp=t[6]) for t in f['towers']]
    return dict(tick=int(f['tick']), players=[], entities=ents, episode=dict(crown_towers=towers))


def lookahead_units(obs, prev, my_side, drops):
    out = X.extrapolate(obs, prev, H, my_side, drops=drops)
    bs = oc.from_engine(out, my_side, DECK, unmapped=set(), feature_version=fv)
    return body_only_board(bs).units


rec_cache, extra = {}, {}            # per drop row: list of (token row, unit_form) for the units only the drops add
stats = Counter()
for r in sorted(range(n), key=lambda r: info[r][3]['file']):
    if phase[r] != 'drop':
        continue
    ep, my_side = info[r][3], info[r][4]
    key = (ep['file'], my_side, ep['gone_by'])
    if key not in extra:
        if ep['file'] not in rec_cache:
            rec_cache = {ep['file']: json.load(open(paths[ep['file']], encoding='utf-8'))}
        rec = rec_cache[ep['file']]
        by_tick = {int(f['tick']): f for f in rec['frames']}
        ticks = sorted(t for t in by_tick if t <= ep['gone_by'])
        tr = X.DropTracker()
        for t in ticks:
            tr.observe(native_obs(by_tick[t]), my_side)
        cur, prv = native_obs(by_tick[ticks[-1]]), native_obs(by_tick[ticks[-2]])
        if not tr.pending or ticks[-1] != ep['gone_by']:
            stats['no_prediction'] += 1
            extra[key] = []
        else:
            on = Counter(lookahead_units(cur, prv, my_side, tr.pending))
            off = Counter(lookahead_units(cur, prv, my_side, None))
            added = on - off
            assert not (off - on)
            stats['predicted'] += 1
            stats['units_added_%d' % sum(added.values())] += 1
            extra[key] = [(np.asarray(oc._token(u, False), np.float32), u.form, u.cls) for u in added.elements()]
    stats['rows_' + ('with' if extra[key] else 'without') + '_children'] += 1
print(dict(stats), flush=True)


def balloon_token(sub, r):
    lo, hi = sub['off'][r], sub['off'][r + 1]
    t = sub['tok'][lo:hi]
    hit = np.flatnonzero((np.rint(t[:, 0]) == SB) & (t[:, 2] == 1))
    return lo + hit[0] if len(hit) == 1 else None


def edited(kind):
    tok, uf, off = sub['tok'], sub['unit_form'], sub['off']
    toks, ufs, lens = [], [], []
    for r in range(n):
        lo, hi = off[r], off[r + 1]
        t, f = tok[lo:hi].copy(), uf[lo:hi].copy()
        if phase[r] == 'drop' and kind == 'hand':             # the audit's hand-placed ring (cf_sb.py, 1.3 tiles)
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
        if phase[r] == 'drop' and kind == 'extrap':
            ex = extra[(info[r][3]['file'], info[r][4], info[r][3]['gone_by'])]
            if ex:
                t = np.concatenate([t, np.stack([e[0] for e in ex]).astype(t.dtype)])[:64]
                f = np.concatenate([f, np.asarray([e[1] for e in ex], f.dtype)])[:64]
        toks.append(t); ufs.append(f); lens.append(len(t))
    return dict(sub, tok=np.concatenate(toks), unit_form=np.concatenate(ufs), off=np.r_[0, np.cumsum(lens)].astype(np.int64))


is_drop = phase == 'drop'
has_pred = np.array([bool(extra.get((info[r][3]['file'], info[r][4], info[r][3]['gone_by']))) if is_drop[r] else False
                     for r in range(n)])
variants = dict(real=sub, hand=edited('hand'), extrap=edited('extrap'))


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


res = dict(data=os.path.relpath(DATA, ROOT), feature_version=fv, rows=int(n), drop_rows=int(is_drop.sum()),
           drop_rows_with_predicted_children=int(has_pred.sum()), extrap_stats=dict(stats),
           pro_log_rate_drop_rows=round(float(pro_log[is_drop].mean()), 4),
           pro_log_rate_drop_rows_with_prediction=round(float(pro_log[has_pred].mean()), 4), models={})
for name, path in CKPTS.items():
    model, _ = load_model(os.path.join(ROOT, path), 'cpu')
    model.eval()
    if model.feature_version != fv:
        raise SystemExit(f'{name}: model fv {model.feature_version} != data fv {fv}')
    P = {k: probs(model, v) for k, v in variants.items()}
    r = {}
    for label, m in (('drop_rows', is_drop), ('drop_rows_with_prediction', has_pred)):
        r[label] = {k: dict(p_play=round(float(P[k][m, 0].mean()), 4), p_log_given_play=round(float(P[k][m, 1].mean()), 4),
                            p_log_now=round(float(P[k][m, 2].mean()), 4)) for k in variants}
    others = ~is_drop
    r['non_drop_rows_unchanged'] = bool(np.allclose(P['real'][others], P['extrap'][others]))
    res['models'][name] = r
    print(name, json.dumps(r), flush=True)
json.dump(res, open(OUT, 'w'), indent=1)
print(json.dumps(res, indent=1))
