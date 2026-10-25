"""Plan A S1c (owner 2026-10-25): fit the memory-v2 artifacts from the pro memory tables + the live CLX / CLXIII X-Bows.

    icebow/.venv/Scripts/python.exe -B -X utf8 scratchpad/gauntlet/L74/memory/s1c/fit_s1c.py > .../s1c/fit_s1c.out

Samples = OWN reach X-Bows (match_memory: within 13.5 tiles of an alive enemy princess) whose 600-tick lock window closed
before the match's last decision; label = xb_locked (a reach princess lost >= 5 % of its max HP in the window). Split by
MATCH: pro = the dataset's own split (1 = held out: the S3 val replays, both sides of a replay together), live = sha1(log
name) % 5 == 0 held out.
  counter_priors.json  per opponent card, beta-binomial empirical-Bayes shrunk lock rate (strength by method of moments) and
                       its lift vs the base rate, in the CAUSAL deck view (revealed by the opponent before the X-Bow's tick;
                       shrunk to the base) and the answer view (it answered the X-Bow; shrunk to the answered mean);
                       pro TRAIN X-Bows only
  lock_head.json       L2 logistic on standardised match_memory.LOCK_INPUTS (v1 summary + S1c fields + time) at the X-Bow's
                       tick (the X-Bow itself is not visible yet: causal), pro + live TRAIN X-Bows (weight 1 each; the source
                       is reported, not an input); train features use OUT-OF-FOLD priors (5 folds by match), so the head
                       never sees priors fit on its own labels; L2 strength by grouped CV log loss
Report (stdout): the prior tables, held-out AUC / Brier / log loss / calibration / AUC by revealed opponent cards, v2 vs a
v1-only head (SUMMARY_FIELDS + time) with a match-cluster bootstrap CI on the difference, per source.
CAVEAT: every sample is an X-Bow a player CHOSE to place, so P(lock) is conditional on that choice (selection bias): it is
not the lock chance of an X-Bow the policy would place where pros (or CLX) did not."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path[:0] = [str(REPO), str(HERE.parent)]
from pipeline import match_memory as M  # noqa: E402
from pipeline.dataset_gen import checkpoint_gid  # noqa: E402

MEM = REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1.npz'
DATA = REPO / 'icebow/data/pipeline/gen_dataset_v32_fv5.npz'
LOGS = REPO / 'scratchpad/gauntlet/L68/live_reader'
LIVE_KEYS = ('ICEBOW_Mark_CLX_PARITY', 'ICEBOW_Mark_CLXIII_NOLEAK')
LIVE_CACHE = HERE / 'live_tables.npz'
MIN_N, FOLDS, LAMBDAS, BOOT = 30, 5, (1.0, 10.0, 100.0, 1000.0), 1000
C = M._COL


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def h5(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest(), 16)


# ------------------------------------------------------------------------------------------------------------ data
def pro_tables():
    z = np.load(MEM)
    packed = {k[4:]: z[k] for k in z.files if k.startswith('tab_')}
    meta = json.loads(str(z['meta']))
    d = np.load(DATA)
    split, tick, rt = d['split'], d['tick'].astype(np.int64), z['row_tab']
    nt = len(packed['off']) - 1
    tsplit = np.full(nt, -1, np.int64)
    np.maximum.at(tsplit, rt, split)                      # all rows of a table share its replay's split (checked: 0 mixed)
    end = np.full(nt, -1, np.int64)
    np.maximum.at(end, rt, tick)                          # the table's last decision row = the match end (conservative)
    return packed, meta['card_vocab'], dict(group=[str(t) for t in z['table_tag']], split=tsplit, end=end,
                                            src=['pro'] * nt)


def live_tables(gid):
    """Every complete live log of LIVE_KEYS -> its match_memory table (in the pro vocabulary), cached (the logs are read
    once: ~2 s each)."""
    if LIVE_CACHE.exists():
        z = np.load(LIVE_CACHE)
        info = json.loads(str(z['info']))
        return {k[4:]: z[k] for k in z.files if k.startswith('tab_')}, info
    import live_dump as LD
    tabs, info = [], dict(group=[], end=[], key=[], sha256=[])
    for f in sorted(LOGS.glob('live_play_*.jsonl')):
        key = None
        with open(f, 'rb') as fh:
            for _, raw in zip(range(400), fh):
                if b'"event": "start"' in raw[:60]:
                    key = next((k for k in LIVE_KEYS if k.encode() in raw), None)
                    break
        if key is None:
            continue
        try:
            m = LD.read(f)
        except Exception as exc:                          # a truncated / odd log: skipped, named
            print(f'live skip {f.name}: {exc!r}'[:160], file=sys.stderr)
            continue
        if m['end'] is None or not m['samples']:
            continue
        tabs.append(M.build(m['side'], m['samples'], m['plays']).table(gid))
        info['group'].append(f.name)
        info['end'].append(int(m['samples'][-1]['tick']))
        info['key'].append(key)
        info['sha256'].append(sha256(f))
    packed = M.pack(tabs)
    np.savez_compressed(LIVE_CACHE, info=json.dumps(info), **{'tab_' + k: v for k, v in packed.items()})
    return packed, info


def concat(a, b):
    out = {k: np.concatenate([a[k], b[k]]) for k in M.TABLE_KEYS}
    out['off'] = np.concatenate([a['off'], b['off'][1:] + a['off'][-1]])
    return out


def samples(packed, T):
    """Own reach X-Bows with a closed window -> dict of arrays (+ the opponent cards revealed before each)."""
    off, vals, flag, tick = packed['off'], packed['vals'], packed['flag'].astype(np.int64), packed['tick'].astype(np.int64)
    tab = np.repeat(np.arange(len(off) - 1), np.diff(off))
    end, split = np.asarray(T['end'])[tab], np.asarray(T['split'])[tab]
    ok = ((flag & 1) > 0) & (vals[:, C['xb_reach']] == 1) & (tick + M.XB_WINDOW <= end) & (split >= 0)
    ev = np.flatnonzero(ok)
    opp = (vals[:, C['is_play']] == 1) & (vals[:, C['mine']] == 0) & (packed['card'] > 0)
    deck = []
    for e in ev:
        a = off[tab[e]]
        o = np.flatnonzero(opp[a:off[tab[e] + 1]] & (packed['vis'][a:off[tab[e] + 1]] <= tick[e]))
        deck.append(sorted({int(c) for c in packed['card'][a + o]}))
    return dict(ev=ev, tab=tab[ev], tick=tick[ev], y=(vals[ev, C['xb_locked']] == 1).astype(np.int64),
                ans=np.where((flag[ev] & 4) > 0, packed['ans_card'][ev].astype(np.int64), 0), deck=deck,
                split=split[ev], group=[T['group'][j] for j in tab[ev]], src=[T['src'][j] for j in tab[ev]])


# ------------------------------------------------------------------------------------------------------------ priors
def fit_priors(S, idx, vocab):
    """Shrunk per-card lock lifts on samples ``idx`` (order-free: integer counts, cards in id order) -> the JSON dict."""
    idx = np.sort(np.asarray(idx, np.int64))
    y = S['y'][idx]
    p0 = int(y.sum()) / len(idx)
    answered = idx[S['ans'][idx] > 0]
    p_ans = int(S['y'][answered].sum()) / max(len(answered), 1)
    views = {}
    for view, mu in (('deck', p0), ('answer', p_ans)):
        n, k = Counter(), Counter()
        for i in idx:
            for c in (S['deck'][i] if view == 'deck' else [int(S['ans'][i])] if S['ans'][i] else []):
                n[c] += 1
                k[c] += int(S['y'][i])
        cs = sorted(c for c in n if n[c] >= MIN_N)
        r, nn = np.array([k[c] / n[c] for c in cs]), np.array([n[c] for c in cs], np.float64)
        tau2 = max(float(np.mean((r - mu) ** 2) - np.mean(mu * (1 - mu) / nn)), 1e-6) if cs else None
        views[view] = (n, k, mu, max(mu * (1 - mu) / tau2 - 1.0, 1.0) if cs else float(MIN_N))   # no card >= MIN_N: m = MIN_N
    cards = {}
    for c in sorted(set(views['deck'][0]) | set(views['answer'][0])):
        row = {}
        for view, (n, k, mu, m) in views.items():
            rate = (k[c] + m * mu) / (n[c] + m)
            row[view] = {'n': n[c], 'k': k[c], 'rate': round(rate, 6), 'lift': round(rate - p0, 6)}
        cards[vocab[c]] = row
    return {'base': round(p0, 6), 'answered_mean': round(p_ans, 6), 'n_xbows': int(len(idx)),
            'strength': {v: round(t[3], 3) for v, t in views.items()}, 'min_n_for_strength': MIN_N, 'cards': cards}


# ------------------------------------------------------------------------------------------------------------ features
def features(packed, S, idx, lut, gid, chunk=1024):
    """LOCK_INPUTS rows at the X-Bows ``idx`` (their own tick: the X-Bow is not yet visible) with priors ``lut``."""
    out = []
    for s in range(0, len(idx), chunk):
        j = idx[s:s + chunk]
        E = M.gather_rows(packed, S['tab'][j])
        t = S['tick'][j]
        s14 = M._features_v1(E, t, np.zeros((len(j), 0), np.int64))['mem_summary'][:, :len(M.SUMMARY_FIELDS)]
        out.append(M.lock_x(s14, M._s1c(E, t, s14, lut, None), t))
    return np.concatenate(out) if out else np.zeros((0, len(M.LOCK_INPUTS)))


# ------------------------------------------------------------------------------------------------------------ model
def fit_logit(X, y, lam, it=100):
    mu, sd = X.mean(0), X.std(0)
    sd = np.where(sd < 1e-9, 1.0, sd)
    Z = np.concatenate([(X - mu) / sd, np.ones((len(X), 1))], 1)
    pen = np.full(Z.shape[1], lam)
    pen[-1] = 0.0
    beta = np.zeros(Z.shape[1])
    for _ in range(it):
        p = 1 / (1 + np.exp(-(Z @ beta)))
        step = np.linalg.solve(Z.T @ (Z * (p * (1 - p))[:, None]) + np.diag(pen), Z.T @ (p - y) + pen * beta)
        beta -= step
        if np.abs(step).max() < 1e-10:
            break
    return {'mean': mu, 'std': sd, 'w': beta[:-1], 'b': np.float64(beta[-1])}


def auc(y, p):
    order = np.argsort(p, kind='stable')
    ps = p[order]
    ranks = np.empty(len(p))
    _, first, cnt = np.unique(ps, return_index=True, return_counts=True)
    ranks[order] = np.repeat(first + (cnt + 1) / 2.0, cnt)       # average ranks for ties, 1-based
    n1 = int(y.sum())
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float('nan')


def metrics(y, p):
    q = np.clip(p, 1e-9, 1 - 1e-9)
    return dict(n=int(len(y)), lock=round(float(y.mean()), 4), auc=round(auc(y, p), 4),
                brier=round(float(np.mean((p - y) ** 2)), 4), logloss=round(float(-np.mean(y * np.log(q) + (1 - y) * np.log(1 - q))), 4),
                mean_p=round(float(p.mean()), 4))


def cv_lambda(X, y, folds):
    best = None
    for lam in LAMBDAS:
        ll = []
        for k in range(FOLDS):
            tr, va = folds != k, folds == k
            h = fit_logit(X[tr], y[tr], lam)
            p = np.clip(M.lock_p(h, X[va]), 1e-9, 1 - 1e-9)
            ll.append(-np.sum(y[va] * np.log(p) + (1 - y[va]) * np.log(1 - p)))
        score = sum(ll) / len(y)
        print(f'  lambda {lam:7.1f}: CV log loss {score:.4f}')
        if best is None or score < best[1]:
            best = (lam, score)
    return best[0]


def boot(y, pa, pb, groups, rng):
    """Match-cluster bootstrap of (AUC, Brier) of a minus b -> 95 % intervals."""
    g = np.unique(groups, return_inverse=True)[1]
    members = [np.flatnonzero(g == i) for i in range(g.max() + 1)]
    da, db = [], []
    for _ in range(BOOT):
        s = np.concatenate([members[i] for i in rng.integers(0, len(members), len(members))])
        da.append(auc(y[s], pa[s]) - auc(y[s], pb[s]))
        db.append(np.mean((pa[s] - y[s]) ** 2) - np.mean((pb[s] - y[s]) ** 2))
    q = (lambda v: [round(float(np.nanpercentile(v, 2.5)), 4), round(float(np.nanpercentile(v, 97.5)), 4)])
    return q(da), q(db)


# ------------------------------------------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='write counter_priors.json + lock_head.json (else report only)')
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    pp, vocab, PT = pro_tables()
    gid = checkpoint_gid(vocab)
    lp, LT = live_tables(gid)
    nlive = len(lp['off']) - 1
    LT = dict(LT, split=[int(h5(g) % 5 == 0) for g in LT['group']], src=['live'] * nlive)
    packed = concat(pp, lp)
    T = {k: list(PT[k]) + list(LT[k]) for k in ('group', 'split', 'end', 'src')}
    S = samples(packed, T)
    src = np.array(S['src'])
    train, test = np.flatnonzero(S['split'] == 0), np.flatnonzero(S['split'] == 1)
    pro_train = train[src[train] == 'pro']
    print(f'tables: pro {len(pp["off"]) - 1} (no rows / no split: {int((PT["split"] < 0).sum())}), live {nlive} '
          f'({Counter(LT["key"])})')
    print(f'own reach X-Bows with a closed window: {len(S["y"])} (pro {int((src == "pro").sum())}, live '
          f'{int((src == "live").sum())}); train {len(train)} (pro {len(pro_train)}), held out {len(test)} '
          f'(pro {int((src[test] == "pro").sum())}, live {int((src[test] == "live").sum())})')
    for s_ in ('pro', 'live'):
        m = src == s_
        print(f'  {s_}: lock {S["y"][m].mean():.3f}, answered {np.mean(S["ans"][m] > 0):.3f}, lock when answered '
              f'{S["y"][m & (S["ans"] > 0)].mean():.3f}, unanswered {S["y"][m & (S["ans"] == 0)].mean():.3f}')

    pri = fit_priors(S, pro_train, vocab)
    print(f'\n## counter priors (pro train X-Bows {pri["n_xbows"]}): base {pri["base"]}, answered mean '
          f'{pri["answered_mean"]}, EB strength (pseudo X-Bows) {pri["strength"]}')
    for view in ('answer', 'deck'):
        rows = sorted(((v[view]['lift'], k, v[view]['n'], v[view]['k']) for k, v in pri['cards'].items() if v[view]['n']),
                      key=lambda r: (r[0], r[1]))
        print(f'  {view.upper()} view: {len(rows)} cards; most X-Bow-denying (lowest shrunk lift) / most X-Bow-friendly:')
        for r in rows[:10] + [None] + rows[-10:]:
            print('    ...' if r is None else f'    {r[1]:24s} n {r[2]:5d} raw {r[3] / r[2]:.3f} shrunk lift {r[0]:+.3f}')
        if view == 'answer':
            lifts = np.array([r[0] for r in rows if r[2] >= MIN_N])
            print(f'  answer lifts (n >= {MIN_N}): quantiles 10/25/50/75/90 % '
                  f'{np.round(np.percentile(lifts, [10, 25, 50, 75, 90]), 3).tolist()}; counters (lift < '
                  f'{M.COUNTER_LIFT}): {sum(r[0] < M.COUNTER_LIFT for r in rows)} cards: '
                  f'{[r[1] for r in rows if r[0] < M.COUNTER_LIFT]}')

    folds = np.array([h5(g) % FOLDS for g in S['group']])
    X = np.zeros((len(S['y']), len(M.LOCK_INPUTS)))
    for k in range(FOLDS):                                 # out-of-fold priors for the train rows
        rows = train[folds[train] == k]
        lut = M.v2_lut(gid, fit_priors(S, pro_train[folds[pro_train] != k], vocab))
        X[rows] = features(packed, S, rows, lut, gid)
    X[test] = features(packed, S, test, M.v2_lut(gid, pri), gid)
    y = S['y']
    v1c = list(range(len(M.SUMMARY_FIELDS))) + list(range(len(M.LOCK_INPUTS) - 4, len(M.LOCK_INPUTS)))
    print('\n## lock head: L2 by grouped 5-fold CV on train (v2 inputs)')
    lam = cv_lambda(X[train], y[train], folds[train])
    print('  v1-only inputs:')
    lam1 = cv_lambda(X[train][:, v1c], y[train], folds[train])
    h2, h1 = fit_logit(X[train], y[train], lam), fit_logit(X[train][:, v1c], y[train], lam1)
    p2, p1 = M.lock_p(h2, X), M.lock_p(h1, X[:, v1c])
    base = np.full(len(y), y[train].mean())
    nrev = np.round(X[:, M.LOCK_INPUTS.index('opp_revealed_8')] * 8).astype(int)
    groups = np.array(S['group'])
    print(f'  chosen lambda: v2 {lam}, v1-only {lam1}')
    for name, sel in (('HELD OUT pooled', test), ('HELD OUT pro', test[src[test] == 'pro']),
                      ('HELD OUT live', test[src[test] == 'live']), ('train (in-sample)', train)):
        if not len(sel):
            continue
        print(f'\n## {name}')
        for nm, p in (('v2', p2), ('v1-only', p1), ('base rate', base)):
            print(f'  {nm:9s} {metrics(y[sel], p[sel])}')
        if name.startswith('HELD'):
            da, db = boot(y[sel], p2[sel], p1[sel], groups[sel], rng)
            print(f'  v2 - v1: AUC {auc(y[sel], p2[sel]) - auc(y[sel], p1[sel]):+.4f} 95% CI {da}; Brier '
                  f'{np.mean((p2[sel] - y[sel]) ** 2) - np.mean((p1[sel] - y[sel]) ** 2):+.4f} 95% CI {db} '
                  f'(match-cluster bootstrap, {BOOT})')
            print('  by revealed opponent cards at the X-Bow:  bin  n  lock  AUC v2  AUC v1  Brier v2  Brier v1')
            for lo, hi in ((0, 1), (2, 3), (4, 5), (6, 7), (8, 99)):
                b = sel[(nrev[sel] >= lo) & (nrev[sel] <= hi)]
                if len(b):
                    print(f'    {lo}-{min(hi, 8)} {len(b):5d} {y[b].mean():.3f}  {auc(y[b], p2[b]):.3f}   {auc(y[b], p1[b]):.3f}'
                          f'   {np.mean((p2[b] - y[b]) ** 2):.4f}    {np.mean((p1[b] - y[b]) ** 2):.4f}')
            print('  calibration (v2, predicted-p bins): bin  n  mean p  observed')
            for lo in np.arange(0, 1, 0.1):
                b = sel[(p2[sel] >= lo) & (p2[sel] < lo + 0.1)]
                if len(b):
                    print(f'    [{lo:.1f},{lo + .1:.1f}) {len(b):5d}  {p2[b].mean():.3f}  {y[b].mean():.3f}')
    ci, ce = M.LOCK_INPUTS.index('ctr_known'), M.LOCK_INPUTS.index('ctr_cycle_el_10')
    cp = M.LOCK_INPUTS.index('ctr_plays_4')
    k = test[X[test, ci] == 1]
    if len(k):
        far = X[k, cp] > 0
        el = X[k, ce][far] * 10
        print(f'\n## counter cycle at held-out X-Bows with a revealed counter (n {len(k)} of {len(test)}): plays to a counter '
              f'in hand 0/1/2/3/4: {np.bincount(np.round(X[k, cp] * 4).astype(int), minlength=5).tolist()}; when not in '
              f'hand (n {int(far.sum())}): elixir to cycle there median {np.median(el):.1f}, mean {el.mean():.2f}, share <= 9 '
              f'(icebow\'s cheapest 4-card cycle: Skeletons + Log + Knight + Ice Wizard / Tornado) {np.mean(el <= 9):.3f}; '
              f'lock with the counter in hand {y[k][~far].mean():.3f} vs not {y[k][far].mean():.3f} (association)')
    order = np.argsort(-np.abs(h2['w']))[:12]
    print('\n## v2 head: largest standardised weights: ' + ', '.join(f'{M.LOCK_INPUTS[i]} {h2["w"][i]:+.3f}' for i in order))
    print('\nCAVEAT: trained on X-Bows players CHOSE to place (selection bias); P(lock) is conditional on that choice.')
    if not a.write:
        return
    srcs = {'memory_tables': {'path': str(MEM.relative_to(REPO)), 'sha256': sha256(MEM)},
            'dataset': {'path': str(DATA.relative_to(REPO)), 'sha256': sha256(DATA)}}
    pri_out = {'meta': {'kind': 'match_memory_v2_counter_priors', 'by': 'scratchpad/gauntlet/L74/memory/s1c/fit_s1c.py',
                        'sources': srcs, 'samples': 'own reach X-Bows, closed 600-tick window, pro dataset split 0',
                        'views': {'deck': 'the opponent revealed the card before the X-Bow tick (causal); shrunk to base',
                                  'answer': 'the card answered the X-Bow (lane, 4 s, 12 tiles); shrunk to answered_mean'},
                        **{k: v for k, v in pri.items() if k != 'cards'}},
               'cards': pri['cards']}
    M.PRIORS.write_text(json.dumps(pri_out, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    live_logs = sorted(zip(LT['group'], LT['sha256']))
    chk = test[:4]
    head = {'meta': {'kind': 'match_memory_v2_lock_head', 'by': 'scratchpad/gauntlet/L74/memory/s1c/fit_s1c.py',
                     'sources': dict(srcs, live_logs={'n': len(live_logs), 'keys': list(LIVE_KEYS),
                                                      'sha256_of_name_sha_list': hashlib.sha256(
                                                          json.dumps(live_logs).encode()).hexdigest()},
                                     counter_priors_sha256=hashlib.sha256(M.PRIORS.read_bytes()).hexdigest()),
                     'n_train': int(len(train)), 'n_train_live': int((src[train] == 'live').sum()), 'lambda': lam,
                     'held_out': metrics(y[test], p2[test]), 'held_out_v1_only': metrics(y[test], p1[test]),
                     'caveat': 'selection bias: X-Bows players chose to place'},
            'inputs': list(M.LOCK_INPUTS), 'mean': h2['mean'].tolist(), 'std': h2['std'].tolist(), 'w': h2['w'].tolist(),
            'b': float(h2['b']), 'check_x': X[chk].tolist(), 'check_p': M.lock_p(h2, X[chk]).tolist()}
    M.LOCK_HEAD.write_text(json.dumps(head, indent=1) + '\n', encoding='utf-8')
    print(f'wrote {M.PRIORS.name} {M.v2_meta()}')


if __name__ == '__main__':
    main()
