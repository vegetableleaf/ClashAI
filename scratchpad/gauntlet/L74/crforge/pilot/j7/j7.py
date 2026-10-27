"""J7 whole-match open loop (ticket A2b-2): crforge vs fin15 vs fin16 on the SAME extracted inputs (extract/EXTRACT.md).

    python -I j7.py truth  --inputs IN.jsonl --out truth.jsonl            # laptop: live tower rows from our live logs
    python -I j7.py plans  --inputs IN.jsonl --out DIR                    # per-match driver plans (both engines read them)
    python -I j7.py score  --truth truth.jsonl --runs DIR [--inputs IN.jsonl] --out DIR   # J7 tables + CIs + paired diff
Engine runs: J7Run.java (crforge, pod 33920) and fin_run.py (RoyaleSim fin15 / fin16, pod 32657) write one
<match>.json per (engine, mode, tick) arm: {"match", "rows": [[t, T0L, T0R, T0K, T1L, T1R, T1K, awake0, awake1]] (a row on
every change), "end": tick, "refused": {...}}.

Grading is replay_metrics.j7() unchanged: live rows = our frame log's towers (reader kind 13 = king awake), sim rows = the
engine's tower state at the same tick. The ceiling is the engine against itself with every play moved to its other
candidate run tick (run_ticks hi instead of lo): the frame gap is the only play-tick freedom the inputs leave.
"""
import argparse, itertools, json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(ROOT))
IDS = ('T0L', 'T0R', 'T0K', 'T1L', 'T1R', 'T1K')
# fillers for unseen opponent slots: plain non-champion troops, same row name in crforge and RoyaleSim (a: name pairs)
FILLERS = ('Musketeer', 'Wizard', 'Bats', 'Minions', 'Cannon', 'Pekka', 'Prince', 'BabyDragon', 'MiniPekka', 'Bowler')
END = 6000                 # fights.TIME_OUT_TICK: J7 grades live frames before it (the whole-match selector's t1)


def cycle_fail(deal, seq):
    """extract.cycle_fail (copied: extract.py is another ticket's working file)."""
    hand, queue = list(deal[:4]), list(deal[4:])
    for i, k in enumerate(seq):
        if k not in hand:
            return i
        hand.remove(k); hand.append(queue.pop(0)); queue.append(k)
    return None


def best_deal(seq):
    """A deal under which the longest prefix of the plays is legal (the record's fitting deal when one exists)."""
    best, bd = -1, None
    for d in itertools.permutations(range(8)):
        f = cycle_fail(d, seq)
        f = len(seq) if f is None else f
        if f > best:
            best, bd = f, list(d)
            if f == len(seq):
                break
    return bd, best


# ------------------------------------------------------------------ truth (laptop)

def truth(inputs, out):
    from scratchpad.gauntlet.L74.parity import fights as F
    with open(out, 'w') as w:
        for line in open(inputs):
            r = json.loads(line)
            m, why = F.read_match(F.ps.LIVE / (r['match'] + '.jsonl'))
            if m is None:
                w.write(json.dumps(dict(match=r['match'], skipped=why)) + '\n'); continue
            maxhp, rows = {}, []
            for t, bodies in m['frames']:
                if t >= END:
                    break
                tw = {b['id']: b for b in bodies if b['tower']}
                for k, b in tw.items():
                    maxhp.setdefault(k, b['max_hp'])
                rows.append([t] + [tw[k]['hp'] if k in tw else None for k in IDS] +
                            [int(f'T{s}K' in tw and tw[f'T{s}K'].get('kind') == 13) for s in (0, 1)])
            w.write(json.dumps(dict(match=r['match'], my_side=m['side'], maxhp=maxhp, rows=rows)) + '\n')
            print(r['match'], len(rows), flush=True)


# ------------------------------------------------------------------ plans

def plans(inputs, out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    idx = []
    for line in open(inputs):
        r = json.loads(line)
        my = r['my_side']
        deal = {}
        for s in (0, 1):
            seq = [p['deck_index'] for p in sorted(r['plays'], key=lambda p: p['tick']) if p['side'] == s and p['kind'] == 'play']
            d = r['deal'].get(str(s)) or (r['opp_deal_fit'] if s != my else None)
            how = 'own_exact' if s == my and d else 'opp_fit' if d else None
            if d and sorted(d) != list(range(8)):     # own_order with an unread slot (-1): not a deal
                d, how = None, None
            if not d:
                d, n = best_deal(seq); how = f'best_prefix_{n}_of_{len(seq)}'
            deal[s] = dict(order=d, how=how, fail=cycle_fail(d, seq))
        cmds, last = [], {}
        for k, p in enumerate(sorted(r['plays'], key=lambda p: (p['tick'], p['side']))):
            if p['kind'] == 'play':
                s, i = p['side'], p['deck_index']
                cmds.append(dict(kind='play', side=s, card=p['card'], display=p['name'], deck_index=i, form=p['form'],
                                 level=r['sides'][str(s)]['levels'][i], x=p['x'], y=p['y'],
                                 lo=p['run_ticks'][0], hi=p['run_ticks'][1], tick=p['tick']))
                last[s, p['name']] = len(cmds) - 1
            else:   # ability: the unit of its card's last play on that side (crforge names it cmd<k>_0)
                cmds.append(dict(kind='ability', side=p['side'], display=p['name'], unit_cmd=last.get((p['side'], p['name'])),
                                 lo=p['run_ticks'][0], hi=p['run_ticks'][1], tick=p['tick']))
        S = {s: dict(r['sides'][s]) for s in '01'}
        filled = {}
        for s in '01':                    # A2b-1b log-only decks: an unseen slot (None) gets a never-played filler card
            spare = [c for c in FILLERS if c not in S[s]['deck']]
            for k in range(8):
                if S[s]['deck'][k] is None:
                    c = spare.pop(0); filled.setdefault(s, []).append(c)
                    S[s]['deck'] = S[s]['deck'][:k] + [c] + S[s]['deck'][k + 1:]
                    S[s]['display'] = S[s]['display'][:k] + [c] + S[s]['display'][k + 1:]
                    S[s]['levels'] = S[s]['levels'][:k] + [16] + S[s]['levels'][k + 1:]
        plan = dict(match=r['match'], my_side=my, seed=0, filled=filled,
                    words=[S['0']['word'] or 0, S['1']['word'] or 0],   # words only seed the shuffle; the deal replaces it
                    decks=[S['0']['deck'], S['1']['deck']], display=[S['0']['display'], S['1']['display']],
                    levels=[S['0']['levels'], S['1']['levels']], slots=[S['0']['slot_flags'], S['1']['slot_flags']],
                    towers=[[S[s]['towers']['group'], S[s]['towers']['king_level'] or S[s]['towers']['level'], S[s]['towers']['level']] for s in '01'],
                    deal=[deal[0]['order'], deal[1]['order']], deal_how=[deal[0]['how'], deal[1]['how']],
                    deal_fail=[deal[0]['fail'], deal[1]['fail']], cmds=cmds)
        (out / (r['match'] + '.json')).write_text(json.dumps(plan))
        idx.append(r['match'])
    with open(out / 'index.txt', 'w', newline='\n') as w:     # LF: the pod's shell loops read it
        w.write('\n'.join(idx) + '\n')
    print(len(idx), 'plans')


# ------------------------------------------------------------------ score

def at(rows, t):
    """The engine row in force at tick t (rows sorted, one per change)."""
    lo, hi = 0, len(rows) - 1
    if rows[0][0] > t:
        return rows[0]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if rows[mid][0] <= t:
            lo = mid
        else:
            hi = mid - 1
    return rows[lo]


def bodies(row, maxhp, live):
    out = []
    for k, hp in zip(IDS, row[1:7]):
        if hp is None or (not live and hp <= 0):
            continue
        b = dict(id=k, hp=hp, max_hp=maxhp.get(k, 0), tower=True)
        if k.endswith('K'):
            if live:
                b['kind'] = 13 if row[7 + int(k[1])] else 0
            else:
                b['awake'] = bool(row[7 + int(k[1])])
        out.append(b)
    return out


def grade(tr, run, alt):
    from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as RM
    rows = [(lr[0], bodies(lr, tr['maxhp'], True), bodies(at(run['rows'], lr[0]), tr['maxhp'], False)) for lr in tr['rows']]
    pert = [[(t, lv, bodies(at(alt['rows'], t), tr['maxhp'], False)) for t, lv, _ in rows]] if alt else []
    return RM.j7(dict(side=tr['my_side'], match=tr['match']), [], None, rows, pert)['j7']


def score(truth_path, runs, inputs, out):
    from scratchpad.gauntlet.L74.parity.metrics import replay_metrics as RM
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    tr = {d['match']: d for d in map(json.loads, open(truth_path)) if 'rows' in d}
    meta = {}
    if inputs:
        for line in open(inputs):
            r = json.loads(line)
            cyc = r['own_cycle_fail'] is None and r['opp_fitting_deals'] > 0
            meta[r['match']] = dict(nofit=r['opp_fitting_deals'] == 0, flags=r['flags'], noflag=not r['flags'],
                                    api=r.get('source') != 'live_only', cycle_ok=cyc,
                                    deck8=cyc and not any(':deck_seen:' in f for f in r['flags']),
                                    opp16=r['sides'][str(1 - r['my_side'])]['towers']['level'] == 16)
    arms = sorted(p.name for p in Path(runs).iterdir() if p.is_dir())
    res = {}                       # arm -> match -> j7 dict (+ refused)
    for arm in arms:
        if not arm.endswith('_lo'):
            continue
        base = arm[:-3]
        res[base] = {}
        for p in sorted((Path(runs) / arm).glob('*.json')):
            if p.stem not in tr:
                continue
            run = json.loads(p.read_text())
            if 'rows' not in run:
                res[base][p.stem] = dict(crash=run.get('crash')); continue
            ap = Path(runs) / (base + '_hi') / p.name
            alt = json.loads(ap.read_text()) if ap.exists() else None
            alt = alt if alt and 'rows' in alt else None
            j = grade(tr[p.stem], run, alt)
            j['refused'] = run.get('refused', {}); j['plays_ok'] = run.get('plays_ok'); j['plays_n'] = run.get('plays_n')
            res[base][p.stem] = j
    (out / 'per_match.json').write_text(json.dumps(res, default=str))
    mean = lambda xs: sum(xs) / len(xs) if xs else float('nan')
    king_ok = lambda a, b: (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 100)
    Q = dict(seq=lambda r: float(r['seq_same']), result=lambda r: float(r['result_live'] == r['result_sim']),
             timing=lambda r: float(r['seq_timing']), traj=lambda r: r['traj_ok'] / max(1, r['traj_n']),
             king=lambda r: mean([king_ok(r['king_live'][s], r['king_sim'][s]) for s in (0, 1)]))
    CQ = dict(seq=lambda r, c: float(c['seq_same']), result=lambda r, c: float(c['result'] == r['result_sim']),
              timing=lambda r, c: float(c['seq_timing']), traj=lambda r, c: c['traj_ok'] / max(1, c['traj_n']),
              king=lambda r, c: mean([king_ok(r['king_sim'][s], c['king'][s]) for s in (0, 1)]))
    fell = {m for d in res.values() for m, r in d.items() if r.get('falls_live')}
    g = lambda m, k: meta.get(m, {}).get(k, False)
    if meta and not any(g(m, 'api') is False for m in meta):     # the A2b-2 set (API only): its original subsets
        subsets = {'all': lambda m: True, 'no-flag': lambda m: g(m, 'noflag'),
                   'all but opp-deal misfits': lambda m: not g(m, 'nofit'), 'opp-deal misfits only': lambda m: g(m, 'nofit')}
    elif meta:                                                   # A2b-2b tiers (EXTRACT.md A2b-1b) and splits
        subsets = {'deck8 (PRIMARY)': lambda m: g(m, 'deck8'),
                   'deck8, API-backed (API levels)': lambda m: g(m, 'deck8') and g(m, 'api'),
                   'deck8, log-only (hp-derived levels)': lambda m: g(m, 'deck8') and not g(m, 'api'),
                   'deck8, opponent towers L16': lambda m: g(m, 'deck8') and g(m, 'opp16'),
                   'deck8, opponent towers below L16': lambda m: g(m, 'deck8') and not g(m, 'opp16'),
                   'deck8, live >= 1 tower fall': lambda m: g(m, 'deck8') and m in fell,
                   'cycle_ok': lambda m: g(m, 'cycle_ok'),
                   'any (every RNG-free match)': lambda m: True,
                   'any, log-only': lambda m: not g(m, 'api'),
                   'any, opponent-deal misfits only': lambda m: g(m, 'nofit')}
    else:
        subsets = {'all': lambda m: True}
    # a match with no live tower fall agrees on the crown sequence whenever the engine fells none: grade the rest apart
    subsets['live >= 1 tower fall'] = lambda m: m in fell
    common = set.intersection(*[{m for m, r in d.items() if 'seq_same' in r} for d in res.values()]) if res else set()
    lines, rep = [], {}
    lines.append(f"arms: {sorted(res)}; matches graded by every arm: {len(common)}; crashes: "
                 f"{ {a: sum('crash' in r for r in d.values()) for a, d in res.items()} }")
    for sname, sel in subsets.items():
        ms = sorted(m for m in common if sel(m))
        if not ms:
            continue
        lines.append(f"\n## subset {sname}: {len(ms)} matches")
        lines.append('| arm | crown sequence | result | falls in time | trajectory | king wake | ceiling seq (lo vs hi tick) | refused plays / plays |')
        lines.append('|---|---|---|---|---|---|---|---|')
        for a in sorted(res):
            d = res[a]
            cells = []
            for q, f in Q.items():
                v, ci = RM.boot([(m, f(d[m])) for m in ms], mean)
                cells.append(f"{v:.3f} [{ci[0]:.3f}, {ci[1]:.3f}]")
                rep.setdefault(sname, {}).setdefault(a, {})[q] = dict(v=v, ci=ci, n=len(ms))
            cs = [CQ['seq'](d[m], d[m]['ceiling'][0]) for m in ms if d[m].get('ceiling')]
            refd = sum(sum(d[m]['refused'].values()) for m in ms); pn = sum(d[m].get('plays_n') or 0 for m in ms)
            lines.append(f"| {a} | " + ' | '.join(cells) + f" | {mean(cs):.3f} (n {len(cs)}) | {refd} / {pn} |")
            rep[sname][a]['ceiling_seq'] = mean(cs)
        # paired differences: each crforge arm minus each RoyaleSim arm, per match, bootstrap over matches
        for a in sorted(x for x in res if x.startswith('crforge')):
            for b in sorted(x for x in res if x.startswith('fin')):
                for q in ('seq', 'result', 'timing', 'traj', 'king'):
                    v, ci = RM.boot([(m, Q[q](res[a][m]) - Q[q](res[b][m])) for m in ms], mean)
                    rep[sname].setdefault('diff', {})[f'{a} - {b} {q}'] = dict(v=v, ci=ci)
                    if q in ('seq', 'result', 'timing'):
                        lines.append(f"   paired {a} - {b}, {q}: {v:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    # diagnosis aids: refusal reasons and the first-divergence tick, per arm
    lines.append('\n## refusals and first divergence')
    for a in sorted(res):
        d = res[a]
        rc = Counter()
        for m in common:
            rc.update(d[m]['refused'])
        fd = sorted(d[m]['first_div']['tick'] for m in common if d[m].get('first_div'))
        med = fd[len(fd) // 2] if fd else None
        lines.append(f"- {a}: refused {dict(rc.most_common(8))}; first tower divergence in {len(fd)}/{len(common)} matches, median tick {med}")
    (out / 'SCORE.md').write_text('\n'.join(lines) + '\n')
    (out / 'score.json').write_text(json.dumps(rep, indent=1, default=str))
    print('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['truth', 'plans', 'score'])
    ap.add_argument('--inputs'); ap.add_argument('--out', required=True)
    ap.add_argument('--truth'); ap.add_argument('--runs')
    a = ap.parse_args()
    if a.mode == 'truth':
        truth(a.inputs, a.out)
    elif a.mode == 'plans':
        plans(a.inputs, a.out)
    else:
        score(a.truth, a.runs, a.inputs, a.out)


if __name__ == '__main__':
    main()
