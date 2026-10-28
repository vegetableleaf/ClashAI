"""P2-SCORE v5: the ALL-MATCHES live human reference (owner 10-28: the B-live rule and the C-live limit are set from every
recorded live match, weighted toward recent matches).  The sealed block is never opened: every step tests the log NAME first
(card.block_of) and the reference stops at live_split.json's sealed_from.

    python -I allref.py scan                       # laptop, light: start-event metadata of every non-sealed log -> data/live_meta.jsonl
    python -I allref.py parse --logs DIR --list F  # pod: live_table.cached on the listed logs -> opp_model/cache
    python -I allref.py build                      # LT caches + meta -> data/allref_v5.json.gz (records + 25-stat rows, both decks)
    python -I allref.py shift                      # reader / Mark shift tests vs placebo boundaries -> out/v5_shift.json|txt (masks)
    python -I allref.py bnull --half-life 7 --n-sim 1900 --draws 1000      # B-live human null at the scored n -> out/v5_bnull.json
    python -I allref.py cnull --seeds 0 1 2 ...    # C-live human null draws -> out/v5_cnull/SEED.json (fresh discriminator each)
    python -I allref.py csum                       # aggregate the C null -> out/v5_cnull.json

Reference rule (pre-registered in THRESHOLDS v5): every non-sealed, non-dry live_play log of the ICEBOW deck (all Marks, both
accounts) with public frames and >= 3 detected opponent plays; weight w = 0.5 ** (age_days / half_life) with age measured
back from sealed_from; a stat the shift test flags at boundary b is NaN for matches before b (dropped, not corrected).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
import random
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import card as CD  # noqa: E402

REG = CD.L74 / 'models/registry.json'
LTC = CD.L74 / 'opp_model/cache'
META = HERE / 'data' / 'live_meta.jsonl'
REF = HERE / 'data' / 'allref_v5.json.gz'
OUT = HERE / 'out'
SEALED = CD.SPLIT['sealed_from']
T_SEAL = datetime.strptime(SEALED, '%Y%m%d_%H%M%S')
# reader eras (logs' start event cue_inputs.reader + the 10-27 game-build port: live gap 04:26 -> 06:58, HANDOFF_1028 / STATUS 10-27 05:22)
ERAS = [('v2', '20261017_132941'), ('merged_a', '20261027_050000'), ('merged_b', '20261028_075349'), ('sf', SEALED[:15])]
CLX, C3 = 'ICEBOW Mark CLX: PARITY', 'ICEBOW Mark CLXIII: NOLEAK'
# boundary tests, time order: (name, ts, kind, mark filter before, mark filter after)
BOUNDS = [('T1 reader v2 -> merged (+ Mark CXXXVIII)', '20261017_132941', 'reader', None, None),
          ('M0 Mark CLIX -> CLX (Ranked from 10-19)', '20261019_002011', 'mark', None, CLX),
          ('M1 Mark CLX -> CLXIII', '20261025_084914', 'mark', CLX, C3),
          ('T2 game build 160635001 + reader port', '20261027_050000', 'reader', C3, C3),
          ('T3 reader merged -> merged_sf', '20261028_075349', 'reader', C3, C3)]
# placebo boundaries (no known change; one Mark, one reader era): the window is split at its median match
PLACEBO = [('XCVIII', 'ICEBOW Mark XCVIII: TOWERREFINE', '20261008', '20261015'), ('CXII', 'ICEBOW Mark CXII: PLAINIW', '20261013', '20261016'),
           ('CXXIV', 'ICEBOW Mark CXXIV: LONGER', '20261015', '20261017_132941'), ('CLX', CLX, '20261019_002011', '20261021_142818'),
           ('CLXIII a', C3, '20261025', '20261027_050000'), ('CLXIII b', C3, '20261027_050000', '20261028_075349')]
NWIN = 300


def _start(path):
    with open(path, 'rb') as fh:
        for _, raw in zip(range(400), fh):
            if raw.startswith(b'{"event": "start"'):
                return json.loads(raw)
    return None


def scan(out):
    reg = json.loads(REG.read_text())
    sha2mark = {f['sha256']: m['name'] for m in reg['marks'] for f in m.get('files', []) if f.get('sha256')}
    n = 0
    with open(out, 'w') as fo:
        for e in sorted(os.scandir(CD.LOGS), key=lambda e: e.name):
            if not (e.name.startswith('live_play_') and e.name.endswith('.jsonl')):
                continue
            stem = e.name[:-6]
            b = CD.block_of(stem)
            if b == 'sealed':
                continue                                  # name test first: the sealed block is never opened
            s = _start(e.path) or {}
            ck = str(s.get('ckpt') or '')
            sha = s.get('ckpt_sha256') or ''
            mark = sha2mark.get(sha) or Path(ck.replace('\\', '/')).name
            cue = s.get('cue_inputs') if isinstance(s.get('cue_inputs'), dict) else {}
            fo.write(json.dumps(dict(stem=stem, block=b, size=e.stat().st_size, has_start=bool(s), dry=bool(s.get('dry_run')),
                                     sha=sha[:8], mark=mark,
                                     deck='bait' if (mark.startswith('Bait') or 'bait' in ck.lower()) else 'icebow',
                                     reader=(cue or {}).get('reader'), cue_active=(cue or {}).get('active'))) + '\n')
            n += 1
    print('scanned', n, '->', out)


def parse(logs, lst):
    import live_table as LT
    names = [x.strip() for x in open(lst) if x.strip()]
    bad = [x for x in names if CD.block_of(x) == 'sealed']
    if bad:
        raise SystemExit(f'refusing: {len(bad)} sealed-block logs in the list')
    for i, nm in enumerate(names):
        d = LT.cached(Path(logs) / (nm + '.jsonl'))
        if i % 50 == 0:
            print(i, nm, 'none' if d is None else len(d['plays']), flush=True)
    print('parsed', len(names))


def era(ts):
    return next(name for name, b in ERAS if ts < b)


def _nan(o):
    return None if isinstance(o, float) and math.isnan(o) else o


def build():
    cache, out = LTC, REF
    meta = [json.loads(x) for x in open(META)]
    recs, why = [], {}
    for m in meta:
        st = m['stem']
        if CD.block_of(st) == 'sealed' or m['block'] == 'sealed':
            continue
        if not m['has_start'] or m['dry']:
            why['dry_or_no_start'] = why.get('dry_or_no_start', 0) + 1
            continue
        c = Path(cache) / (st + '.json.gz')
        if not c.exists():
            why['no_cache'] = why.get('no_cache', 0) + 1
            continue
        d = json.loads(gzip.decompress(c.read_bytes()))
        if d.get('none') or d.get('v') != 2 or not d.get('start') or d['start'].get('dry'):
            why['no_public_frames'] = why.get('no_public_frames', 0) + 1
            continue
        if len(d['plays']) < 3:
            why['lt3_plays'] = why.get('lt3_plays', 0) + 1
            continue
        own = [t + CD.LIVE_OFF for k, t in d['falls'].items() if k.startswith('own_P')]
        ts = st[10:25]
        recs.append(dict(src='live', id=st + '.jsonl', t0=d['t0'], end=d['end'], side=d['side'], plays=d['plays'], mine=d['mine'],
                         seen=d['seen'], own_fall=min(own) if own else None, xb=None, xbt=None, arch=CD.arch2(d['seen']),
                         ts=ts, mark=m['mark'], sha=m['sha'], deck=m['deck'], reader=m['reader'], era=era(ts),
                         age_d=round((T_SEAL - datetime.strptime(ts, '%Y%m%d_%H%M%S')).total_seconds() / 86400, 5)))
    rows = CD.rows(recs)
    keep = [k for k in rows[0] if not k.startswith('_')] if rows else []
    rows = [{**{k: _nan(x[k]) for k in keep}, '_arch': x['_arch'], '_pos': True} for x in rows]
    ice = sorted(r['id'] for r in recs if r['deck'] == 'icebow')
    meta_out = dict(built=datetime.now().isoformat(timespec='seconds'), sealed_from=SEALED, n=len(recs), n_icebow=len(ice),
                    stems_sha256=hashlib.sha256('\n'.join(ice).encode()).hexdigest(), skipped=why, eras=ERAS)
    out.write_bytes(gzip.compress(json.dumps(dict(meta=meta_out, records=recs, rows=rows)).encode()))
    print(json.dumps(meta_out))


def load(deck='icebow'):
    d = json.loads(gzip.decompress(REF.read_bytes()))
    pairs = [(r, x) for r, x in zip(d['records'], d['rows']) if deck is None or r['deck'] == deck]
    for _, x in pairs:
        for k in CD.STATS:
            if x.get(k) is None:
                x[k] = float('nan')
    return d['meta'], [p[0] for p in pairs], [p[1] for p in pairs]


# ------------------------------------------------------------------ shift tests
def _d(a, b):
    c = CD.SC.cohen(a, b, CD.STATS, 5)
    return {k: (c[k][6], c[k][7], c[k][0], c[k][3]) for k in CD.STATS}


def shift():
    meta, R, X = load(None)
    I = [(r, x) for r, x in zip(R, X) if r['deck'] == 'icebow']
    res = dict(bounds={}, placebo={}, deck={})
    for name, mk, lo, hi in PLACEBO:
        w = [(r, x) for r, x in I if r['mark'] == mk and lo <= r['ts'] < hi]
        h = len(w) // 2
        a, b = w[max(0, h - NWIN):h], w[h:h + NWIN]
        res['placebo'][name] = dict(n=(len(a), len(b)), split=w[h][0]['ts'] if w else None, d=_d([x for _, x in a], [x for _, x in b]))
    ex = [v[0] ** 2 - v[1] ** 2 for p in res['placebo'].values() for v in p['d'].values() if v[0] == v[0]]
    tau2 = max(0.0, sum(ex) / len(ex))
    masks = {}
    for name, ts, kind, mb, ma in BOUNDS:
        a = [x for r, x in I if r['ts'] < ts and (mb is None or r['mark'] == mb)][-NWIN:]
        b = [x for r, x in I if r['ts'] >= ts and (ma is None or r['mark'] == ma)][:NWIN]
        dd = _d(a, b)
        flag = {k: bool(v[0] == v[0] and abs(v[0]) > 1.96 * math.sqrt(v[1] ** 2 + tau2)) for k, v in dd.items()}
        res['bounds'][name] = dict(ts=ts, kind=kind, n=(len(a), len(b)), d=dd, flag=flag,
                                   mdd=1.96 * math.sqrt(1 / max(1, len(a)) + 1 / max(1, len(b)) + tau2))
        for k, f in flag.items():
            if f:
                masks[k] = max(masks.get(k, ''), ts)            # drop everything before the LATEST boundary that moves the stat
    # deck (information, not a mask: the bait deck is outside the reference by rule): bait vs icebow matches of the same days
    bd = [x for r, x in zip(R, X) if r['deck'] == 'bait' and r['ts'] < '20261021']
    days = {r['ts'][:8] for r, x in zip(R, X) if r['deck'] == 'bait'}
    ic = [x for r, x in I if r['ts'][:8] in days and r['ts'] < '20261021']
    res['deck'] = dict(n=(len(ic), len(bd)), d=_d(ic, bd))
    res['tau2'], res['masks'] = tau2, masks
    OUT.mkdir(exist_ok=True)
    (OUT / 'v5_shift.json').write_text(json.dumps(res, indent=1, default=str))
    L = [f'v5 shift tests (per-stat Cohen d, after - before; {NWIN} matches max per side; flag = |d| > 1.96 sqrt(SE^2 + tau^2), '
         f'tau^2 = placebo excess variance {tau2:.5f} (tau {math.sqrt(tau2):.3f}))']
    hdr = 'stat'.ljust(15) + ''.join(n.split()[0].rjust(8) for n, *_ in BOUNDS) + ''.join(('P:' + n)[:8].rjust(9) for n, *_ in PLACEBO) + '   deck'
    L.append(hdr)
    for k in CD.STATS:
        s = k.ljust(15)
        for n, *_ in BOUNDS:
            v = res['bounds'][n]['d'][k][0]
            s += (f'{v:+.2f}' + ('*' if res['bounds'][n]['flag'][k] else ' ')).rjust(8) if v == v else '     nan'
        for n, *_ in PLACEBO:
            v = res['placebo'][n]['d'][k][0]
            s += (f'{v:+.2f}'.rjust(9) if v == v else '      nan')
        v = res['deck']['d'][k][0]
        L.append(s + (f'{v:+.2f}'.rjust(7) if v == v else '    nan'))
    for n, *_ in BOUNDS:
        b = res['bounds'][n]
        L.append(f'{n}: n before/after {b["n"]}, smallest flaggable |d| {b["mdd"]:.2f}, flagged {[k for k, f in b["flag"].items() if f]}')
    L.append('placebo n: ' + ', '.join(f'{n} {p["n"]} split {p["split"]}' for n, p in res['placebo'].items()))
    L.append(f'deck (bait - icebow, same days < 10-21): n {res["deck"]["n"]}')
    L.append(f'MASKS (stat: dropped for matches before ts): {json.dumps(masks)}')
    (OUT / 'v5_shift.txt').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


# ------------------------------------------------------------------ the human nulls at the scored n
def weighted(half_life, masks):
    meta, R, X = load('icebow')
    for r, x in zip(R, X):
        r['w'] = x['_w'] = 0.5 ** (r['age_d'] / half_life)
        for k, b in masks.items():
            if r['ts'] < b:
                x[k] = float('nan')
    return meta, R, X


def neff(ws):
    return sum(ws) ** 2 / sum(w * w for w in ws)


def _draw(rng, cum, n):
    import bisect
    tot = cum[-1]
    return [bisect.bisect_left(cum, rng.random() * tot) for _ in range(n)]


def bnull(th, half_life, n_sim, draws, seed=0):
    masks = th['B'].get('live_reference', {}).get('masks') or json.loads((OUT / 'v5_shift.json').read_text())['masks']
    meta, R, X = weighted(half_life, masks)
    ws = [x['_w'] for x in X]
    ne = neff(ws)
    cum, s = [], 0.0
    for w in ws:
        s += w
        cum.append(s)
    rng = random.Random(seed)
    z = CD.SC.Z90
    out = []
    for i in range(draws):
        Ri = [dict(X[j], _w=1.0) for j in _draw(rng, cum, round(ne))]
        Mi = [X[j] for j in _draw(rng, cum, n_sim)]
        b = CD.level_b(Ri, Mi, th)
        tmax = max(abs(b['stats'][k][6]) + z * b['stats'][k][7] for k in b['have'])
        out.append(dict(rms=b['rms'], tost_max=tmax, b3=b['pass_b3'], tost=b['pass_tost'], rms_ok=b['pass_rms'], full=b['passed']))
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
    per = {k: neff([x['_w'] for x in X if x[k] == x[k]]) for k in CD.STATS}
    res = dict(half_life=half_life, n_sim=n_sim, draws=draws, n_matches=len(X), neff=ne, neff_per_stat=per, masks=masks,
               pass_full=sum(o['full'] for o in out) / draws, pass_rms=sum(o['rms_ok'] for o in out) / draws,
               pass_tost=sum(o['tost'] for o in out) / draws, pass_b3=sum(o['b3'] for o in out) / draws,
               rms_q95=q([o['rms'] for o in out], .95), rms_q50=q([o['rms'] for o in out], .5),
               tost_max_q95=q([o['tost_max'] for o in out], .95), tost_max_q50=q([o['tost_max'] for o in out], .5),
               sens={str(h): neff([0.5 ** (r['age_d'] / h) for r in R]) for h in (3.5, 7, 14, 1e9)},
               limits_used=dict(rms=th['B']['b_live_rms_d_max'], tost=th['B']['b_live_per_stat_abs_d_max']))
    OUT.mkdir(exist_ok=True)
    (OUT / 'v5_bnull.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != 'neff_per_stat'}, indent=1))
    return res


def cnull(th, half_life, n_sim, seeds, threads=4):
    import disc
    masks = th['B'].get('live_reference', {}).get('masks') or json.loads((OUT / 'v5_shift.json').read_text())['masks']
    meta, R, X = weighted(half_life, masks)
    d = OUT / 'v5_cnull'
    d.mkdir(parents=True, exist_ok=True)
    for sd in seeds:
        rng = random.Random(1000 + sd)
        idx = list(range(len(R)))
        rng.shuffle(idx)
        A, B = idx[:len(idx) // 2], idx[len(idx) // 2:]
        H = [R[i] for i in A]                                              # weighted human class (as in scoring)
        cum, s = [], 0.0
        for i in B:
            s += R[i]['w']
            cum.append(s)
        M = [{k: v for k, v in R[B[j]].items() if k != 'w'} for j in _draw(rng, cum, n_sim)]   # humans drawn as a fake model
        r = disc.train_eval(H, M, seed=sd, threads=threads)
        (d / f'{sd}.json').write_text(json.dumps(dict(seed=sd, auc=r['auc'], ci=r['ci'], n_h=r['n_h'], neff_h=r['neff_h'], n_m=r['n_m'])))
        print(sd, round(r['auc'], 4), [round(x, 4) for x in r['ci']], round(r['neff_h']), flush=True)


def csum():
    v = [json.loads(f.read_text()) for f in sorted((OUT / 'v5_cnull').glob('*.json'))]
    up = sorted(x['ci'][1] for x in v)
    au = sorted(x['auc'] for x in v)
    q95 = up[min(len(up) - 1, math.ceil(.95 * len(up)) - 1)]
    res = dict(draws=len(v), auc_mean=sum(au) / len(au), auc_q95=au[min(len(au) - 1, math.ceil(.95 * len(au)) - 1)],
               upper_ci_q95=q95, upper_ci_max=up[-1], pass_at_055=sum(u <= 0.55 for u in up) / len(up),
               neff_h=sum(x['neff_h'] for x in v) / len(v), n_m=v[0]['n_m'] if v else None, uppers=up)
    (OUT / 'v5_cnull.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


# ------------------------------------------------------------------ v6 (owner 10-28 16:10): calibrated to TODAY's humans
NEWEST_FROM, NEWEST_MARK = '20261025_084914', C3          # the newest block = the current Mark (CLXIII) since it went live


def newest(R):
    return [i for i, r in enumerate(R) if r['mark'] == NEWEST_MARK and r['ts'] >= NEWEST_FROM]


def bnull6(th, half_life, n_sim, draws, seed=0, out='v6_bnull.json'):
    """Drift-aware B-live null: the 'model' = n_sim draws from the NEWEST block (today's humans), the reference = n_eff draws ~ w
    from the whole weighted pool (the scored reference, Kish n_eff). Per draw: RMS d, B3, z_max = max_k |d_k| / SE_k. The v6
    per-stat rule is |d_k| <= z_max_limit x SE_k; z_max_limit = the smallest value at which RMS <= limit, B3 and the z rule pass
    jointly in >= 95% of draws."""
    masks = json.loads((OUT / 'v5_shift.json').read_text())['masks']
    meta, R, X = weighted(half_life, masks)
    ws = [x['_w'] for x in X]
    ne = neff(ws)
    cum, s = [], 0.0
    for w in ws:
        s += w
        cum.append(s)
    nw = newest(R)
    rng = random.Random(seed)
    rmax = th['B']['b_live_rms_d_max']
    res = []
    for _ in range(draws):
        Ri = [dict(X[j], _w=1.0) for j in _draw(rng, cum, round(ne))]
        Mi = [X[nw[rng.randrange(len(nw))]] for _ in range(n_sim)]
        b = CD.level_b(Ri, Mi, th)
        res.append(dict(rms=b['rms'], b3=b['pass_b3'], z=max(abs(b['stats'][k][6]) / b['stats'][k][7] for k in b['have']),
                        v5=b['passed']))
    ok = sorted(o['z'] for o in res if o['rms'] <= rmax and o['b3'])
    need = math.ceil(0.95 * draws)
    zlim = _up(ok[need - 1], 0.05) if len(ok) >= need else None          # None: RMS / B3 alone fail > 5% of today's humans
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
    r = dict(half_life=half_life, n_sim=n_sim, draws=draws, n_matches=len(X), neff=ne, n_newest=len(nw),
             newest_share=sum(ws[i] for i in nw) / sum(ws), masks=masks, z_max_limit=zlim,
             pass_full=(sum(o['rms'] <= rmax and o['b3'] and o['z'] <= zlim for o in res) / draws) if zlim else 0.0,
             pass_rms=sum(o['rms'] <= rmax for o in res) / draws, pass_b3=sum(o['b3'] for o in res) / draws,
             rms_q50=q([o['rms'] for o in res], .5), rms_q95=q([o['rms'] for o in res], .95),
             z_q50=q([o['z'] for o in res], .5), z_q95=q([o['z'] for o in res], .95),
             pass_v5_rule=sum(o['v5'] for o in res) / draws)
    (OUT / out).write_text(json.dumps(r, indent=1))
    print(json.dumps(r, indent=1))
    return r


def cnull6(half_life, n_sim, seeds, threads=4):
    """Drift-aware C-live null: the human class = a random half of the newest block (weights ~ w, as scored), the 'model' =
    n_sim draws from the OTHER half (match-level split keeps duplicates together). Conservative: the scored human class is the
    whole newest block (about twice this n_eff)."""
    import disc
    masks = json.loads((OUT / 'v5_shift.json').read_text())['masks']
    meta, R, X = weighted(half_life, masks)
    nw = newest(R)
    d = OUT / 'v6_cnull'
    d.mkdir(parents=True, exist_ok=True)
    for sd in seeds:
        rng = random.Random(2000 + sd)
        idx = list(nw)
        rng.shuffle(idx)
        A, B = idx[:len(idx) // 2], idx[len(idx) // 2:]
        H = [R[i] for i in A]
        M = [{k: v for k, v in R[B[rng.randrange(len(B))]].items() if k != 'w'} for _ in range(n_sim)]
        r = disc.train_eval(H, M, seed=sd, threads=threads)
        (d / f'{sd}.json').write_text(json.dumps(dict(seed=sd, auc=r['auc'], ci=r['ci'], n_h=r['n_h'], neff_h=r['neff_h'], n_m=r['n_m'])))
        print(sd, round(r['auc'], 4), [round(x, 4) for x in r['ci']], round(r['neff_h']), flush=True)


def register6(half_life, n_sim):
    """THRESHOLDS v6 from v5 + out/v6_bnull.json + out/v6_cnull.json (csum6). LF bytes (the logged sha is of LF)."""
    th = json.loads((HERE / 'THRESHOLDS.json').read_text())
    assert th['version'] == 5, 'register6 builds v6 from v5 only'
    bn, cn = (json.loads((OUT / f).read_text()) for f in ('v6_bnull.json', 'v6_cnull.json'))
    assert bn['half_life'] == half_life and bn['n_sim'] == n_sim and bn['z_max_limit']
    B, C = th['B'], th['C']
    R = B['live_reference']
    R['half_life_days'], R['neff'] = half_life, round(bn['neff'], 1)
    R['mask_rule'] += ' (Mark-change extension of the owner\'s reader rule: LEAD-APPROVED 10-28)'
    B['b_live_rule'], B['b_live_z_max'] = 'se_scaled', bn['z_max_limit']
    B['b_live_per_stat_abs_d_max_note'] = 'v6: unused by B-live (se_scaled rule); kept for v5 reproduction'
    B['b_live_human_null'] = {k: bn[k] for k in ('draws', 'n_sim', 'neff', 'n_newest', 'newest_share', 'pass_full', 'pass_rms',
                                                 'pass_b3', 'rms_q50', 'rms_q95', 'z_q50', 'z_q95', 'pass_v5_rule')}
    B['b_live_human_null']['control'] = 'drift-aware: model = n_sim draws from the newest block (CLXIII since 10-25 08:49)'
    auc = max(C['auc_upper_ci_max_overall'], _up(cn['upper_ci_q95'], 0.005))
    C['live_auc_upper_ci_max'] = auc
    C['live_human_class'], C['live_newest_from'], C['live_newest_mark'] = 'newest', NEWEST_FROM, NEWEST_MARK
    C['live_human_null'] = {k: cn[k] for k in ('draws', 'auc_mean', 'auc_q95', 'upper_ci_q95', 'upper_ci_max', 'pass_at_055', 'neff_h', 'n_m')}
    C['live_human_null']['control'] = 'drift-aware: human class = half the newest block (weighted), model = n_sim draws from the other half'
    old = th['changelog']
    th['version'], th['registered'] = 6, datetime.now().strftime('%Y-%m-%d')
    th['changelog'] = (f"v6 ({th['registered']}, P2-SCORE, OWNER DECISION 10-28 16:10: calibrate to TODAY's humans; human controls only, "
                       f"before any model score). Reference half-life {half_life} d (Kish n_eff {bn['neff']:.0f}); masks unchanged (Mark rule "
                       f"lead-approved). B-live: per-stat rule |d_k| <= {bn['z_max_limit']} x SE_k (SE-scaled, replaces the flat 25-stat "
                       f"TOST), RMS <= {B['b_live_rms_d_max']}, B3 CI, >= {n_sim} model games; drift-aware null ({bn['draws']} draws, model = "
                       f"{n_sim} draws from the newest block of {bn['n_newest']}): today's humans pass {bn['pass_full']:.3f} (v5 rule on the same "
                       f"draws: {bn['pass_v5_rule']:.3f}). C-live: human class = the newest block (Mark {NEWEST_MARK} since {NEWEST_FROM}); "
                       f"{cn['draws']} fresh discriminators on newest-block halves, upper CI q95 {cn['upper_ci_q95']:.3f} -> limit {auc}. "
                       f"v5 sha 438a7692...; v5 text: {old}")
    (HERE / 'THRESHOLDS.json').write_bytes((json.dumps(th, indent=2) + '\n').encode())
    print(hashlib.sha256((HERE / 'THRESHOLDS.json').read_bytes()).hexdigest())


def csum6():
    v = [json.loads(f.read_text()) for f in sorted((OUT / 'v6_cnull').glob('*.json'))]
    up, au = sorted(x['ci'][1] for x in v), sorted(x['auc'] for x in v)
    k = min(len(up) - 1, math.ceil(.95 * len(up)) - 1)
    res = dict(draws=len(v), auc_mean=sum(au) / len(au), auc_q95=au[k], upper_ci_q95=up[k], upper_ci_max=up[-1],
               pass_at_055=sum(u <= 0.55 for u in up) / len(up), neff_h=sum(x['neff_h'] for x in v) / len(v), n_m=v[0]['n_m'], uppers=up)
    (OUT / 'v6_cnull.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k_: v_ for k_, v_ in res.items() if k_ != 'uppers'}))


def _up(x, step):
    return math.ceil(x / step - 1e-9) * step


def register(half_life, n_sim):
    """THRESHOLDS v5 from v4 + the human controls (out/v5_shift.json, v5_bnull.json, v5_cnull.json). Each limit = max(plan
    value, the human 95th percentile at the scored n): humans pass >= 95% by construction, and no limit is tighter than the
    plan's equivalence margin. Writes THRESHOLDS.json; the caller logs its sha in HUMANLIKE.md BEFORE any model score."""
    th = json.loads((HERE / 'THRESHOLDS.json').read_text())
    assert th['version'] == 4, 'register builds v5 from v4 only'
    sh, bn, cn = (json.loads((OUT / f).read_text()) for f in ('v5_shift.json', 'v5_bnull.json', 'v5_cnull.json'))
    meta = json.loads(gzip.decompress(REF.read_bytes()))['meta']
    assert bn['half_life'] == half_life and bn['n_sim'] == n_sim and bn['masks'] == sh['masks']
    B, C = th['B'], th['C']
    rms = max(B['b_live_rms_d_max'], _up(bn['rms_q95'], 0.01))
    tost = max(B['b_live_per_stat_abs_d_max'], _up(bn['tost_max_q95'], 0.01))
    auc = max(C['auc_upper_ci_max_overall'], _up(cn['upper_ci_q95'], 0.005))
    B['live_reference'] = dict(rule='every non-sealed, non-dry live_play log of the icebow deck (all Marks, both accounts) with public '
                                    'frames and >= 3 detected opponent plays (allref.py build over live_table parser-v2 caches)',
                               deck='icebow', half_life_days=half_life, weight='w = 0.5 ** (age_days / half_life_days), age from sealed_from',
                               sealed_from=SEALED, stems_sha256=meta['stems_sha256'], n_matches=meta['n_icebow'], neff=round(bn['neff'], 1),
                               masks=sh['masks'], mask_rule='a stat the shift test flags at boundary b is NaN before b '
                                                            '(|d| > 1.96 sqrt(SE^2 + tau^2), tau^2 from 6 placebo boundaries)')
    B['b_live_rms_d_max'], B['b_live_per_stat_abs_d_max'], B['b_live_min_sim_games'] = rms, tost, n_sim
    B['b_live_human_null'] = {k: bn[k] for k in ('draws', 'n_sim', 'neff', 'pass_full', 'pass_rms', 'pass_tost', 'pass_b3', 'rms_q50',
                                                 'rms_q95', 'tost_max_q50', 'tost_max_q95')}
    vf = OUT / 'verify' / 'v5_bnull.json'           # the same null re-run AT the registered limits (v5_verify.py)
    if vf.exists():
        v = json.loads(vf.read_text())
        assert v['limits_used'] == dict(rms=rms, tost=tost), (v['limits_used'], rms, tost)
        B['b_live_human_null']['pass_full_at_registered_limits'] = v['pass_full']
    C['live_auc_upper_ci_max'], C['live_min_model_games'] = auc, n_sim
    C['live_human_null'] = {k: cn[k] for k in ('draws', 'auc_mean', 'auc_q95', 'upper_ci_q95', 'upper_ci_max', 'pass_at_055', 'neff_h', 'n_m')}
    old = th['changelog']
    th['version'], th['registered'] = 5, datetime.now().strftime('%Y-%m-%d')
    th['changelog'] = (f"v5 ({th['registered']}, P2-SCORE, owner decision 10-28: B-live rule and C-live limit set from ALL recorded live "
                       f"matches, recency-weighted; human controls only, before any model score). B-live / C-live reference = "
                       f"B.live_reference ({meta['n_icebow']} matches, half-life {half_life} d, Kish n_eff {bn['neff']:.0f}; reader / Mark "
                       f"shift masks {sh['masks']}). Human null at the scored n (n_eff draws vs {n_sim} model games, {bn['draws']} draws): "
                       f"full B-live pass {bn['pass_full']:.3f} under the plan margins; RMS q95 {bn['rms_q95']:.3f}, max per-stat TOST "
                       f"q95 {bn['tost_max_q95']:.3f} -> limits RMS {rms}, per-stat {tost} (max of plan and human q95; full pass at these limits in "
                       f"B.b_live_human_null). C-live: "
                       f"{cn['draws']} fresh discriminators on human halves (weighted human class, {n_sim} humans as the model), upper "
                       f"CI q95 {cn['upper_ci_q95']:.3f} -> limit {auc}; sufficiency = >= {n_sim} model games (C.n_per_class_min stays "
                       f"for C-HF). S (siege) unchanged on the CLXIII calibration block. v4 sha a5eb2c8f...; v4 text: {old}")
    (HERE / 'THRESHOLDS.json').write_bytes((json.dumps(th, indent=2) + '\n').encode())   # LF: the logged sha is of LF bytes
    print(hashlib.sha256((HERE / 'THRESHOLDS.json').read_bytes()).hexdigest())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('scan', 'parse', 'build', 'shift', 'bnull', 'cnull', 'csum', 'register', 'bnull6', 'cnull6',
                                    'csum6', 'register6'))
    ap.add_argument('--out', default=str(META))
    ap.add_argument('--logs')
    ap.add_argument('--list')
    ap.add_argument('--half-life', type=float, default=7.0)
    ap.add_argument('--n-sim', type=int, default=1900)
    ap.add_argument('--draws', type=int, default=1000)
    ap.add_argument('--seeds', type=int, nargs='*', default=[0])
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--unregistered', action='store_true', help='bnull / cnull before v5 exists: plan margins from the v4 file')
    a = ap.parse_args()
    if a.cmd == 'scan':
        scan(a.out)
    elif a.cmd == 'parse':
        parse(a.logs, a.list)
    elif a.cmd == 'build':
        build()
    elif a.cmd == 'shift':
        shift()
    elif a.cmd == 'csum':
        csum()
    elif a.cmd == 'register':
        register(a.half_life, a.n_sim)
    elif a.cmd == 'register6':
        register6(a.half_life, a.n_sim)
    elif a.cmd == 'csum6':
        csum6()
    elif a.cmd == 'cnull6':
        cnull6(a.half_life, a.n_sim, a.seeds, a.threads)
    else:
        th = json.loads((HERE / 'THRESHOLDS.json').read_text()) if a.unregistered else CD.SC.load_thresholds()[0]
        if a.cmd == 'bnull':
            bnull(th, a.half_life, a.n_sim, a.draws)
        elif a.cmd == 'bnull6':
            bnull6(th, a.half_life, a.n_sim, a.draws)
        else:
            cnull(th, a.half_life, a.n_sim, a.seeds, a.threads)


if __name__ == '__main__':
    main()
