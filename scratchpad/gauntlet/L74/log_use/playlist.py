"""Play-list Log metrics computed the SAME way on pros, SIM and live (only both seats' public play lists: tick + card).

Sources: pros = habits/pro_sides.jsonl (Path of Legend sides of the exact icebow8 deck; mirrors dropped), SIM = W12 eval
o3_plays (vs the W7 opponent), live = log_use.py per_match.jsonl own_plays / opp_plays (PublicObserver plays).
Our hand is rebuilt from our own play order (8-card cycle: a played card is back in hand after 4 more of our plays), so
the Log state is known only after our first Log. Bait = log_use.CORE / EXT. "Revealed" = the opponent played it earlier.

  python playlist.py [--live per_match.jsonl]
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import glob
import json
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import log_use as L                                      # noqa: E402

PRO = REPO / 'scratchpad/gauntlet/L74/habits/pro_sides.jsonl'
LOG = 'the_log'
PUNISH = 120            # ticks: the lead's W14 punish window (bait card within 6 s after our Log)
REACT = 240             # ticks: our Log within 12 s after an enemy ground-troop play


def k(c):
    from pipeline import vocab
    return vocab.engine_key(str(c)).replace('-', '_')


def metrics(own, opp, end):
    """own / opp: [(tick, key)] sorted; -> per-match dict."""
    logs = [t for t, c in own if c == LOG]
    out = dict(logs=len(logs), minutes=end / 1200, bait=[], ground=[], punish=[], pre=None, post=None)
    if not logs:
        return out

    def log_out(t):                      # None before our first Log
        prev = [x for x in own if x[0] < t]
        li = max((i for i, x in enumerate(prev) if x[1] == LOG), default=None)
        return None if li is None else len(prev) - 1 - li < 4
    core_t = min((t for t, c in opp if c in L.CORE), default=None)
    for t, c in opp:
        if c in L.EXT:
            s = log_out(t)
            if s is not None:
                out['bait'].append((c, s))
        tr = L.TRAITS.get(c)
        if tr and tr['kind'] == 'troop' and not tr['air'] and log_out(t) is False:
            out['ground'].append(any(0 <= lt - t <= REACT for lt in logs))
    if core_t is not None:
        out['punish'] = [any(0 < t - lt <= PUNISH for t, c in opp if c in L.CORE) for lt in logs]
        out['pre'] = (sum(lt < core_t for lt in logs), core_t / 1200)
        out['post'] = (sum(lt >= core_t for lt in logs), max(0.0, end - core_t) / 1200)
    seq = [x for x in own if x[0] >= logs[0]] + [(end, None)]
    out_t = tot = 0; since = None
    for (t0, c0), (t1, _) in zip(seq, seq[1:]):
        since = 0 if c0 == LOG else (since + 1 if since is not None else None)
        tot += t1 - t0; out_t += (t1 - t0) * (since < 4)
    out['base'] = out_t / tot if tot else None
    out['core_rev'] = core_t is not None
    return out


def ci(xs, f, B=1000):
    rng = random.Random(0)
    v = sorted(f([rng.choice(xs) for _ in xs]) for _ in range(B))
    return v[int(.025 * B)], v[int(.975 * B) - 1]


def report(label, rows):
    if not rows:
        return [f'- {label}: no rows']
    M = L.mean
    b = [x for r in rows for x in r['bait']]
    cb = [s for c, s in b if c in L.CORE]
    pun = [x for r in rows for x in r['punish']]
    g = [x for r in rows for x in r['ground']]
    rev = [r for r in rows if r.get('core_rev')]
    pre = sum(r['pre'][0] for r in rev) / max(1e-9, sum(r['pre'][1] for r in rev))
    post = sum(r['post'][0] for r in rev) / max(1e-9, sum(r['post'][1] for r in rev))
    norev = [r for r in rows if not r.get('core_rev')]
    lpm = [r['logs'] for r in rows]
    lo, hi = ci(lpm, M)
    plo, phi = ci(pun, M) if pun else (float('nan'),) * 2
    return [f'- {label}: {len(rows)} matches; Logs/match {M(lpm):.2f} [{lo:.2f}, {hi:.2f}], /min {sum(lpm)/sum(r["minutes"] for r in rows):.2f}; '
            f'win {M(r["won"] for r in rows):.3f}; opp revealed a CORE bait card in {len(rev)/len(rows):.3f}',
            f'  - CORE bait plays/match {len(cb)/len(rows):.2f}, Log out of hand at them {M(cb):.3f} (EXT {M(s for _, s in b):.3f}) vs '
            f'time share Log out {M(r["base"] for r in rows if r.get("base") is not None):.3f}',
            f'  - punish rate (our Log, opp has/will reveal CORE bait, a CORE bait play within 6 s): {M(pun):.3f} [{plo:.3f}, {phi:.3f}] n {len(pun)}',
            f'  - enemy ground-troop plays with our Log in hand followed by a Log within 12 s: {M(g):.3f} (n {len(g)})',
            f'  - Logs/min in CORE-bait matches before the first reveal {pre:.2f}, after {post:.2f}; matches without a reveal '
            f'{sum(r["logs"] for r in norev)/max(1e-9, sum(r["minutes"] for r in norev)):.2f}',
            f'  - win: CORE-revealed {M(r["won"] for r in rev):.3f} vs not {M(r["won"] for r in norev):.3f}']


def pros():
    rows = []
    for line in open(PRO, encoding='utf-8'):
        j = json.loads(line)
        if not j.get('icebow8') or sorted(map(k, j.get('opp_deck') or [])) == sorted(map(k, j['deck'])):
            continue
        ev = j['ev']
        own = [(e[0], k(e[2])) for e in ev if e[1] == 'me']
        opp = [(e[0], k(e[2])) for e in ev if e[1] == 'op']
        if not own:
            continue
        end = max(e[0] for e in ev)
        r = metrics(own, opp, end); r['won'] = bool(j.get('win'))
        rows.append(r)
    return rows


def sim(root_glob):
    rows = defaultdict(list)
    for f in glob.glob(root_glob, recursive=True):
        arm = next((p for p in Path(f).parts if p.startswith('w12_')), 'sim')
        arm = arm.rsplit('_7', 1)[0] if arm.count('_7') else arm
        for line in open(f, encoding='utf-8'):
            j = json.loads(line)
            o3 = j.get('o3_plays')
            if not o3:
                continue
            own = [(t, k(c)) for t, c in o3['learner']]
            opp = [(t, k(c)) for t, c in o3['opp']]
            r = metrics(own, opp, j.get('end_tick') or 3600); r['won'] = j.get('outcome') == 'win'
            rows[arm].append(r)
    return rows


def live(path):
    rows = defaultdict(list)
    for line in open(path, encoding='utf-8'):
        j = json.loads(line)
        if 'own_plays' not in j:
            continue
        own = [(t, c.replace('-', '_')) for t, c in j['own_plays']]
        opp = [(t, c) for t, c in j['opp_plays']]
        r = metrics(sorted(own), sorted(opp), j['ticks']); r['won'] = bool(j['won'])
        rows[j['mark']].append(r)
    return rows


DECKS = {'league decks_rl.json (share/data_20261020 copy of the pods file)': REPO / 'share/data_20261020/decks_rl.json',
         'W7 exploiter decks_live_train.json': REPO / 'scratchpad/gauntlet/L74/mix/decks_live_train.json'}


def decks():
    """training-opponent deck files: share of decks holding a CORE / EXT bait card (any JSON layout of 8-card lists)."""
    out = []
    for label, p in DECKS.items():
        if not p.exists():
            out.append(f'- {label}: MISSING'); continue
        ds = []

        def walk(o):
            if isinstance(o, list) and len(o) == 8 and all(isinstance(c, str) for c in o):
                ds.append({k(c.split('@')[0]) for c in o})
            elif isinstance(o, dict):
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(json.loads(p.read_text(encoding='utf-8')))
        core = sum(bool(d & set(L.CORE)) for d in ds); ext = sum(bool(d & set(L.EXT)) for d in ds)
        out.append(f'- {label}: {len(ds)} decks, CORE bait {core/len(ds):.3f}, any EXT {ext/len(ds):.3f}')
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', default=str(HERE / 'per_match.jsonl'))
    ap.add_argument('--sim', default='C:/Users/benpe/pod_backup_weekend/tonight1020/*/w12_*/**/matches.jsonl')
    a = ap.parse_args(argv)
    out = ['## training-opponent decks'] + decks() + ['## pros (icebow8, Path of Legend)'] + report('pros', pros())
    out.append('## SIM (W12 eval vs the W7 opponent)')
    for arm, rs in sorted(sim(a.sim).items()):
        out += report(arm, rs)
    if Path(a.live).exists():
        out.append('## live')
        lv = live(a.live)
        for mk, rs in sorted(lv.items(), key=lambda kv: -len(kv[1])):
            if len(rs) >= 20:
                out += report(mk, rs)
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1:])
