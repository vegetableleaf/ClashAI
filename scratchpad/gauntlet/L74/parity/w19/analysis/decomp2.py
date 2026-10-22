"""Per failing fight (live vs unperturbed SIM): how many of the K perturbed SIMs agree with live; body death dt; class.
  python decomp2.py RUN_DIR [--all-matches] [--mode strict]"""
import json, glob, os, sys, statistics
from collections import Counter, defaultdict
from pathlib import Path
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402

run = sys.argv[1]
stamped = '--all-matches' not in sys.argv
mode = sys.argv[sys.argv.index('--mode') + 1] if '--mode' in sys.argv else 'strict'
FORM = ('', ' evo', ' hero')
out = []
for f in sorted(glob.glob(run + '/matches/*.json')):
    d = json.load(open(f, encoding='utf-8'))
    s = d['summary']
    if s.get('skipped') or (stamped and not s.get('phase3b_births')):
        continue
    for r in d['fights']:
        if 'error' in r or not F.is_clean(r, mode):
            continue
        c = r.get('card')
        if not c or c['sim'][0] is None:
            continue
        L, S = c['live'], c['sim']
        ag = [F.card_agree(L, x) if x is not None else None for x in S]
        a = r['anchor']
        lab = ('own ' if r['own'] else 'opp ') + a['name'] + FORM[a['form']]
        pk = [x[0] for x in ag[1:] if x is not None]
        # sorted deaths for troop anchors
        dts = []
        if not L['spell'] and len(L['own']) == len(S[0]['own']):
            dts = [(x - y) if (x is not None and y is not None) else ('L' if x is None and y is not None else 'S' if y is None and x is not None else 0)
                   for x, y in zip(L['own'], S[0]['own'])]
        out.append(dict(match=s['match'], lab=lab, a0=ag[0][0], mis=ag[0][1], n=ag[0][2], tok=ag[0][3], kag=sum(pk), k=len(pk),
                        tl=L['tower'], ts=S[0]['tower'], dts=dts, nl=len(L.get('own', [])), ns=len(S[0].get('own', [])),
                        t0=r['t0'], spell=L['spell']))
fails = [x for x in out if not x['a0']]
print(run, 'fights', len(out), 'a0 agree', round(1 - len(fails)/len(out), 4))
print('failing fights by #perturbed agreeing (of K):', sorted(Counter(x['kag'] for x in fails).items()))
print('passing fights by #perturbed disagreeing:', sorted(Counter(x['k'] - x['kag'] for x in out if x['a0']).items()))
dd = [v for x in fails for v in x['dts'] if isinstance(v, int) and v != 0]
print('timing dts (live-sim) of failing troop fights: n', len(dd), 'abs quartiles', [sorted(map(abs, dd))[int(q*len(dd))] for q in (.25, .5, .75, .9)] if dd else None,
      'live later', sum(v > 0 for v in dd), 'sim later', sum(v < 0 for v in dd))
sv = Counter(v for x in fails for v in x['dts'] if isinstance(v, str))
print('survival mismatches: live alive/sim dead', sv['L'], ' live dead/sim alive', sv['S'])
print('count mismatches (live n != sim n):', sum(x['nl'] != x['ns'] for x in fails if not x['spell']),
      Counter((x['nl'] - x['ns']) for x in fails if not x['spell'] and x['nl'] != x['ns']).most_common(6))
by = defaultdict(list)
for x in out:
    by[x['lab']].append(x)
print('\nlabel | n | a0 | fails | fails w/ >=1 perturbed agreeing | timing dt med | surv L/S | count')
for lab, xs in sorted(by.items(), key=lambda kv: -sum(not x['a0'] for x in kv[1]))[:30]:
    fl = [x for x in xs if not x['a0']]
    d2 = [abs(v) for x in fl for v in x['dts'] if isinstance(v, int) and v != 0]
    sv = Counter(v for x in fl for v in x['dts'] if isinstance(v, str))
    print(f"{lab} | {len(xs)} | {1-len(fl)/len(xs):.3f} | {len(fl)} | {sum(x['kag']>0 for x in fl)} | "
          f"{statistics.median(d2) if d2 else '-'} | {sv['L']}/{sv['S']} | {sum(x['nl']!=x['ns'] for x in fl if not x['spell'])}")
json.dump(out, open(Path(__file__).parent / (Path(run).name + '_d2.json'), 'w'))
