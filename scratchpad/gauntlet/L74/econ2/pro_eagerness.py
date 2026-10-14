"""L74 econ2 option 1 -- is the low-elixir eagerness IMITATION FIT (too eager on the pros' own states) or DISTRIBUTION
SHIFT (as patient as pros on pro states, eager only on states the bot reaches itself)?

    pod: PYTHONPATH=/workspace/clashbot nice -n 19 /workspace/venv33/bin/python pro_eagerness.py run --out DIR \
           --pro icebow/data/pipeline/gen_dataset_v32_fv5.npz --sim /workspace/results/DISTILL_ADAPT/gen \
           --ckpt r1=PATH --ckpt adapt=PATH --ckpt gen_v1=PATH [--ckpt imit_v32=PATH] --sim-model adapt
    any: python pro_eagerness.py selftest

Per row, from the row's OWN observation (board frame: me at the bottom, token y >= 0.5 = my half):
  e      own elixir = sc[3] * 10 (exact in pro and SIM rows); bins 0-2 / 2-4 / 4-6 / 6-8 / 8-10
  phase  from the tick: 1x < 2400 <= 2x < 3600 <= OT (econ_gap.ph); deployed tau .35 / .45 / .55
  value  of an enemy body = pipeline.decision_options.body_value(cls) (card cost / bodies the card puts out, children share
         the parent's; FULL hp, like econ2's push value; spells and ability markers 0). fv5 rows carry no spell tokens.
  vm     enemy body value on my half (all bodies, buildings included = econ2's vm)
  vt     enemy TROOP value on their half (buildings excluded: they do not push)
  rec    opponent NON-spell plays in the row's opp_past (last 3 public plays) with age <= 15 s, summed elixir cost
  UNDER_ATTACK  vm >= 3
  APPROACH      vm < 1 and vt >= 3 and rec >= 3   (a push committed, units recently deployed, none yet on my half)
  QUIET         vm < 0.5 and vt < 1              (no meaningful enemy value anywhere; their buildings ignored)
  OTHER         the rest (small value on my half, troops on their half without a recent play, ...)
Rows: pro = eval_gen.val_rows (split 1); label = y_gate. SIM = every learner decision of the distill generator; the
'sampled' subset = train_distill.select (accepted plays + 1 wait row / 2 s, none within 1 s before a play) = the pro row
sampling, label = the bot's accepted play. CIs: Poisson bootstrap over matches (pro: replay `rep`, both sides; SIM: game).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT), str(HERE.parent / 'distill')]

E_NAMES = ('0-2', '2-4', '4-6', '6-8', '8-10')
CTX = ('QUIET', 'APPROACH', 'UNDER_ATTACK', 'OTHER')
PH = ('1x', '2x', 'OT')
TAU = np.array([.35, .45, .55])
RECENT_S, APPROACH_V, ATTACK_V, NONE_ON_MINE, QUIET_MINE, QUIET_THEIRS = 15.0, 3.0, 3.0, 1.0, 0.5, 1.0
B = 1000


# ------------------------------------------------------------------ row features
def unit_tables():
    """per vocab id: (body value, is building)."""
    from pipeline import vocab
    from pipeline.decision_options import body_value
    return (np.array([body_value(c) for c in range(vocab.N_VOCAB)]),
            np.array([vocab.kind_of(c) == 'building' for c in range(vocab.N_VOCAB)]))


def card_tables(card_vocab):
    """per gen card id: (elixir cost, is spell), RoyaleSim catalog, dataset_gen's key rule."""
    from pipeline import vocab
    from pipeline.body_identity import CATALOG
    cat = {}
    for c in json.loads(CATALOG.read_text(encoding='utf-8'))['cards']:
        k = vocab.engine_key(c['name'])
        if k:
            cat.setdefault(vocab.base_key(k), (float(c.get('elixir') or 0), c.get('kind') == 'spell'))
    cost, spell = np.zeros(len(card_vocab)), np.zeros(len(card_vocab), bool)
    for i, k in enumerate(card_vocab[1:], 1):
        cost[i], spell[i] = cat.get(k.replace('-', '_'), (0.0, False))
    return cost, spell


def features(tok, off, sc, opp_past, tick, utab, ctab):
    """-> dict of per-row arrays: e, eb, ph, ctx, vm, vt, rec. ``tok`` flat [units, F] with row offsets ``off``."""
    val, bld = utab
    cost, spell = ctab
    n = len(off) - 1
    rid = np.repeat(np.arange(n), np.diff(off))
    cls = tok[:, 0].astype(np.int64)
    v = np.where((tok[:, 2] > .5) & (tok[:, 13] < .5), val[cls], 0.0)
    mine = tok[:, 5] >= .5
    vm = np.bincount(rid, v * mine, n)
    vt = np.bincount(rid, v * (~mine & ~bld[cls]), n)
    c = opp_past[..., 0].astype(np.int64)
    rec = (((c > 0) & ~spell[c] & (opp_past[..., 4] <= RECENT_S)) * cost[c]).sum(1)
    ctx = np.full(n, 3, np.int8)
    ctx[(vm < QUIET_MINE) & (vt < QUIET_THEIRS)] = 0
    ctx[(vm < NONE_ON_MINE) & (vt >= APPROACH_V) & (rec >= APPROACH_V)] = 1
    ctx[vm >= ATTACK_V] = 2
    e = sc[:, 3].astype(np.float64) * 10
    return dict(e=e, eb=np.digitize(e, [2, 4, 6, 8]).astype(np.int8), ph=np.digitize(tick, [2400, 3600]).astype(np.int8),
                ctx=ctx, vm=vm, vt=vt, rec=rec)


def push_starts(T, vm):
    """econ2.push_starts (econ2.py:42): enemy value on my half >= 7 after >= 80 ticks below. Copied: econ2 imports
    econ_gap, whose import reads laptop/VM paths."""
    out, lh, on = [], -10 ** 9, False
    for t, v in zip(T, vm):
        if v >= 7:
            if not on and t - lh >= 80:
                out.append(t)
            on, lh = True, t
        else:
            on = False
    return out


# ------------------------------------------------------------------ data
def gather(off, idx):
    """flat unit ids of rows ``idx`` + their new offsets."""
    lens = off[idx + 1] - off[idx]
    new = np.concatenate([[0], np.cumsum(lens)]).astype(np.int64)
    return np.repeat(off[idx] - new[:-1], lens) + np.arange(new[-1]), new


def load_pro(path):
    from pipeline.eval_gen import val_rows
    z = np.load(path, allow_pickle=False)
    meta = json.loads(str(z['meta']))
    split = z['split']
    va = val_rows({'split': split})
    off = z['off']
    flat, new = gather(off, va)
    arrs = {'off': new}
    for k in z.files:
        if k in ('meta', 'tags', 'off'):
            continue
        a = z[k]
        arrs[k] = a[flat] if k in ('tok', 'unit_form') else a[va]
        del a
    return arrs, meta


def load_sim(gen_dir, card_vocab):
    import train_distill as TD
    files = sorted(Path(gen_dir).rglob('distill_*.npz'))
    if not files:
        raise SystemExit(f'no distill_*.npz under {gen_dir}')
    keys = ('sc', 'past', 'hand_card', 'hand_form', 'next_card', 'next_form', 'deck_card', 'deck_form', 'opp_past',
            'opp_cycle', 'projectiles', 'effects', 'own_ability', 'tick', 'play', 'accepted', 'p', 'why')
    parts = {}
    for gi, f in enumerate(files):
        g, meta = TD.load_game(f)
        if meta['card_vocab'] != card_vocab:
            raise SystemExit(f'{f}: card vocab differs from the pro data')
        mask = g['mask'].astype(bool)
        m = mask.sum(1)
        if not (mask == (np.arange(mask.shape[1]) < m[:, None])).all():
            raise ValueError('unit mask is not a prefix')
        plays, waits, _ = TD.select(g)
        n = len(m)
        sampled = np.zeros(n, bool); sampled[plays] = True; sampled[waits] = True
        lab = np.zeros(n, np.int8); lab[plays] = 1
        cols = {k: g[k] for k in keys}
        cols.update(tok=g['tok'][mask], unit_form=g['unit_form'][mask], n_tok=m, sampled=sampled, y_gate=lab,
                    game=np.full(n, gi, np.int32))
        for k, v in cols.items():
            parts.setdefault(k, []).append(v)
    arrs = {k: np.concatenate(v) for k, v in parts.items()}
    arrs['off'] = np.concatenate([[0], np.cumsum(arrs.pop('n_tok'))]).astype(np.int64)
    n = len(arrs['sc'])
    arrs.update(y_xy=np.zeros((n, 2), np.float32), y_hand_pos=np.full(n, -1, np.int8), y_card=np.zeros(n, np.int16),
                y_wait_card=np.zeros(n, np.int16), y_crowns=np.zeros((n, 2), np.int8))
    return arrs, len(files)


def remap(arrs, data_vocab, model_vocab):
    """card ids of the data vocab -> the model's (0 = pad / unknown) on the arrays an fv1-3 model reads."""
    if data_vocab == model_vocab:
        return arrs, 0
    pos = {k: i for i, k in enumerate(model_vocab)}
    lut = np.array([pos.get(k, 0) for k in data_vocab], np.int64)
    out = dict(arrs)
    for k in ('hand_card', 'next_card', 'deck_card', 'y_card', 'y_wait_card'):
        out[k] = lut[arrs[k].astype(np.int64)].astype(arrs[k].dtype)
    for k in ('past', 'opp_past'):
        if k in arrs:
            a = arrs[k].copy(); a[..., 0] = np.where(a[..., 0] > 0, lut[np.clip(a[..., 0], 0, None).astype(np.int64)], a[..., 0])
            out[k] = a
    for k in ('opp_cycle', 'projectiles', 'effects', 'own_ability'):
        out.pop(k, None)                                       # fv1-3 never read them (dropped, not remapped)
    return out, int((lut[1:] == 0).sum())


def gate_p(ckpt, arrs, data_vocab, dev, bs=2048):
    import torch
    from pipeline.eval_gen import GenRows
    from pipeline.model_gen import load_model
    model, st = load_model(ckpt, dev)
    model.eval()
    a, missing = remap(arrs, data_vocab, st['card_vocab'])
    if a is not arrs and int(getattr(model, 'feature_version', 1)) >= 4:
        raise SystemExit(f'{ckpt}: fv>=4 model with another card vocab; refusing to drop its object inputs')
    rows = GenRows(a, np.arange(len(a['sc'])), dev)
    out = []
    with torch.no_grad():
        for s in range(0, len(rows.idx), bs):
            out.append(torch.sigmoid(model(rows.batch(rows.idx[s:s + bs]))['gate'].float()).cpu().numpy())
    info = dict(feature_version=int(getattr(model, 'feature_version', 1)), vocab_missing=missing,
                refine=[k for k in ('cell_refine', 'tower_refine') if getattr(model, k, None) is not None])
    del model, rows
    torch.cuda.empty_cache() if dev.type == 'cuda' else None
    return np.concatenate(out).astype(np.float64), info


# ------------------------------------------------------------------ statistics
def groups(f):
    """[(name, mask)]: ctx x elixir bin (all phases), the same per phase, and pooled low-elixir (< 4) rows."""
    g = []
    for c, cn in enumerate(CTX):
        for b, bn in enumerate(E_NAMES):
            m = (f['ctx'] == c) & (f['eb'] == b)
            g.append((f'{cn}|{bn}', m))
            for p, pn in enumerate(PH):
                g.append((f'{cn}|{bn}|{pn}', m & (f['ph'] == p)))
        g.append((f'{cn}|0-4', (f['ctx'] == c) & (f['e'] < 4)))
        g.append((f'{cn}|0-4|1x', (f['ctx'] == c) & (f['e'] < 4) & (f['ph'] == 0)))
    g.append(('ALL|0-4', f['e'] < 4))
    g.append(('ALL', np.ones(len(f['e']), bool)))
    return g


def boot(cl, grp, cols, seed=0):
    """Poisson cluster bootstrap of sum(col)/n per group. -> {name: {n, col: point}}, {col: replicates [B, G]}."""
    ncl = int(cl.max()) + 1
    W = np.random.default_rng(seed).poisson(1.0, (B, ncl)).astype(np.float64)
    names = [n for n, _ in grp]
    S0 = np.stack([np.bincount(cl[m], minlength=ncl) for _, m in grp], 1).astype(np.float64)
    n_rep = W @ S0
    pts = {n: {'n': int(S0[:, i].sum()), 'matches': int((S0[:, i] > 0).sum())} for i, n in enumerate(names)}
    reps = {}
    for k, v in cols.items():
        S = np.stack([np.bincount(cl[m], v[m], minlength=ncl) for _, m in grp], 1)
        tot = S.sum(0) / np.maximum(S0.sum(0), 1)
        reps[k] = (W @ S) / np.where(n_rep > 0, n_rep, np.nan)
        for i, n in enumerate(names):
            pts[n][k] = float(tot[i]) if S0[:, i].sum() else None
    return pts, reps


def ci(r):
    lo, hi = np.nanpercentile(r, [2.5, 97.5], axis=0)
    return lo, hi


def stat_cols(f, p, lab):
    tau = TAU[f['ph']]
    return {'label': lab.astype(np.float64), 'p': p, 'over': (p > tau).astype(np.float64), 'p_minus_label': p - lab,
            'over_minus_label': (p > tau) - lab.astype(np.float64)}


def add_ci(pts, reps, names, keys=('p', 'over', 'label', 'p_minus_label', 'over_minus_label')):
    for k in keys:
        lo, hi = ci(reps[k])
        for i, n in enumerate(names):
            if pts[n].get(k) is not None:
                pts[n][k + '_ci'] = [float(lo[i]), float(hi[i])]


# ------------------------------------------------------------------ run
def deck_key(deck_card):
    """per row: its 8 card ids sorted (forms ignored) as one int64 key."""
    d = np.sort(deck_card.astype(np.int64), 1)
    return (d * (256 ** np.arange(8, dtype=np.int64)[::-1])).sum(1)


def pro_block(cl, f, p, lab, mask, names, seed=0):
    """bucket stats of one model on the pro rows in ``mask``."""
    sub = {k: v[mask] for k, v in f.items()}
    pts, reps = boot(cl[mask], groups(sub), stat_cols(sub, p[mask], lab[mask]), seed=seed)
    add_ci(pts, reps, names)
    return pts, reps


def compare(pts_s, reps_s, pts_p, reps_p, names):
    """same model, same bucket: SIM-visited minus pro (independent bootstraps -> difference of replicates), plus the
    label-gap decomposition: bot - pros = fit (p_pro - L_pro) + shift (p_sim - p_pro) + decision (L_sim - p_sim)."""
    cmp = {}
    for i, n in enumerate(names):
        row = {}
        for k in ('p', 'over', 'label'):
            vs, vp = pts_s[n].get(k), pts_p[n].get(k)
            if vs is None or vp is None:
                continue
            lo, hi = np.nanpercentile(reps_s[k][:, i] - reps_p[k][:, i], [2.5, 97.5])
            row[k] = {'sim': vs, 'pro': vp, 'diff': vs - vp, 'ci': [float(lo), float(hi)]}
        for k in ('p', 'over'):
            if k in row and 'label' in row:
                row[f'decomp_{k}'] = {'fit': row[k]['pro'] - row['label']['pro'], 'shift': row[k]['sim'] - row[k]['pro'],
                                      'decision': row['label']['sim'] - row[k]['sim'],
                                      'total': row['label']['sim'] - row['label']['pro']}
        if row:
            cmp[n] = row
    return cmp


BAL_GROUPS = ('APPROACH|0-4', 'APPROACH|0-4|1x', 'UNDER_ATTACK|0-4', 'UNDER_ATTACK|0-4|1x', 'ALL|0-4')


def balance(cl_p, fp, pp, mp, cl_s, fs, ps, ms):
    """Covariate means pro vs SIM inside BAL_GROUPS, and the SIM - pro gap in p / p > tau after reweighting the SIM rows to
    the pro distribution over cells (elixir 0.5 bins x vm bins x vt bins x phase; common support only)."""
    fp_, fs_ = {k: v[mp] for k, v in fp.items()}, {k: v[ms] for k, v in fs.items()}
    gp, gs = dict(groups(fp_)), dict(groups(fs_))
    pp_, ps_, clp, cls_ = pp[mp], ps[ms], cl_p[mp], cl_s[ms]

    def cell(f):
        return ((np.floor(np.clip(f['e'], 0, 9.99) * 2).astype(np.int64) * 6 + np.digitize(f['vm'], [1, 3, 5, 7, 10])) * 5
                + np.digitize(f['vt'], [3, 5, 8, 12])) * 3 + f['ph']
    cp, cs = cell(fp_), cell(fs_)
    out = {}
    for g in BAL_GROUPS:
        a, b = gp[g], gs[g]
        if not a.any() or not b.any():
            continue
        cov ={k: [float(fp_[k][a].mean()), float(fs_[k][b].mean())] for k in ('e', 'vm', 'vt', 'rec', 'opp_el')}
        cov['share_1x'] = [float((fp_['ph'][a] == 0).mean()), float((fs_['ph'][b] == 0).mean())]
        size = int(max(cp.max(), cs.max())) + 1
        n_p, n_s = np.bincount(cp[a], minlength=size), np.bincount(cs[b], minlength=size)
        sup_p = a & (n_s[cp] > 0)
        w = np.where(b & (n_p[cs] > 0), n_p[cs] / np.maximum(n_s[cs], 1), 0.0)
        tau_p, tau_s = TAU[fp_['ph']], TAU[fs_['ph']]
        P, RP = boot(clp, [('g', sup_p)], {'p': pp_, 'over': (pp_ > tau_p).astype(float)}, seed=3)
        S, RS = boot(cls_, [('g', b)], {'wp': w * ps_, 'wo': w * (ps_ > tau_s), 'w': w}, seed=4)
        row = {'covariates_pro_sim': cov, 'pro_rows_in_support': float(sup_p.sum() / max(a.sum(), 1)),
               'sim_rows_in_support': float((w > 0).sum() / max(b.sum(), 1))}
        for k, kw in (('p', 'wp'), ('over', 'wo')):
            sim_v = S['g'][kw] / S['g']['w']
            lo, hi = np.nanpercentile(RS[kw][:, 0] / RS['w'][:, 0] - RP[k][:, 0], [2.5, 97.5])
            row[k] = {'pro': P['g'][k], 'sim_reweighted': sim_v, 'diff': sim_v - P['g'][k], 'ci': [float(lo), float(hi)]}
        out[g] = row
    return out


def run(a):
    import torch
    torch.set_num_threads(a.threads)
    dev = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    t0 = time.time()
    log = lambda *x: print(f'[{time.time() - t0:7.1f}s]', *x, flush=True)
    a.out.mkdir(parents=True, exist_ok=True)
    utab = unit_tables()
    pro, meta = load_pro(a.pro)
    vocab_ = meta['card_vocab']
    ctab = card_tables(vocab_)
    log('pro val rows', len(pro['sc']), 'replays', len(np.unique(pro['rep'])))
    fp = features(pro['tok'], pro['off'], pro['sc'], pro['opp_past'], pro['tick'], utab, ctab)
    fp['opp_el'] = pro['sc'][:, 5].astype(np.float64) * 10
    res = {'definitions': __doc__, 'pro': {'data': str(a.pro), 'rows': int(len(pro['sc'])),
                                          'matches': int(len(np.unique(pro['rep'])))}, 'models': {}}
    cl_pro = np.unique(pro['rep'], return_inverse=True)[1]
    lab_pro = pro['y_gate'].astype(np.int8)
    dk_pro = deck_key(pro['deck_card'])
    p_pro = {}
    for spec in a.ckpt:
        name, path = spec.split('=', 1)
        try:
            p_pro[name], info = gate_p(Path(path), pro, vocab_, dev)
        except Exception as ex:                                # "if it loads"
            res['models'][name] = {'ckpt': path, 'error': f'{type(ex).__name__}: {ex}'}
            log(name, 'FAILED', ex)
            continue
        res['models'][name] = {'ckpt': path, **info}
        log(name, 'pro p done', info)
    del pro
    names = [n for n, _ in groups(fp)]
    masks = {'all': np.ones(len(lab_pro), bool)}
    if a.sim:
        sim, ngames = load_sim(a.sim, vocab_)
        log('sim decisions', len(sim['sc']), 'games', ngames)
        fs = features(sim['tok'], sim['off'], sim['sc'], sim['opp_past'], sim['tick'], utab, ctab)
        fs['opp_el'] = sim['sc'][:, 5].astype(np.float64) * 10
        masks['deck'] = np.isin(dk_pro, np.unique(deck_key(sim['deck_card'])))
        res['pro'].update(deck_rows=int(masks['deck'].sum()), deck_matches=int(len(np.unique(cl_pro[masks['deck']]))),
                          bot_decks=[[vocab_[int(c)] for c in row] for row in np.unique(np.sort(sim['deck_card'], 1), axis=0)])
        log('bot decks', res['pro']['bot_decks'], 'pro rows with that deck', res['pro']['deck_rows'])
    reps_pro = {}
    for name, p in p_pro.items():
        for sub, m in masks.items():
            res['models'][name][f'pro_{sub}'], reps_pro[(name, sub)] = pro_block(cl_pro, fp, p, lab_pro, m, names)
        log(name, 'pro stats done')
    for sub, m in masks.items():
        res[f'pro_occupancy_{sub}'] = {n: {'n': int(g.sum()), 'share': float(g.mean())}
                                       for n, g in groups({k: v[m] for k, v in fp.items()})}
    if a.sim:
        p, info = gate_p(Path(dict(s.split('=', 1) for s in a.ckpt)[a.sim_model]), sim, vocab_, dev)
        d = np.abs(p - sim['p'])
        res['sim'] = {'dir': str(a.sim), 'games': ngames, 'decisions': int(len(p)), 'model': a.sim_model, **info,
                      'recorded_vs_plain_p': {'max_abs': float(d.max()), 'mean_abs': float(d.mean()),
                                              'share_gt_0.01': float((d > .01).mean())}}
        cl = sim['game']
        s = sim['sampled']
        # pro-style sampled subset: same sampling as the pro rows -> label rates and conditional p comparable
        fss = {k: v[s] for k, v in fs.items()}
        gs = groups(fss)
        pts_s, reps_s = boot(cl[s], gs, stat_cols(fss, p[s], sim['y_gate'][s]), seed=1)
        add_ci(pts_s, reps_s, names)
        res['sim']['sampled'] = pts_s
        res['sim_occupancy_sampled'] = {n: {'n': int(m.sum()), 'share': float(m.mean())} for n, m in gs}
        # every decision: what the deployed stack did
        ga = groups(fs)
        why = sim['why']
        over = p > TAU[fs['ph']]
        pts_a, reps_a = boot(cl, ga, {'p': p, 'over': over.astype(float), 'decided_play': sim['play'].astype(float),
                                      'accepted_play': (sim['play'] & sim['accepted']).astype(float),
                                      'over_but_wait': (over & ~sim['play']).astype(float)}, seed=2)
        add_ci(pts_a, reps_a, names, keys=('p', 'over', 'decided_play'))
        for n, m in ga:
            if m.any():
                u, c = np.unique(why[m], return_counts=True)
                pts_a[n]['why'] = {str(k): int(v) for k, v in zip(u, c)}
        res['sim']['all_decisions'] = pts_a
        res['sim_occupancy_all'] = {n: {'n': int(m.sum()), 'share': float(m.mean())} for n, m in ga}
        if a.sim_model in p_pro:
            for sub in masks:
                res[f'sim_vs_pro_{sub}'] = compare(pts_s, reps_s, res['models'][a.sim_model][f'pro_{sub}'],
                                                   reps_pro[(a.sim_model, sub)], names)
                res[f'balance_{sub}'] = balance(cl_pro, fp, p_pro[a.sim_model], masks[sub], cl, fs, p, s)
        # APPROACH proxy vs econ2's push start, on the SIM decision time series (every ~0.5 s)
        res['approach_validation'] = validate(sim['tick'], sim['game'], fs)
        np.savez_compressed(a.out / 'rows.npz', **{f'pro_{k}': v for k, v in fp.items()}, pro_rep=cl_pro, pro_label=lab_pro,
                            pro_deck=masks['deck'], **{f'pro_p_{k}': v for k, v in p_pro.items()},
                            **{f'sim_{k}': v for k, v in fs.items()}, sim_game=cl, sim_sampled=s, sim_label=sim['y_gate'],
                            sim_play=sim['play'], sim_why=why, sim_p=p, sim_tick=sim['tick'])
    out = a.out / 'pro_eagerness.json'
    out.write_text(json.dumps(res, indent=1))
    log('written', out)


def validate(tick, game, f, ahead=300, before=200):
    """share of APPROACH decisions followed by an econ2 push start within ``ahead`` ticks (precision proxy), the same for
    every context, and the context mix of decisions in the ``before`` ticks before each push start."""
    nxt = np.full(len(tick), np.iinfo(np.int64).max)
    pre = np.zeros(len(tick), bool)
    npush = 0
    for gi in np.unique(game):
        ix = np.flatnonzero(game == gi)
        T = tick[ix]
        ps = np.array(push_starts(T, f['vm'][ix]), np.int64)
        npush += len(ps)
        if len(ps):
            j = np.searchsorted(ps, T, side='right')
            ok = j < len(ps)
            nxt[ix[ok]] = ps[j[ok]] - T[ok]
            pre[ix[ok]] = nxt[ix[ok]] <= before                   # strictly before the next push start
    soon = nxt <= ahead
    out = {'push_starts': npush, 'ahead_ticks': ahead, 'before_ticks': before,
           'p_push_within_ahead_by_ctx': {c: float(soon[f['ctx'] == i].mean()) for i, c in enumerate(CTX)},
           'ctx_mix_before_push': {c: float((f['ctx'][pre] == i).mean()) for i, c in enumerate(CTX)},
           'ctx_mix_overall': {c: float((f['ctx'] == i).mean()) for i, c in enumerate(CTX)}}
    return out


# ------------------------------------------------------------------ report
def fmt(v, pct=True):
    return '-' if v is None else (f'{100 * v:.1f}' if pct else f'{v:.2f}')


def fci(d, k):
    c = d.get(k + '_ci')
    return f"{fmt(d.get(k))} [{fmt(c[0])}, {fmt(c[1])}]" if c else fmt(d.get(k))


def report(a):
    r = json.loads((a.out / 'pro_eagerness.json').read_text())
    P = r['pro']
    L = ['# PRO_EAGERNESS tables (generated by pro_eagerness.py report; all rates in %)', '',
         f"Pro VAL rows {P['rows']:,} from {P['matches']:,} replays (both sides). Bot-deck subset ('deck'): pro rows whose 8 cards "
         f"equal the SIM bot's deck {P.get('bot_decks')}: {P.get('deck_rows', 0):,} rows / {P.get('deck_matches', 0):,} replays.", '',
         '## Definitions', '', '```', r['definitions'].strip(), '```', '']
    keys = [f'{c}|{e}' for c in CTX for e in E_NAMES] + [f'{c}|0-4' for c in CTX] + ['ALL|0-4', 'ALL']
    low = [f'{c}|{e}{ph}' for c in CTX for e in ('0-2', '2-4', '0-4') for ph in ('', '|1x')] + ['ALL|0-4', 'ALL']
    subs = [s for s in ('deck', 'all') if f'pro_occupancy_{s}' in r]
    for name, m in r['models'].items():
        if 'error' in m:
            L += [f'## {name}: did not load', '', f"`{m['ckpt']}`: {m['error']}", '']
            continue
        for sub in subs:
            L += [f"## {name} on pro VAL rows, {sub} (`{m['ckpt']}`, fv{m['feature_version']}, vocab ids missing {m['vocab_missing']})", '',
                  'bucket | n | matches | pro play label | mean p | p - label [95% CI] | share p > tau | (p > tau) - label [CI]',
                  '---|---|---|---|---|---|---|---']
            for k in (keys if sub == 'all' else low):
                d = m[f'pro_{sub}'][k]
                if d['n']:
                    L.append(f"{k} | {d['n']:,} | {d['matches']:,} | {fmt(d['label'])} | {fmt(d['p'])} | {fci(d, 'p_minus_label')} | "
                             f"{fmt(d['over'])} | {fci(d, 'over_minus_label')}")
            L.append('')
    if 'sim' in r:
        s = r['sim']
        L += [f"## {s['model']} on its OWN SIM states ({s['games']:,} games, {s['decisions']:,} decisions, `{s['dir']}`)", '',
              f"Plain-checkpoint p vs the p the deployed (grafted) teacher recorded: {s['recorded_vs_plain_p']}.", '']
        so = r['sim_occupancy_sampled']
        for sub in subs:
            cmp, po = r.get(f'sim_vs_pro_{sub}', {}), r[f'pro_occupancy_{sub}']
            L += [f'### Same model, same bucket: SIM-visited vs pro rows ({sub}), both pro-style sampled', '',
                  'bucket | n pro / sim | occupancy pro / sim | pro label | bot label (SIM) | mean p pro | mean p SIM | p SIM - pro [CI] | '
                  'p>tau pro | p>tau SIM | diff [CI]', '---|---|---|---|---|---|---|---|---|---|---']
            for k in keys + [f'{c}|{e}|1x' for c in CTX for e in ('0-2', '2-4', '0-4')]:
                row = cmp.get(k)
                if not row or 'p' not in row:
                    continue
                ps_, ov, lb = row['p'], row['over'], row['label']
                L.append(f"{k} | {po[k]['n']:,} / {so[k]['n']:,} | {fmt(po[k]['share'])} / {fmt(so[k]['share'])} | {fmt(lb['pro'])} | "
                         f"{fmt(lb['sim'])} | {fmt(ps_['pro'])} | {fmt(ps_['sim'])} | {fmt(ps_['diff'])} [{fmt(ps_['ci'][0])}, {fmt(ps_['ci'][1])}] | "
                         f"{fmt(ov['pro'])} | {fmt(ov['sim'])} | {fmt(ov['diff'])} [{fmt(ov['ci'][0])}, {fmt(ov['ci'][1])}]")
            L += ['', f'#### Decomposition ({sub}), pp: bot label - pro label = fit (p_pro - L_pro) + shift (p_sim - p_pro) + '
                      'decision layer (L_sim - p_sim)', '', 'bucket | metric | fit | shift | decision | total', '---|---|---|---|---|---']
            for k in [x for x in low if not x.startswith('OTHER')]:
                for met in ('p', 'over'):
                    dd = cmp.get(k, {}).get(f'decomp_{met}')
                    if dd:
                        L.append(f"{k} | {'mean p' if met == 'p' else 'p > tau'} | {fmt(dd['fit'])} | {fmt(dd['shift'])} | "
                                 f"{fmt(dd['decision'])} | {fmt(dd['total'])}")
            L += ['', f'#### Shift after reweighting SIM rows to the pro ({sub}) cell mix (elixir .5 x vm x vt x phase)', '',
                  'group | covariates pro / SIM (e, vm, vt, rec, opp_el, share 1x) | support pro / SIM | mean p pro | SIM rew. | diff [CI] | '
                  'p>tau pro | SIM rew. | diff [CI]', '---|---|---|---|---|---|---|---|---']
            for g, b in r.get(f'balance_{sub}', {}).items():
                cv = ', '.join(f"{k} {v[0]:.2f}/{v[1]:.2f}" for k, v in b['covariates_pro_sim'].items())
                q, o = b['p'], b['over']
                L.append(f"{g} | {cv} | {fmt(b['pro_rows_in_support'])} / {fmt(b['sim_rows_in_support'])} | {fmt(q['pro'])} | "
                         f"{fmt(q['sim_reweighted'])} | {fmt(q['diff'])} [{fmt(q['ci'][0])}, {fmt(q['ci'][1])}] | {fmt(o['pro'])} | "
                         f"{fmt(o['sim_reweighted'])} | {fmt(o['diff'])} [{fmt(o['ci'][0])}, {fmt(o['ci'][1])}]")
            L.append('')
        L += ['### Every SIM decision (deployed D3 stack): p, p > tau, decided play, why', '',
              'bucket | n | occupancy | mean p | p > tau | decided play | accepted | p > tau but waited | why', '---|---|---|---|---|---|---|---|---']
        for k in keys:
            d = s['all_decisions'][k]
            if d['n']:
                L.append(f"{k} | {d['n']:,} | {fmt(r['sim_occupancy_all'][k]['share'])} | {fmt(d['p'])} | {fmt(d['over'])} | "
                         f"{fmt(d['decided_play'])} | {fmt(d['accepted_play'])} | {fmt(d['over_but_wait'])} | {d.get('why')}")
        L += ['', '### Context proxy vs econ2 push starts (SIM decision series)', '', '```',
              json.dumps(r['approach_validation'], indent=1), '```', '']
    (a.out / 'PRO_EAGERNESS_tables.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
    print('\n'.join(L))


# ------------------------------------------------------------------ check
def selftest():
    from pipeline import vocab
    val = np.zeros(vocab.N_VOCAB); val[vocab.unit_id('giant')] = 5; val[vocab.unit_id('knight')] = 3
    val[vocab.unit_id('skeletons')] = 1 / 3; val[vocab.unit_id('tesla')] = 4
    bld = np.array([vocab.kind_of(c) == 'building' for c in range(vocab.N_VOCAB)])
    cost = np.array([0, 5, 3, 2]); spell = np.array([False, False, False, True])

    def tk(name, side, y):
        r = np.zeros(14, np.float32); r[0] = vocab.unit_id(name); r[1 + side] = 1; r[5] = y
        return r
    rows = [[],                                                       # QUIET
            [tk('giant', 1, .3)],                                     # APPROACH (recent giant play)
            [tk('giant', 1, .3)],                                     # OTHER: giant on their half, no recent play
            [tk('knight', 1, .6)],                                    # UNDER_ATTACK
            [tk('tesla', 1, .3), tk('skeletons', 1, .6)],             # QUIET (their building ignored, skeleton 0.33)
            [tk('giant', 1, .3), tk('knight', 0, .6)]]                # APPROACH (my own unit does not count)
    off = np.concatenate([[0], np.cumsum([len(r) for r in rows])])
    tok = np.stack([t for r in rows for t in r])
    op = np.zeros((6, 3, 5), np.float32); op[..., 4] = -1
    op[1, 0] = (1, 0, .5, .3, 4.0); op[2, 0] = (1, 0, .5, .3, 20.0); op[5, 0] = (1, 0, .5, .3, 2.0); op[5, 1] = (3, 0, .5, .3, 1.0)
    sc = np.zeros((6, 70), np.float32); sc[:, 3] = [.1, .3, .5, .7, .9, 1.0]
    f = features(tok, off, sc, op, np.array([0, 2399, 2400, 3599, 3600, 5000]), (val, bld), (cost, spell))
    assert f['ctx'].tolist() == [0, 1, 3, 2, 0, 1], f['ctx']
    assert f['eb'].tolist() == [0, 1, 2, 3, 4, 4] and f['ph'].tolist() == [0, 0, 1, 1, 2, 2]
    assert abs(f['rec'][5] - 5) < 1e-9                               # the spell play is not counted
    flat, new = gather(np.array([0, 2, 5, 6]), np.array([2, 0]))
    assert flat.tolist() == [5, 0, 1] and new.tolist() == [0, 1, 3]
    assert push_starts([0, 10, 50, 60, 70, 300], [0, 8, 0, 8, 0, 9]) == [10, 300]
    cl = np.repeat(np.arange(50), 10)
    pts, reps = boot(cl, [('a', np.ones(500, bool))], {'x': np.tile([0., 1.], 250)})
    assert pts['a']['x'] == .5 and abs(np.nanmean(reps['x']) - .5) < .01
    # reweighting: p depends only on elixir; SIM sits at higher elixir -> raw gap, ~0 after reweighting
    rng = np.random.default_rng(0)

    def toy(e):
        n = len(e)
        return dict(e=e, eb=np.digitize(e, [2, 4, 6, 8]).astype(np.int8), ph=np.zeros(n, np.int8), ctx=np.ones(n, np.int8),
                    vm=np.zeros(n), vt=np.full(n, 4.0), rec=np.full(n, 4.0), opp_el=np.zeros(n))
    fp_, fs_ = toy(rng.uniform(0, 4, 20000)), toy(rng.uniform(3, 4, 20000))
    b = balance(np.arange(20000) // 20, fp_, fp_['e'] / 10, np.ones(20000, bool), np.arange(20000) // 20, fs_, fs_['e'] / 10,
                np.ones(20000, bool))['APPROACH|0-4']
    assert abs(b['p']['diff']) < .005 and b['pro_rows_in_support'] < .3, b
    print('selftest ok')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=('run', 'report', 'selftest'))
    ap.add_argument('--pro', type=Path, default=ROOT / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz')
    ap.add_argument('--sim', type=Path, default=None)
    ap.add_argument('--ckpt', action='append', default=[], help='name=path (repeatable)')
    ap.add_argument('--sim-model', default='adapt')
    ap.add_argument('--out', type=Path, default=HERE)
    ap.add_argument('--threads', type=int, default=3)
    a = ap.parse_args()
    if a.mode == 'selftest':
        return selftest()
    if a.mode == 'run':
        run(a)
    report(a)


if __name__ == '__main__':
    main()
