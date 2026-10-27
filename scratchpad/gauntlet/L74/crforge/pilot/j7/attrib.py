"""Attribution of the fin arms' refusals (A2b-2b, J7.md concern 4): how much of fin16's J7 loss do its refused plays explain?

    python -I attrib.py ablate --plans DIR --fin RUNDIR --out DIR [--only place|ability]   # plans minus the cmds fin refused
    python -I attrib.py census --plans DIR --fin RUNDIR --truth truth.jsonl --per-match per_match.json --arm fin16_force
Ablation: crforge (force, lo) re-run on the plans with exactly the commands fin refused removed. If those refusals were
the cause of fin's loss, crforge loses the same ground on them; what crforge keeps is engine difference, not input loss.
Census: each refusal against fin's own first tower divergence (before = a possible cause, after = possibly a consequence),
and each placement refusal in enemy ground against the live / fin state of the princess tower whose fall opens it.
"""
import argparse, json
from collections import Counter
from pathlib import Path

PLACE = {'OUT_OF_TERRITORY', 'NO_DEPLOY', 'WATER'}
ABIL = {'NO_HERO', 'ABILITY_SPENT'}
IDS = ('T0L', 'T0R', 'T0K', 'T1L', 'T1R', 'T1K')


def kind(why):
    return 'place' if why in PLACE else 'ability' if why in ABIL else 'other'


def ablate(plans, fin, out, only):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    names = [n.strip() for n in open(Path(plans) / 'index.txt') if n.strip()]
    dropped = Counter()
    for n in names:
        plan = json.loads((Path(plans) / (n + '.json')).read_text())
        run = json.loads((Path(fin) / (n + '.json')).read_text())
        drop = {k for k, _, why, _ in run.get('refused_cmds', []) if only is None or kind(why) == only}
        dropped[len(drop) > 0] += 1
        keep = [c for k, c in enumerate(plan['cmds']) if k not in drop]
        # ability unit_cmd indices are not used by J7Run (it resolves the unit at the giving tick), so no renumbering
        plan['cmds'] = keep; plan['ablated'] = sorted(drop)
        (out / (n + '.json')).write_text(json.dumps(plan))
    (out / 'index.txt').write_text('\n'.join(names) + '\n')
    print(len(names), 'plans; matches with a dropped command', dropped[True])


def at(rows, t):
    best = rows[0]
    for r in rows:
        if r[0] > t:
            break
        best = r
    return best


def census(plans, fin, truth, per_match, arm, only=None):
    tr = {d['match']: d for d in map(json.loads, open(truth))}
    pm = json.loads(Path(per_match).read_text())
    fa, cf = pm[arm], pm['crforge_force']
    c = Counter(); seq = Counter()
    for p in sorted(Path(fin).glob('*.json')):
        m = p.stem
        if m not in fa or m not in tr or (only is not None and m not in only):
            continue
        run = json.loads(p.read_text()); plan = json.loads((Path(plans) / p.name).read_text())
        fd = (fa[m].get('first_div') or {}).get('tick')
        real = [x for x in run.get('refused_cmds', []) if kind(x[2]) != 'other']
        early = [x for x in real if fd is None or x[1] <= fd]
        seq['matches'] += 1
        seq[f"refusal_before_fin_div={'yes' if early else 'no'}"] += 1
        seq[f"refusal_before_fin_div={'yes' if early else 'no'}, fin_seq={fa[m]['seq_same']}, cf_seq={cf[m]['seq_same']}"] += 1
        for k, t, why, card in real:
            c[why, 'before_div' if fd is None or t <= fd else 'after_div'] += 1
            if why == 'OUT_OF_TERRITORY':
                cmd = plan['cmds'][k]; s = cmd['side']
                enemy = (s == 0 and cmd['y'] > 16000) or (s == 1 and cmd['y'] < 16000)
                if not enemy:
                    c['OOT own half'] += 1; continue
                lane = ('T1' if s == 0 else 'T0') + ('L' if cmd['x'] < 9000 else 'R')
                j = IDS.index(lane) + 1
                lv = at(tr[m]['rows'], t)[j]; fv = at(run['rows'], t)[j]
                c[f"OOT enemy half: live {lane[2]}-princess {'down' if not lv else 'up'}, fin {'down' if not fv else 'up'}"] += 1
            if why in ABIL:
                c['ability card ' + card + ' ' + why] += 1
    for k, v in sorted(seq.items()):
        print('seq', k, v)
    for k, v in sorted(c.items(), key=lambda kv: str(kv[0])):
        print(k, v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['ablate', 'census'])
    ap.add_argument('--plans', required=True); ap.add_argument('--fin', required=True)
    ap.add_argument('--out'); ap.add_argument('--only', choices=['place', 'ability'])
    ap.add_argument('--truth'); ap.add_argument('--per-match'); ap.add_argument('--arm', default='fin16_force')
    ap.add_argument('--matches', help='census: a file of match stems to restrict to')
    a = ap.parse_args()
    if a.mode == 'ablate':
        ablate(a.plans, a.fin, a.out, a.only)
    else:
        census(a.plans, a.fin, a.truth, a.per_match, a.arm, {l.strip() for l in open(a.matches)} if a.matches else None)


if __name__ == '__main__':
    main()
