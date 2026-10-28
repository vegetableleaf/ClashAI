"""P2-SCORE: the closed-loop opponent scorecard (plan1026 Pillar 2) -- ONE command per opponent checkpoint -> the A-D report
against THRESHOLDS.json (sha-checked through scorecard.load_thresholds).  Labels in the output: (a) measured.

    # laptop: launch the closed loop on a pod (resumable), fetch the rows, score everything, D last
    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/opp_model/humanlike/card.py card --name NAME --ckpt CKPT --pod 32657
            [--opp-extra "--opp-decide-every 20 --opp-tau 0.2"] [--level-a-data NPZ --level-a-mem NPZ] [--hf-sim DIR] [--no-c]
    # score rows already on disk (ROOT/NAME_SEED/D3/matches.jsonl from run_closed.sh + ROOT/ENGINE.json)
    ... card.py score --name NAME --sim ROOT [--ckpt CKPT ...]
    ... card.py selftest                      # human-vs-human controls + planted bugs for B (26 stats), B-HF, siege, C

Sources, one record format (`plays` = the opponent's plays [tick, key, cost, x, y, n_bodies, clean gap, public elixir est.] in
OUR tile frame, us at low y; `mine` = our play ticks; `xb` = our reach X-Bows [[tick, locked]] in order; `xbt` = all our X-Bow ticks):
  live   live_play logs of the TIME BLOCK (opp/live_split.json): 'calibration' (default reference) or 'train'; CLXIII (sha 8d328a43,
         the fixed live Mark) only.  Opponent plays = PlayDetector on the public frames (opp_model/live_table.cached); X-Bow
         locks = match_memory on live_dump.read (memory/xbow_arch.py's path).  The SEALED block is read only by level_d(), last.
  sim    run_closed.sh rows (gap.py --record-board): the opponent's ACCEPTED plays at land tick + 20 (crforge runs a play 20 ticks
         after it is given; the live detector cannot see it earlier), positions from the engine X, Y; public elixir estimate =
         the board sample's counter before the play; locks = succ48/xbow_count.py's rule on the 1-s board.
  hf     hf_ref.py output (HF tier-A replays re-driven on crforge), one record per side.
Public-information rule: live enters only through detected plays, our own plays and tower reads."""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import math
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
L74 = HERE.parents[1]
ROOT = HERE.parents[4]
sys.path[:0] = [str(HERE), str(L74 / 'opp_model'), str(L74 / 'human'), str(L74 / 'weekend'), str(L74 / 'memory'),
                str(L74 / 'succ48'), str(L74 / 'monitor'), str(ROOT)]
import scorecard as SC  # noqa: E402

SPLIT = json.loads((L74 / 'plan1026/opp/live_split.json').read_text())
LOGS = ROOT / 'scratchpad/gauntlet/L68/live_reader'
CACHE = HERE / 'cache'                                   # per-log live records (not committed)
MARK_SHA = '8d328a43'                                    # CLXIII NOLEAK = the fixed live data config (plan decision 2)
LIVE_OFF = 78                                            # live_table: fall clock = game tick - 78
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=30', '-o', 'StrictHostKeyChecking=no', '-i',
       str(Path.home() / '.ssh/runpod_clashbot')]
HOST = 'root@157.157.221.29'
TPS, WIN, RIVER, BR = 20, 160, 16.0, 3.0

CORE9, POS4, EXTRA = SC.CORE9, SC.POS4, SC.EXTRA
NEW7 = ['ppm_ot', 'lane_left', 'split_rate', 'troop_depth', 'spell_depth', 'pocket_share', 'ans_spell_3s']
STATS = CORE9 + POS4 + [k for k in EXTRA if k != 'repeat_rate'] + NEW7    # 25: repeat_rate dropped (a card cannot be played twice in a row; HF SD 0)


def arch2(names):
    """= opp_model/analyze.arch2 (copied: analyze imports doctrine/measure -> polars, absent on the pods)."""
    import archetypes as A
    a = A.classify(names)
    if a in ('weak_other', 'other') and 'hogrider' in {A.canon(n) for n in names}:
        return 'hog'
    return a


# ------------------------------------------------------------------ the time split
def block_of(stem: str) -> str:
    s = stem[len('live_play_'):] if stem.startswith('live_play_') else stem
    return 'train' if s < SPLIT['train_before'] else 'sealed' if s >= SPLIT['sealed_from'] else 'calibration'


# ------------------------------------------------------------------ per-match stats (one code path for every source)
def _spell(key):
    import opp_behaviour as OB
    return (OB.catalog()[0].get(key) or ('',))[0] == 'spell'


def new_stats(r):
    P = sorted(r['plays'], key=lambda p: p[0])
    nan = float('nan')
    f = dict.fromkeys(NEW7, nan)
    d3 = r['end'] - 3600
    if d3 >= 600:
        f['ppm_ot'] = sum(p[0] >= 3600 for p in P) / (d3 / (60.0 * TPS))
    troops = [p for p in P if not _spell(p[1])]
    spells = [p for p in P if _spell(p[1])]
    if P:
        f['lane_left'] = sum(p[3] < 9 for p in P) / len(P)
    if troops:
        f['troop_depth'] = sum(p[4] for p in troops) / len(troops)
    if spells:
        f['spell_depth'] = sum(p[4] for p in spells) / len(spells)
    w = defaultdict(set)
    for p in troops:
        if abs(p[3] - 9) >= 0.5:
            w[int((p[0] - r['t0']) // WIN)].add(p[3] < 9)
    multi = [v for k, v in w.items() if sum(1 for p in troops if int((p[0] - r['t0']) // WIN) == k) >= 2]
    if multi:
        f['split_rate'] = sum(len(v) == 2 for v in multi) / len(multi)
    fall = r.get('own_fall')
    if fall is not None:
        after = [p for p in troops if p[0] > fall]
        if len(after) >= 2:
            f['pocket_share'] = sum(p[4] < RIVER - BR for p in after) / len(after)
    ans = []
    ts = [p[0] for p in P]
    import bisect
    for o in r['mine']:
        i = bisect.bisect_right(ts, o)
        if i < len(P) and P[i][0] - o <= 3 * TPS:
            ans.append(_spell(P[i][1]))
    if ans:
        f['ans_spell_3s'] = sum(ans) / len(ans)
    return f


def stat_row(r, arch):
    import opp_behaviour as OB
    m = dict(plays=sorted(r['plays'], key=lambda p: p[0]), mine=sorted(r['mine']), end=r['end'], t0=r['t0'])
    f = OB.features(m)
    f.update(SC.extra_stats(m['plays']))
    f.update(SC.sig_stats(arch, m['plays'], m['end']))
    f.update(new_stats(r))
    f['_arch'], f['_pos'] = arch, True
    return f


# ------------------------------------------------------------------ sources
def _xb_live(path):
    import live_dump as LD
    from pipeline import match_memory as M
    m = LD.read(path)
    ev = M.build(m['side'], m['samples'], m['plays']).events(m['last'] + 1)
    xb = [[int(e['tick']), int(bool(e['xb']['locked']))] for e in ev
          if e['type'] == 'play' and e['mine'] and e['card'] == 'x-bow' and e.get('reach') and e.get('xb')]
    xbt = [int(e['tick']) for e in ev if e['type'] == 'play' and e['mine'] and e['card'] == 'x-bow']
    return xb, xbt


def _live_one(path):
    import live_table as LT
    c = CACHE / (path.stem + '.json.gz')
    if c.exists():
        return json.loads(gzip.decompress(c.read_bytes()))
    sha = None
    with open(path, 'rb') as fh:                                   # cheap Mark test before the full parse
        for _, raw in zip(range(400), fh):
            if raw.startswith(b'{"event": "start"'):
                sha = json.loads(raw).get('ckpt_sha256') or ''
                break
    if not (sha or '').startswith(MARK_SHA):
        CACHE.mkdir(exist_ok=True)
        c.write_bytes(gzip.compress(b'null'))
        return None
    d = LT.cached(path)
    rec = None
    if d and d.get('start') and not d['start'].get('dry') and (d['start'].get('sha') or '').startswith(MARK_SHA):
        own = [t + LIVE_OFF for k, t in d['falls'].items() if k.startswith('own_P')]
        try:
            xb, xbt = _xb_live(path)
        except Exception as e:                                     # noqa: BLE001  a truncated log: no siege data, stated
            xb, xbt = None, None
            print(f'xb skip {path.name}: {e!r}'[:140], file=sys.stderr)
        rec = dict(src='live', id=path.name, t0=d['t0'], end=d['end'], side=d['side'], plays=d['plays'], mine=d['mine'],
                   seen=d['seen'], own_fall=min(own) if own else None, xb=xb, xbt=xbt)
    CACHE.mkdir(exist_ok=True)
    c.write_bytes(gzip.compress(json.dumps(rec).encode()))
    return rec


def live_records(block='calibration', _allow_sealed=False):
    if block == 'sealed' and not _allow_sealed:
        raise SystemExit('the sealed block is read only by level D')
    out = []
    for f in sorted(LOGS.glob('live_play_*.jsonl')):
        if block_of(f.stem) != block:
            continue                                               # the sealed block is never opened here (name test first)
        r = _live_one(f)
        if r is not None and len(r['plays']) >= 3:
            r['arch'] = arch2(r['seen'])
            out.append(r)
    return out


def _canon_sim(name):
    from pipeline import vocab
    k = (vocab.engine_key(str(name).split('@')[0]) or str(name)).replace('-', '_')
    for suf in ('_evo', '_hero'):                          # the board record names forms ('knight_evo'); live / HF keys are bases
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k


def sim_records(root, live_visible=True, mvm=False):
    """run_closed.sh rows -> records (+ outcome for D).  live_visible: keep only plays the live detector can see (o3_score.visible:
    bodiless spells never appear in the live public frames), so B-live / C-live compare like with like; False for B-HF.
    mvm (pairs.py --mvm rows, B-HF / C-HF): both seats are the model -> one record per SEAT, plays at the tick the command was
    given (hf_ref.py's HF tick convention; no +20), own_fall None (pocket_share is not a B-HF stat)."""
    import o3_score as O3
    import xbow_count as XC
    from pipeline.opp_elixir_count import card_cost
    out = []
    for r, h in XC.rows(str(root)):
        L = int(h['L'])
        mir = bool(h['mirror'][0])
        fr = (lambda X, Y: (18 - X / 1000, 32 - Y / 1000)) if mir else (lambda X, Y: (X / 1000, Y / 1000))
        smp = h['samples']
        st = [s[0] for s in smp]
        import bisect
        if mvm:
            out += _mvm_records(r, h, fr, live_visible)
            continue
        plays = []
        for q in h['opp']:
            if not q[3]:
                continue
            t = int(q[1] if q[1] is not None else q[0]) + 20
            k = _canon_sim(q[2])
            if live_visible and not O3.visible(k):
                continue
            x, y = fr(q[8], q[9])
            i = bisect.bisect_left(st, t) - 1
            el = smp[i][2] if i >= 0 else None
            plays.append([t, k, card_cost(k) or 0.0, round(x, 2), round(y, 2), 1, 0, el])
        own = [q for q in h['own'] if q[3]]
        fall = None
        for s in smp:                                          # our princess falls: a destroyed tower leaves the board record
            if sum(tw[0] == L and tw[1] != 'k' and tw[4] > 0 for tw in s[5]) < 2:
                fall = s[0]
                break
        o = xb_sim(h)
        deck = [_canon_sim(c) for c in (r.get('opp_deck') or [])]
        out.append(dict(src='sim', id=f"{r['seed']}:{r['tag']}", t0=0, end=int(r['end_tick']), side=1 - L, plays=plays,
                        mine=[int(q[0]) for q in own], seen=deck, own_fall=fall, xb=o[0], xbt=o[1], arch=arch2(deck),
                        win=int(r['outcome'] == 'win'), outcome=r['outcome']))
    return out


def _mvm_records(r, h, fr, live_visible):
    import o3_score as O3
    from pipeline.opp_elixir_count import card_cost

    def pl(seat, flip):
        o = []
        for q in h[seat]:
            if not q[3]:
                continue
            k = _canon_sim(q[2])
            if live_visible and not O3.visible(k):
                continue
            x, y = fr(q[8], q[9])
            if flip:                                  # the learner seat's record: "our" frame = the opponent seat at low y
                x, y = 18 - x, 32 - y
            o.append([int(q[1] if q[1] is not None else q[0]), k, card_cost(k) or 0.0, round(x, 2), round(y, 2), 1, 0, None])
        return o
    rec = []
    for seat, other, flip, dk in (('opp', 'own', False, 'opp_deck'), ('own', 'opp', True, 'learner_deck')):
        deck = [_canon_sim(c) for c in (r.get(dk) or [])]
        res = r['outcome'] if seat == 'own' else {'win': 'loss', 'loss': 'win'}.get(r['outcome'], r['outcome'])
        rec.append(dict(src='sim', id=f"{r['seed']}:{r['tag']}:{seat}", t0=0, end=int(r['end_tick']), plays=pl(seat, flip),
                        mine=[p[0] for p in pl(other, not flip)], seen=deck, own_fall=None, xb=None, xbt=None, arch=arch2(deck),
                        win=int(res == 'win'), outcome=res))
    return rec


def xb_sim(h):
    """succ48/xbow_count.one, returning the per-X-Bow sequence [[tick, locked]] and every X-Bow tick."""
    import xbow_count as XC
    side = h['L']
    series = {}
    for s in h['samples']:
        for t_ in s[5]:
            if t_[0] != side and t_[1] != 'k':
                series.setdefault(XC.tiles(t_[2], t_[3]), []).append((s[0], t_[4]))
    seq, allt = [], []
    for q in h['own']:
        if not q[3] or 'bow' not in str(q[2]).lower().replace('-', ''):
            continue
        t0 = q[1] if q[1] is not None else q[0]
        allt.append(int(t0))
        x, y = XC.tiles(q[8], q[9])
        near = []
        for pos, ser in series.items():
            hp0 = next((hp for t, hp in reversed(ser) if t <= t0), None)
            if hp0 and hp0 > 0 and math.hypot(x - pos[0], y - pos[1]) <= XC.REACH:
                near.append((hp0, max(hp for _, hp in ser), [hp for t, hp in ser if t0 < t <= t0 + XC.WINDOW]))
        if near:
            seq.append([int(t0), int(any(lt and (hp0 - min(lt)) >= XC.LOCK_FRAC * mx for hp0, mx, lt in near))])
    return seq, allt


def hf_records(path, split=None):
    d = json.loads(gzip.decompress(Path(path).read_bytes()))
    out = []
    for r in d['records']:
        if split is not None and r['split'] != split:
            continue
        r['arch'] = arch2(r['deck'])
        r['own_fall'] = None
        out.append(r)
    return out, d['meta']


def rows(recs):
    return [stat_row(r, r['arch']) for r in recs]


# ------------------------------------------------------------------ v5: the weighted all-matches live reference (allref.py)
def wcohen(L, S, keys, nmin=5):
    """SC.cohen with per-row weights '_w' on the live side (absent = 1): weighted mean / SD, n = Kish n_eff (sum w)^2 / sum w^2.
    All weights 1 -> exactly SC.cohen."""
    out = {}
    for k in keys:
        lv = [(x[k], x.get('_w', 1.0)) for x in L if not math.isnan(x[k])]
        W, W2 = sum(w for _, w in lv), sum(w * w for _, w in lv)
        nl = W * W / W2 if W2 else 0.0
        ml = sum(v * w for v, w in lv) / W if W else float('nan')
        sl = math.sqrt(sum(w * (v - ml) ** 2 for v, w in lv) / W * nl / (nl - 1)) if nl > 1 else float('nan')
        ns, ms_, ss = SC._ms([x[k] for x in S])
        d = se = float('nan')
        if nl >= nmin and ns >= nmin:
            sp = math.sqrt(((nl - 1) * sl ** 2 + (ns - 1) * ss ** 2) / (nl + ns - 2))
            if sp > 0:
                d = (ms_ - ml) / sp
                se = math.sqrt(1 / nl + 1 / ns + d * d / (2 * (nl + ns)))
        out[k] = (nl, ml, sl, ns, ms_, ss, d, se)
    return out


def _wlse(rows, k):
    """SC._lse with weights '_w' (n = Kish n_eff)."""
    xs = [(x[k], x.get('_w', 1.0)) for x in rows if not math.isnan(x[k])]
    W, W2 = sum(w for _, w in xs), sum(w * w for _, w in xs)
    n = W * W / W2
    mu = sum(v * w for v, w in xs) / W
    v = sum(w * (x - mu) ** 2 for x, w in xs) / W
    kt = sum(w * (x - mu) ** 4 for x, w in xs) / W / (v * v) if v > 0 else 3.0
    return 0.5 * math.log(v) if v > 0 else float('nan'), math.sqrt(max(kt - 1, 0) / (4 * n))


def wspread_ci(L, S, k, z):
    ls, es = _wlse(S, k)
    ll, el = _wlse(L, k)
    r, e = ls - ll, math.sqrt(es * es + el * el)
    return math.exp(r - z * e), math.exp(r + z * e)


def ref_v5(th):
    """The v5 B-live / C-live live reference: (records, stat rows) from data/allref_v5.json.gz (allref.py build), every row
    weighted '_w' (THRESHOLDS B.live_reference: recency half-life) and the reader / Mark shift masks applied (a masked stat is
    NaN for matches before its boundary).  The file's stems sha must equal the registered one."""
    R = th['B']['live_reference']
    d = json.loads(gzip.decompress((HERE / 'data' / 'allref_v5.json.gz').read_bytes()))
    if d['meta']['stems_sha256'] != R['stems_sha256']:
        raise SystemExit('data/allref_v5.json.gz is not the registered v5 reference (stems sha differs): refusing')
    keep = [i for i, r in enumerate(d['records']) if r['deck'] == R['deck']]
    recs, rows_ = [d['records'][i] for i in keep], [d['rows'][i] for i in keep]
    for r, x in zip(recs, rows_):
        w = 0.5 ** (r['age_d'] / R['half_life_days'])
        r['w'] = x['_w'] = w
        for k, b in R.get('masks', {}).items():
            if r['ts'] < b:
                x[k] = float('nan')
        for k in STATS:
            if x.get(k) is None:
                x[k] = float('nan')
    return recs, rows_


# ------------------------------------------------------------------ level B (B-live and B-HF share the rule; feats = STATS)
def level_b(L, S, th, feats=STATS, margin=None, rms_max=None):
    B = th['B']
    c = wcohen(L, S, feats, B['min_n_per_side_for_a_stat'])
    have = [k for k in feats if not math.isnan(c[k][6])]
    marg = margin if margin is not None else B['b_live_per_stat_abs_d_max']
    tost = {k: abs(c[k][6]) + SC.Z90 * c[k][7] < marg for k in have}
    r = SC.rms(c, have)
    lo, hi = B['b3_spread_ratio_range']
    b3 = {}
    for k in B['b3_stats']:
        if k in have:
            ci = wspread_ci(L, S, k, B['b3_ci_z'])
            b3[k] = (ci[0] <= hi and ci[1] >= lo, ci)
    rmax = rms_max if rms_max is not None else B['b_live_rms_d_max']
    ok = bool(have) and r <= rmax and all(tost.values()) and bool(b3) and all(v[0] for v in b3.values())
    return dict(n_live=len(L), n_sim=len(S), stats=c, have=have, missing=[k for k in feats if k not in have], rms=r, tost=tost,
                b3=b3, pass_rms=bool(r <= rmax), pass_tost=all(tost.values()), pass_b3=bool(b3) and all(v[0] for v in b3.values()),
                passed=ok)


def per_arch(L, S, th, nmin, **kw):
    out = {}
    for a in sorted({x['_arch'] for x in L} | {x['_arch'] for x in S}):
        la, sa = [x for x in L if x['_arch'] == a], [x for x in S if x['_arch'] == a]
        out[a] = level_b(la, sa, th, **kw) if len(la) >= nmin and len(sa) >= nmin else dict(n_live=len(la), n_sim=len(sa), passed=False,
                                                                                             rms=float('nan'), short=True)
    return out


# ------------------------------------------------------------------ siege facts + adaptation-value audit
def siege_facts(recs):
    """Match-level units: [(arch, xb seq, all X-Bow ticks)] -> the facts, pooled over X-Bows."""
    ms = [(r['arch'], r['xb'], r['xbt'] or []) for r in recs if r.get('xb') is not None]
    return ms


def _facts(ms):
    n = sum(len(x) for _, x, _ in ms)
    k = sum(l for _, x, _ in ms for _, l in x)
    multi = [x for _, x, _ in ms if len(x) >= 2]
    pairs = [(a[1], b[1]) for _, x, _ in ms for a, b in zip(x, x[1:])]
    lf = [b for a, b in pairs if a == 0]
    ll = [b for a, b in pairs if a == 1]
    again = {0: [0, 0], 1: [0, 0]}                     # X-Bow again within 30 s after the outcome is known (t + 600 .. t + 1200]
    for _, x, allt in ms:
        for t, l in x:
            again[l][1] += 1
            again[l][0] += any(t + 600 < u <= t + 1200 for u in allt)
    pa = {l: (a / b if b else float('nan')) for l, (a, b) in again.items()}
    nan = float('nan')
    return dict(matches=len(ms), xbows=n, lock_rate=k / n if n else nan,
                zero_lock=sum(all(l == 0 for _, l in x) for x in multi) / len(multi) if multi else nan, n_multi=len(multi),
                p_lock_after_fail=sum(lf) / len(lf) if lf else nan, p_lock_after_lock=sum(ll) / len(ll) if ll else nan,
                n_after_fail=len(lf), n_after_lock=len(ll),
                cond_gap=(sum(ll) / len(ll) - sum(lf) / len(lf)) if lf and ll else nan,
                persistence=pa[0] / pa[1] if pa[1] and pa[1] == pa[1] and pa[1] > 0 else nan, again_fail=pa[0], again_lock=pa[1])


FACT_KEYS = ('lock_rate', 'zero_lock', 'p_lock_after_fail', 'cond_gap')


def siege(L, S, th, B=400, seed=0):
    """SIM minus live per fact, match-cluster bootstrap 90% CI; pass = CI inside +-margin (THRESHOLDS 'S'); + per archetype lock rate."""
    Sg = th.get('S') or dict(lock_rate_pp=0.05, zero_lock_pp=0.05, p_lock_after_fail_pp=0.10, cond_gap_pp=0.10,
                             arch_lock_rate_pp=0.10, arch_min_live_xbows=600)
    lm, sm = siege_facts(L), siege_facts(S)
    fl, fs = _facts(lm), _facts(sm)
    rng = random.Random(seed)
    bs = defaultdict(list)
    for _ in range(B):
        a = _facts([lm[rng.randrange(len(lm))] for _ in lm]) if lm else None
        b = _facts([sm[rng.randrange(len(sm))] for _ in sm]) if sm else None
        if a and b:
            for k in FACT_KEYS:
                bs[k].append(b[k] - a[k])
    res = {}
    for k in FACT_KEYS:
        v = sorted(x for x in bs[k] if x == x)
        m = Sg[k + '_pp']
        ci = (v[int(.05 * len(v))], v[int(.95 * len(v)) - 1]) if len(v) > 20 else (float('nan'), float('nan'))
        res[k] = dict(live=fl[k], sim=fs[k], diff=fs[k] - fl[k], ci=ci, margin=m, passed=bool(ci[0] == ci[0] and -m < ci[0] and ci[1] < m))
    arch = {}
    for a in sorted({x[0] for x in lm}):
        la, sa = [x for x in lm if x[0] == a], [x for x in sm if x[0] == a]
        nl = sum(len(x[1]) for x in la)
        if nl < Sg['arch_min_live_xbows'] or not sa:
            arch[a] = dict(n_live=nl, n_sim=sum(len(x[1]) for x in sa), passed=None)
            continue
        d = []
        for _ in range(B):
            p = _facts([la[rng.randrange(len(la))] for _ in la])['lock_rate']
            q = _facts([sa[rng.randrange(len(sa))] for _ in sa])['lock_rate']
            if p == p and q == q:
                d.append(q - p)
        d.sort()
        ci = (d[int(.05 * len(d))], d[int(.95 * len(d)) - 1])
        arch[a] = dict(n_live=nl, n_sim=sum(len(x[1]) for x in sa), live=_facts(la)['lock_rate'], sim=_facts(sa)['lock_rate'], ci=ci,
                       passed=bool(-Sg['arch_lock_rate_pp'] < ci[0] and ci[1] < Sg['arch_lock_rate_pp']))
    ok = all(v['passed'] for v in res.values()) and all(v['passed'] is not False for v in arch.values())
    return dict(live=fl, sim=fs, tests=res, arch=arch, passed=bool(ok))


# ------------------------------------------------------------------ level D (sealed block; called LAST)
def level_d(S, th):
    """Outcome parity on the SEALED live block: CLXIII matches with a graded result. P_hat per match = the SIM win rate of CLXIII
    against this opponent model in the match's archetype (pooled when that archetype has < 30 SIM games). Pass needs >= 1,500
    matches (THRESHOLDS D.min_sealed_matches): below that the level FAILS by the sufficiency rule whatever the point values."""
    import card_use
    D = th['D']
    res = card_use.results()
    live = [r for r in live_records('sealed', _allow_sealed=True)]
    g = [(r, res[r['id']][0]) for r in live if r['id'] in res and res[r['id']][0] in ('WIN', 'LOSS', 'DRAW') and abs(res[r['id']][1]) <= 100]
    simw = defaultdict(list)
    for s in S:
        simw[s['arch']].append(s['win'])
    pooled = sum(s['win'] for s in S) / len(S)
    ph = lambda a: sum(simw[a]) / len(simw[a]) if len(simw[a]) >= 30 else pooled  # noqa: E731
    n = len(g)
    out = dict(n_sealed=n, need=D['min_sealed_matches'], sim_pooled=pooled, enough=n >= D['min_sealed_matches'])
    if n:
        y = [1.0 if v == 'WIN' else 0.0 for _, v in g]
        p = [ph(r['arch']) for r, _ in g]
        diff = [a - b for a, b in zip(p, y)]
        mu = sum(diff) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in diff) / max(1, n - 1))
        ci = (100 * (mu - SC.Z90 * sd / math.sqrt(n)), 100 * (mu + SC.Z90 * sd / math.sqrt(n)))
        m = D['mean_pred_vs_live_pp_max']
        by = defaultdict(list)
        for (r, v), pp in zip(g, p):
            by[r['arch']].append((pp, 1.0 if v == 'WIN' else 0.0))
        out.update(live_win=sum(y) / n, mean_pred=sum(p) / n, resid_pp=100 * mu, ci_pp=ci, tost=bool(-m < ci[0] and ci[1] < m),
                   arch={a: (len(v), 100 * (sum(x for x, _ in v) - sum(z for _, z in v)) / len(v)) for a, v in by.items()})
    out['passed'] = bool(out['enough'] and out.get('tost'))
    return out


# ------------------------------------------------------------------ level A (delegates to P2-OPP1's opp/level_a.py)
def level_a(ckpt, data, mem, out):
    if not ckpt:
        return dict(scored=False, why='no checkpoint given', passed=False)
    import torch
    sd = torch.load(ckpt, map_location='cpu', weights_only=False)
    keys = list((sd.get('model') or sd.get('state_dict') or sd).keys()) if isinstance(sd, dict) else []
    if not any(str(k).startswith('timing_head') for k in keys):
        return dict(scored=False, why='no timing head (a legacy gate model): level A is defined on the timing head', passed=False)
    if not data:
        return dict(scored=False, why='timing-head model but no --level-a-data (rows_to_npz --keep-wait 1 --only-split 2)', passed=False)
    cmd = [sys.executable, '-I', str(L74 / 'plan1026/opp/level_a.py'), '--ckpt', ckpt, '--data', data, '--split', '2', '--out', str(out)]
    if mem:
        cmd += ['--memory-tables', mem]
    subprocess.run(cmd, check=True)
    a = json.loads(Path(out).read_text())
    return dict(scored=True, result=a, passed=bool(a.get('passed')))


# ------------------------------------------------------------------ printing
f2 = SC.f2


def print_b(tag, b):
    if b.get('short'):
        return f'{tag}: n {b["n_sim"]}/{b["n_live"]} too few => FAIL (sufficiency)'
    worst = sorted(b['have'], key=lambda k: -abs(b['stats'][k][6]))[:5]
    fails = [k for k, v in b['tost'].items() if not v]
    return (f'{tag}: n model {b["n_sim"]} / human {b["n_live"]}; RMS d over {len(b["have"])} stats {f2(b["rms"])} '
            f'(pass {b["pass_rms"]}); TOST all {b["pass_tost"]} ({len(fails)} fail); B3 {b["pass_b3"]} '
            f'=> {"PASS" if b["passed"] else "FAIL"}; worst |d|: ' + ', '.join(f'{k} {b["stats"][k][6]:+.2f}' for k in worst)
            + (f'; missing {b["missing"]}' if b['missing'] else ''))


def score(name, sim_root, th, sha, a_args, hf_sim=None, do_c=True, out_dir=None, do_d=True):
    out_dir = Path(out_dir or HERE / 'out' / f'card_{name}')
    out_dir.mkdir(parents=True, exist_ok=True)
    eng = json.loads((Path(sim_root) / 'ENGINE.json').read_text()) if (Path(sim_root) / 'ENGINE.json').exists() else None
    lines = [f'# Opponent scorecard: {name}', f'THRESHOLDS.json sha256 {sha}',
             f'engine build: {json.dumps(eng) if eng else "UNKNOWN (no ENGINE.json)"}',
             'NOTE: closed-loop numbers before D2 can be engine-limited (the build above is the one that produced them).']
    rep = dict(name=name, thresholds_sha=sha, engine=eng)
    S = sim_records(sim_root)
    L = live_records('calibration')                      # siege facts: THRESHOLDS S stays on the CLXIII calibration block
    SR = rows(S)
    LV, LR = ref_v5(th) if th['B'].get('live_reference') else (L, rows(L))   # v5: B-live / C-live on the all-matches reference
    # A
    A = level_a(*a_args, out_dir / 'A.json')
    rep['A'] = A
    lines.append(f'## A (per decision): {"PASS" if A["passed"] else "FAIL"}' + ('' if A.get('scored') else f' -- not scored: {A["why"]}'))
    # B-live
    b = level_b(LR, SR, th)
    nmin = th['B'].get('b_live_min_sim_games', 0)
    b['enough'] = len(SR) >= nmin
    b['passed'] = bool(b['passed'] and b['enough'])
    pa = per_arch(LR, SR, th, 30)
    rep['B_live'], rep['B_live_arch'] = b, pa
    lines.append('## B-live (vs live humans: ' + (f'v5 all-matches reference, {len(LR)} matches, recency-weighted' if th['B'].get('live_reference')
                                                  else 'CLXIII calibration block') + f'; model games >= {nmin}: {b["enough"]})')
    lines.append(print_b('B-live pooled', b))
    for a, v in pa.items():
        lines.append('  ' + print_b(f'arch {a}', v))
    sg = SC.sig_table(LR, SR)
    lines.append('signature stats d (model - live): ' + '; '.join(f'{a}: ' + ' '.join(f'{k} {f2(c[6])}' for k, c in v[2].items()) + f' (n {v[1]}/{v[0]})'
                                                           for a, v in sg.items() if v[1] >= 5 and v[0] >= 5))
    # B-HF
    if hf_sim:
        Hs, meta = hf_records(th['_hf_ref'], split=2)
        bh = level_b(rows(Hs), rows(sim_records(hf_sim, live_visible=False)), th, feats=[k for k in STATS if k not in ('opp_el', 'pocket_share')],
                     margin=th['B']['b_hf_per_stat_abs_d_max'])
        need = th['B'].get('b_hf_min_games_per_class', 0)
        bh['enough'] = min(bh['n_live'], bh['n_sim']) >= 2 * need          # records are sides: 2 per match
        bh['passed'] = bool(bh['passed'] and bh['enough'])
        rep['B_HF'] = bh
        lines.append(print_b('## B-HF', bh))
    else:
        rep['B_HF'] = dict(passed=False, why='no model-vs-model HF-deck-pair rows (runner not built: NEEDS a learner-deck option)')
        lines.append('## B-HF: FAIL -- not scored: ' + rep['B_HF']['why'])
    # siege
    sgt = siege(L, S, th)
    rep['siege'] = sgt
    lines.append(f'## Siege facts + adaptation-value audit => {"PASS" if sgt["passed"] else "FAIL"}')
    for k, v in sgt['tests'].items():
        lines.append(f'  {k}: live {f2(v["live"])} model {f2(v["sim"])} diff {v["diff"]:+.3f} 90% CI [{v["ci"][0]:+.3f}, {v["ci"][1]:+.3f}] '
                     f'margin +-{v["margin"]} => {"pass" if v["passed"] else "FAIL"}')
    for side, f in (('live', sgt['live']), ('model', sgt['sim'])):
        lines.append(f'  {side}: matches {f["matches"]} reach X-Bows {f["xbows"]} | P(lock|prev failed) {f2(f["p_lock_after_fail"])} '
                     f'(n {f["n_after_fail"]}) vs P(lock|prev locked) {f2(f["p_lock_after_lock"])} (n {f["n_after_lock"]}) | zero-lock share '
                     f'{f2(f["zero_lock"])} (n {f["n_multi"]}) | X-Bow again in 30 s after fail {f2(f["again_fail"])} / after lock '
                     f'{f2(f["again_lock"])} = persistence {f2(f["persistence"])}')
    lines.append('  lock rate by archetype: ' + '; '.join(f'{a} live {f2(v.get("live"))} model {f2(v.get("sim"))} (n {v["n_live"]}/{v["n_sim"]}) '
                                                           f'{"" if v["passed"] is None else "pass" if v["passed"] else "FAIL"}'
                                                           for a, v in sgt['arch'].items()))
    # C
    if do_c:
        import disc
        c = disc.level_c(LV, S, th, tag=name)
        rep['C_live'] = c
        lines.append('## C-live: ' + disc.fmt(c))
        lines.append('   C-HF: FAIL -- not scored (needs the model-vs-model HF-deck-pair rows, as B-HF)')
    else:
        rep['C_live'] = dict(passed=False, why='skipped (--no-c)')
        lines.append('## C: FAIL -- skipped (--no-c)')
    # H (B-only proxy; A and C gate H_ABC)
    cov = SC.coverage({a: bool(v.get('passed')) for a, v in pa.items()}, th)
    abc = A['passed'] and rep['C_live'].get('passed') and rep['B_HF'].get('passed')
    rep['H'] = dict(H_B=cov['H'], H_ABC=cov['H'] if abc else 0.0)
    lines.append(f'## H: H_B {cov["H"]:.3f} over {cov["cells"]} cells; H_ABC {rep["H"]["H_ABC"]:.3f} (A, B-HF, C all needed)')
    # D LAST: the sealed block is opened only here
    d = level_d(S, th) if do_d else dict(n_sealed=0, need=th['D']['min_sealed_matches'], enough=False, passed=False)
    rep['D'] = d
    lines.append(f'## D (sealed block, read last): n {d["n_sealed"]} (need >= {d["need"]}); ' +
                 (f'live win {100 * d["live_win"]:.1f}% vs predicted {100 * d["mean_pred"]:.1f}% (SIM pooled {100 * d["sim_pooled"]:.1f}%), '
                  f'residual {d["resid_pp"]:+.1f} pp 90% CI [{d["ci_pp"][0]:+.1f}, {d["ci_pp"][1]:+.1f}]' if d['n_sealed'] else 'no sealed matches')
                 + f' => {"PASS" if d["passed"] else "FAIL"}' + ('' if d['enough'] else ' (sufficiency rule)'))
    verdict = all([A['passed'], b['passed'], rep['B_HF'].get('passed'), sgt['passed'], rep['C_live'].get('passed'), d['passed']])
    lines.append(f'## VERDICT {name}: {"PASS" if verdict else "FAIL"} (A {A["passed"]}, B-live {b["passed"]}, B-HF {rep["B_HF"].get("passed")}, '
                 f'siege {sgt["passed"]}, C {rep["C_live"].get("passed")}, D {d["passed"]})')
    txt = '\n'.join(lines)
    (out_dir / 'report.txt').write_text(txt + '\n', encoding='utf-8')
    (out_dir / 'report.json').write_text(json.dumps(_clean(rep), indent=1, default=str))
    print(txt)
    return rep


def _clean(o):
    if isinstance(o, dict):
        return {str(k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return None if isinstance(o, float) and math.isnan(o) else o


# ------------------------------------------------------------------ the one command: pod run + fetch + score
def card(a, th, sha):
    root = HERE / 'rows' / a.name
    remote = f'/workspace/score/rows/{a.name}'
    env = f'OPP_CKPT={a.ckpt} ' if a.ckpt else ''
    env += f'OPP_T={a.opp_t} OPP_EXTRA="{a.opp_extra}" WORKERS={a.workers}'
    seeds = ' '.join(map(str, a.seeds))
    sh = (f'cd /workspace/score && (setsid nohup bash -c "{env} bash run_closed.sh {a.name} {remote} {seeds}" > {a.name}.out 2>&1 '
          f'< /dev/null &)')
    if not a.no_run:
        subprocess.run(SSH + ['-p', str(a.pod), HOST, sh], check=True)
        want = 480 * len(a.seeds)
        while True:
            n = subprocess.run(SSH + ['-p', str(a.pod), HOST, f'cat {remote}/*/D3/matches.jsonl 2>/dev/null | wc -l; grep -c "CLOSED DONE" '
                                      f'/workspace/score/{a.name}.out'], capture_output=True, text=True).stdout.split()
            print(time.strftime('%H:%M:%S'), 'rows', n, flush=True)
            if n and (int(n[0]) >= want or (len(n) > 1 and n[1] != '0')):
                break
            time.sleep(120)
    root.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(SSH + ['-p', str(a.pod), HOST, f'cd {remote} && tar czf - ENGINE.json */D3/matches.jsonl'], capture_output=True, check=True).stdout
    import io
    import tarfile
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(root)
    return score(a.name, root, th, sha, (a.ckpt_local or a.ckpt, a.level_a_data, a.level_a_mem), a.hf_sim, not a.no_c)


# ------------------------------------------------------------------ controls (human vs human + planted bugs)
def halves(xs, seed):
    idx = list(range(len(xs)))
    random.Random(seed).shuffle(idx)
    h = len(idx) // 2
    return [xs[i] for i in idx[:h]], [xs[i] for i in idx[h:]]


def selftest(th, hf_path=None, nsp=50, out=None):
    lines = []
    L = live_records('calibration')
    LR = rows(L)
    lines.append(f'calibration block CLXIII live matches with >= 3 opponent plays: {len(L)}')
    cnt = Counter()
    for seed in range(100, 100 + nsp):
        a, b = halves(LR, seed)
        r = level_b(a, b, th)
        cnt['rms'] += r['pass_rms']; cnt['tost'] += r['pass_tost']; cnt['b3'] += r['pass_b3']; cnt['all'] += r['passed']
    lines.append(f'B-live human control, {nsp} random halves of the calibration block (n ~{len(LR) // 2}/side, {len(STATS)} stats): '
                 f'RMS {cnt["rms"]}/{nsp} TOST {cnt["tost"]}/{nsp} B3 {cnt["b3"]}/{nsp} full {cnt["all"]}/{nsp}')
    lines.append(f'train-block CLXIII matches: {len(live_records("train"))} (CLXIII went live 10-25: no era control at one Mark)')
    a, b = halves(LR, 0)
    bad = [dict(x, react_s=x['react_s'] * 1.15, troop_depth=x['troop_depth'] + 1.0) for x in b]
    r1 = level_b(a, bad, th)
    lines.append(f'planted (react_s x1.15, troop depth +1 tile): passed={r1["passed"]} RMS {f2(r1["rms"])}')
    # siege controls
    cnt = Counter()
    for seed in range(100, 100 + nsp // 2):
        a, b = halves(L, seed)
        s = siege(a, b, th, B=200, seed=seed)
        cnt['all'] += s['passed']
        for k, v in s['tests'].items():
            cnt[k] += v['passed']
    lines.append(f'siege human control, {nsp // 2} halves of the calibration block: full {cnt["all"]}/{nsp // 2}; ' +
                 ', '.join(f'{k} {cnt[k]}' for k in FACT_KEYS))
    a, b = halves(L, 1)
    pl = [dict(r, xb=[[t, 1] for t, _ in r['xb']]) if r.get('xb') else r for r in b]                # planted: every X-Bow locks
    lines.append(f'planted siege (every X-Bow locks): passed={siege(a, pl, th, B=200)["passed"]}')
    lf = siege(L, L, th, B=10)['live']
    lines.append(f'live calibration siege facts: {json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in lf.items()})}')
    if hf_path:
        H, meta = hf_records(hf_path)
        HR = rows(H)
        lines.append(f'HF tier-A side records: {len(H)} (crforge build {meta.get("manifest", {}).get("crforge_sha", "?")[:8]})')
        feats = [k for k in STATS if k not in ('opp_el', 'pocket_share')]
        tags = sorted({r['tag'] for r in H})
        cnt = Counter()
        n_ctl = 20
        for seed in range(n_ctl):          # B-HF control: match-level halves at the B-HF size (2,000 games per archetype is the bar)
            ta, tb = halves(tags, seed)
            ta = set(ta[:2000])
            tb = set(tb[:2000])
            xa = [x for x, r in zip(HR, H) if r['tag'] in ta]
            xb = [x for x, r in zip(HR, H) if r['tag'] in tb]
            r = level_b(xa, xb, th, feats=feats, margin=th['B']['b_hf_per_stat_abs_d_max'])
            cnt['all'] += r['passed']; cnt['tost'] += r['pass_tost']; cnt['rms'] += r['pass_rms']
        lines.append(f'B-HF human control, {n_ctl} halves of 2,000 HF matches each (both sides, {len(feats)} stats, TOST margin '
                     f'{th["B"]["b_hf_per_stat_abs_d_max"]}): RMS {cnt["rms"]}/{n_ctl} TOST {cnt["tost"]}/{n_ctl} full {cnt["all"]}/{n_ctl}')
        rhl = level_b(HR[:4000], LR, th, feats=feats)
        lines.append(print_b('HF humans (4,000 sides) as "model" vs live calibration humans', rhl))
    txt = '\n'.join(lines)
    print(txt)
    if out:
        Path(out).write_text(txt + '\n', encoding='utf-8')


def main():
    th, sha = SC.load_thresholds()
    if sorted(th['B'].get('stats_closed_loop', STATS)) != sorted(STATS):
        raise SystemExit('card.py STATS differ from THRESHOLDS B.stats_closed_loop: refusing')
    th['_hf_ref'] = str(HERE / 'data' / 'hf_ref_bec5811a.json.gz')
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('card', 'score', 'selftest', 'prep'))
    ap.add_argument('--name')
    ap.add_argument('--ckpt', default=None, help='opponent checkpoint (pod path for card; default E4)')
    ap.add_argument('--ckpt-local', default=None, help='laptop path of the same checkpoint (level A)')
    ap.add_argument('--opp-t', default='0.1')
    ap.add_argument('--opp-extra', default='')
    ap.add_argument('--pod', type=int, default=32657)
    ap.add_argument('--workers', type=int, default=40)
    ap.add_argument('--seeds', type=int, nargs='*', default=[741200, 742000, 743000, 744000])
    ap.add_argument('--no-run', action='store_true', help='card: only fetch + score')
    ap.add_argument('--sim', default=None)
    ap.add_argument('--hf-sim', default=None)
    ap.add_argument('--hf', default=None, help='selftest: hf_ref.json.gz')
    ap.add_argument('--level-a-data', default=None)
    ap.add_argument('--level-a-mem', default=None)
    ap.add_argument('--no-c', action='store_true')
    ap.add_argument('--no-d', action='store_true', help='debug runs: never open the sealed block')
    ap.add_argument('--out', default=None)
    a = ap.parse_args()
    print(f'THRESHOLDS.json sha256 {sha} (matches HUMANLIKE.md)', flush=True)
    if a.cmd == 'prep':                    # cache the live records of the train + calibration blocks (never the sealed block)
        for b in ('calibration', 'train'):
            print(b, len(live_records(b)), flush=True)
    elif a.cmd == 'selftest':
        selftest(th, a.hf, out=a.out)
    elif a.cmd == 'score':
        score(a.name, a.sim, th, sha, (a.ckpt_local or a.ckpt, a.level_a_data, a.level_a_mem), a.hf_sim, not a.no_c, a.out, not a.no_d)
    else:
        card(a, th, sha)


if __name__ == '__main__':
    main()
