"""W19 (10-22) first-divergence CLASSIFIER for failing J1 fights (an automated diag_night/r3a/div.py): re-runs the listed
fights at K = 0 and, for every anchor body whose fate disagrees (or the spell's hit set / the tower damage), finds the FIRST
divergence among the bodies causally next to it -- the body itself, what attacked it (live phase-3 targets, SIM target_uid)
and what it attacked -- up to the disagreement: hp (2 frames running), position > 0.5 tile (2 frames), target (2 frames),
presence (a body one run has and the other lacks); plus the first divergence of the whole fight. Derived numbers only.

  python cls.py run --base BASE_DIR --out OUT_DIR --live LIVE_DIR [--workers N]
BASE_DIR = a fights.py run (matches/*.json); its stamped matches' strict-clean failing fights (live vs sim[0]) are re-run.
Engine and exports: as for fights.py (PARITY_SIM_PATH / ROYALE_RUNTIME; PARITY_ATTACKS / PARITY_BUFFS as for the base run).
Output OUT_DIR/cls.jsonl, one line per match: {match, err, fights: [classification]} (resumable)."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import glob
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

FORM = ('', ' evo', ' hero')
POS_TOL, STREAK = 500, 2
HP_TOL = int(os.environ.get('CLS_HP_TOL', '5'))
TGT_STRICT = os.environ.get('CLS_TGT_STRICT') == '1'   # 1 = pass-1 rule (a live tower target vs SIM None counts)
ALL_FIGHTS = os.environ.get('CLS_ALL') == '1'          # 1 = classify passing fights too (artefact check: how often do they diverge?)


def lab(side, obs, name, form=0):
    return ('own ' if side == obs else 'opp ') + name + FORM[form or 0]


def failing(base, stamped=True, mode='strict'):
    """{match stem: [(t0, anchor name, anchor tick)]}: strict-clean fights whose live vs sim[0] card view disagrees."""
    out = defaultdict(list)
    for f in sorted(glob.glob(str(Path(base) / 'matches' / '*.json'))):
        d = json.load(open(f, encoding='utf-8'))
        s = d['summary']
        if s.get('skipped') or (stamped and not s.get('phase3b_births')):
            continue
        for r in d['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, mode):
                continue
            if ALL_FIGHTS or not F.card_agree(c['live'], c['sim'][0])[0]:
                a = r['anchor']
                out[s['match']].append((r['t0'], a['name'], a['tick']))
    return out


# ------------------------------------------------------------------ hooks (div.py's)
CAP, SELECT = {}, set()
_bodies, _measure, _run_fight, _cut = F.Engine.bodies, F.measure, F.run_fight, F.cut


def bodies(self, by):
    st, out = _bodies(self, by)
    rows = [dict(zip(self.F, r)) for r in st['entities']]
    uid = {e['uid']: o['id'] for e, o in zip(rows, out)}
    for e, o in zip(rows, out):
        o['tgt'] = uid.get(e['target_uid'])
    return st, out


def measure(rows, setup, flags, cat, stamp):
    CAP['rows'], CAP['setup'] = rows, setup
    return _measure(rows, setup, flags, cat, stamp)


def run_fight(eng, m, events, fight, catalog, *a, **k):
    CAP.clear()
    r = _run_fight(eng, m, events, fight, catalog, *a, **k)
    an = events[fight['anchor']]
    if (fight['t0'], an['name'], an['tick']) in SELECT and 'rows' in CAP and r.get('card'):
        try:
            r['cls'] = classify(m, events, fight, r, CAP['rows'], CAP['setup'], catalog)
        except Exception as e:  # noqa: BLE001
            r['cls'] = dict(error=type(e).__name__ + ':' + str(e)[:160])
    return r


def cut(m, events, window):
    T0 = {t0 for t0, _, _ in SELECT}
    return [f for f in _cut(m, events, window) if f['t0'] in T0]


def live_targets(m, rows):
    out = {}
    for t, live, _ in rows:
        A = m['attacks'].get(t) or m['attacks'].get(t - 1) or m['attacks'].get(t + 1) or {}
        g2id = {bd.get('gen'): bd['id'] for bd in live if bd.get('gen') is not None}
        out[t] = {bd['id']: g2id.get(A[bd['gen']][0]) for bd in live if bd.get('gen') in A}
    return out


def classify(m, events, fight, r, rows, setup, catalog):
    a = events[fight['anchor']]
    obs = m['side']
    L, S0 = r['card']['live'], r['card']['sim'][0]
    ok, mis, n, tok = F.card_agree(L, S0)
    pairs = F.initial_pairs(rows, setup, catalog)
    inv = {s: l for l, s in pairs.items() if s}
    LT = live_targets(m, rows)
    t0, t_end = rows[0][0], rows[-1][0]
    setup_ids = {bd['id'] for bd in setup}
    info = {}                                    # key (live id, or the s-id of an unpaired SIM body) -> (name, side, setup, born)
    life = defaultdict(lambda: [None, None])     # key -> [last live tick, last SIM tick]
    first_live, first_sim = {}, {}
    nm = lambda bd, w: bd['name'] if w == 2 else (catalog.get(bd['card_id']) or {}).get('display_name', str(bd['card_id']))
    for t, live, simb in rows:
        for bd in live:
            if not bd['tower']:
                info.setdefault(bd['id'], (nm(bd, 1), bd['side'], bd['id'] in setup_ids, t))
                life[bd['id']][0] = t
                first_live.setdefault(bd['id'], t)
        for s in simb:
            if not s['tower']:
                k = inv.get(s['id'], s['id'])
                info.setdefault(k, (nm(s, 2), s['side'], k in setup_ids, t))
                life[k][1] = t
                first_sim.setdefault(k, t)

    def death(k, w):
        v = life[k][w]
        return v if v is not None and v < t_end else None
    until = min((e['tick'] for e in events if e['kind'] == 'play' and e['side'] == a['side'] and e['name'] == a['name']
                 and e['tick'] > a['tick']), default=fight['t1'] + 1)
    anc = [k for k, v in info.items() if v[1] == a['side'] and v[0] == a['name'] and not v[2] and a['tick'] - 2 <= v[3] < until]
    bad = []                                     # (key, kind, tick of the disagreement)
    if L['spell']:
        for k in sorted(set(L['hit']) | set(S0['hit'])):
            x, y = L['enemy'].get(k, 'missing'), S0['enemy'].get(k, 'missing')
            same = 'missing' not in (x, y) and (x is None) == (y is None) and (x is None or abs(x - y) <= F.DEATH_TOL)
            if not same:
                tk = min([v for v in (x, y) if isinstance(v, int)] or [a['tick'] + 10])
                kind = 'spell_hit_live_only' if y == 'missing' else 'spell_hit_sim_only' if x == 'missing' else 'spell_fate'
                bad.append((inv.get(k, k), kind, tk))
    else:
        for k in anc:
            dl, ds = death(k, 0), death(k, 1)
            if life[k][0] is None:
                bad.append((k, 'body_sim_only', first_sim.get(k, t0)))
            elif life[k][1] is None:
                bad.append((k, 'body_live_only', first_live.get(k, t0)))
            elif (dl is None) != (ds is None):
                late = (dl if dl is not None else ds) >= t_end - F.DEATH_TOL
                if not late:
                    bad.append((k, 'survival_' + ('sim_dies' if ds is not None else 'live_dies'), dl if dl is not None else ds))
            elif dl is not None and abs(dl - ds) > F.DEATH_TOL:
                bad.append((k, 'death_' + ('sim_early' if ds < dl else 'sim_late'), min(dl, ds)))
    if not bad and not tok:
        kind = 'tower_' + ('sim_more' if S0['tower'] > L['tower'] else 'sim_less')
        bad = [(k, kind, t_end) for k in anc[:1]] or [(None, kind, t_end)]

    def related(k, tk):
        R = {k}
        sk = pairs.get(k, k) if not str(k).startswith('s') else k
        for t, live, simb in rows:
            if t > tk:
                break
            for x, tg in LT.get(t, {}).items():
                if tg == k or x == k:
                    R.add(x); R.add(tg)
            for s in simb:
                if sk and (s.get('tgt') == sk or s['id'] == sk):
                    R.add(inv.get(s['id'], s['id'])); R.add(inv.get(s.get('tgt'), s.get('tgt')))
        R.discard(None)
        return R

    def first_div(R, tk):
        streak, first = Counter(), [None]

        def note(t, kind, k, extra=None):
            if first[0] is None or t < first[0][0]:
                first[0] = (t, kind, k, extra)
        for t, live, simb in rows:
            if t > tk + 4 or first[0] is not None:
                break
            Lb = {bd['id']: bd for bd in live}
            Sb = {s['id']: s for s in simb}
            for bd in live:
                if bd['tower']:
                    s = Sb.get(bd['id'])
                    if (R is None or 'T' in R) and s:
                        streak[bd['id'], 'thp'] = streak[bd['id'], 'thp'] + 1 if s['hp'] != bd['hp'] else 0
                        if streak[bd['id'], 'thp'] == STREAK:
                            note(t, 'tower_hp', bd['id'])
                    continue
                k = bd['id']
                if R is not None and k not in R:
                    continue
                sid = pairs.get(k)
                s = Sb.get(sid) if sid else None
                if s is None:
                    if sid is None and t - first_live[k] >= 4:
                        note(t, 'presence_live_only', k)
                    elif sid is not None and life[k][1] is not None and life[k][1] < t:
                        note(t, 'gone_sim_first', k)
                    elif sid is not None and first_sim.get(k, -1) > t and t - first_live[k] >= 4:
                        note(t, 'appear_sim_late', k)       # pass 3: a body the SIM makes later than live (spawn timing)
                    continue
                # pass 3: hp agrees within HP_TOL (a building's lifetime decay rounds 1 hp apart live / SIM: 2096 vs 2097)
                for kind, cond in (('hp', abs(s['hp'] - bd['hp']) > HP_TOL),
                                   ('pos', math.hypot(s['x'] - bd['x'], s['y'] - bd['y']) > POS_TOL),
                                   # a live crown-tower target against no SIM target is not a divergence: the reader names
                                   # the tower a unit walks to, the SIM sets target_uid only once it locks (W19 pass 1: 380 of
                                   # 518 'tgt' firsts were exactly this, 195 of them on the 4th tick)
                                   ('tgt', LT.get(t, {}).get(k) is not None and pairs.get(LT[t][k], LT[t][k]) != s.get('tgt')
                                    and not (str(LT[t][k]).startswith('T') and s.get('tgt') is None and not TGT_STRICT))):
                    streak[k, kind] = streak[k, kind] + 1 if cond else 0
                    if streak[k, kind] == STREAK:
                        note(t, kind, k, (LT[t][k], inv.get(s.get('tgt'), s.get('tgt'))) if kind == 'tgt' else None)
            for s in simb:
                if s['tower']:
                    continue
                k = inv.get(s['id'], s['id'])
                if R is not None and k not in R:
                    continue
                if k == s['id'] and t - first_sim[k] >= 4:
                    note(t, 'presence_sim_only', k)
                elif k != s['id'] and k not in Lb and life[k][0] is not None and life[k][0] < t:
                    note(t, 'gone_live_first', k)
                elif k != s['id'] and k not in Lb and first_live.get(k, -1) > t and t - first_sim[k] >= 4:
                    note(t, 'appear_sim_early', k)          # pass 3: a body the SIM makes earlier than live (spawn timing)
        return first[0]

    def desc(fd):
        if fd is None:
            return None
        t, kind, k, extra = fd
        if kind == 'tower_hp':
            return dict(dt=t - t0, kind=kind, body=('own ' if k[1] == str(obs) else 'opp ') + 'tower')
        nm_, side, st, born = info.get(k, ('?', None, None, None))
        d = dict(dt=t - t0, kind=kind, body=lab(side, obs, nm_) if side is not None else str(k), setup=st,
                 born=None if born is None else born - t0, anchor=k in anc)
        if extra:
            d['tgt'] = [info.get(x, ('tower' if str(x).startswith('T') else '?',))[0] if x else None for x in extra]
        return d
    out = dict(ok=ok, lab=lab(a['side'], obs, a['name'], a['form']), spell=L['spell'], mis=mis, n=n, tower_ok=tok,
               tl=L['tower'], ts=S0['tower'], t0=t0, anchor_dt=a['tick'] - t0, src=a.get('source'),
               events=[(e['tick'] - t0, 'own' if e['side'] == obs else 'opp', e['name'], e.get('source'))
                       for e in (events[j] for j in fight['events'])][:12],
               flags=sorted(r['flags']), bad=[])
    for k, kind, tk in bad[:6]:
        R = related(k, tk) if k else None
        if R is not None and not tok:
            R.add('T')
        d0 = desc((tk, 'x', k, None)) if k else None
        out['bad'].append(dict(kind=kind, dt=tk - t0, body=d0 and d0['body'], first=desc(first_div(R, tk)), nrel=len(R or ())))
    out['first_global'] = desc(first_div(None, t_end))
    return out


def one(job):
    path, sel, out_dir = job
    SELECT.clear()
    SELECT.update(tuple(x) for x in sel)
    tmp = tempfile.mkdtemp(dir=out_dir)
    os.makedirs(tmp + '/matches')
    try:
        F.run_match(path, 240, tmp, 0)
        d = json.load(open(f'{tmp}/matches/{Path(path).stem}.json'))
        res = []
        for r in d.get('fights', []):
            if 'cls' in r:
                c = r['cls']
                c['match'] = d['summary']['match']
                res.append(c)
        return Path(path).stem, res, None
    except Exception as e:  # noqa: BLE001
        return Path(path).stem, [], type(e).__name__ + ':' + str(e)[:200]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def init():
    F.Engine.bodies, F.measure, F.run_fight, F.cut = bodies, measure, run_fight, cut


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run'])
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--live', required=True)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int, default=0)
    ar = ap.parse_args()
    o = Path(ar.out)
    o.mkdir(parents=True, exist_ok=True)
    fl = failing(ar.base)
    done = {json.loads(x)['match'] for x in open(o / 'cls.jsonl')} if (o / 'cls.jsonl').exists() else set()
    jobs = [(str(Path(ar.live) / (k + '.jsonl')), v, ar.out) for k, v in sorted(fl.items()) if k not in done]
    jobs = jobs[:ar.limit] if ar.limit else jobs
    print('failing fights', sum(len(v) for v in fl.values()), 'matches', len(fl), 'to run', len(jobs), flush=True)
    with ProcessPoolExecutor(ar.workers, initializer=init) as ex, open(o / 'cls.jsonl', 'a') as fo:
        for fut in as_completed([ex.submit(one, j) for j in jobs]):
            stem, res, err = fut.result()
            fo.write(json.dumps(dict(match=stem, err=err, fights=res)) + '\n')
            fo.flush()
    print('CLS_DONE', flush=True)


if __name__ == '__main__':
    main()
