"""HYPOTHESIS LEDGER pass: assign every failing J1 fight (stamped, strict, live vs sim[0]) to the FIRST mechanism whose
measured signature it carries, in a fixed order, and report what stays unexplained after each pass.
  python explain.py BASE_DIR CLS_JSONL [--k8 BASE8_DIR] [--arm NAME:ARM_DIR ...]
Signatures (all from existing outputs):
  noise        some perturbed SIM agrees with live (K=8 run; the modelled hidden-state noise)
  arm:NAME     the law's arm run makes the fight pass (a measured counterfactual)
  formation    the anchor is an own Skeletons play whose members stand > 30 mt off live on the first paired frame (the
               fork's 3-member ring vs live; probe + census)
  spell        >= 2 anchor bodies die on one live tick that the SIM does not match (an unseen / late splash or spell)
  spawn        the first divergence is a spawned body appearing early / late / on one side only (births census family)
  startstate   the first divergence (whole fight) is on a SET-UP body within 10 ticks of the start
  early        the first divergence near the anchor is within 40 ticks (set-up or new body): target / position / hp
  nearmiss     every mismatched death is within 15 ticks and the fates agree (tolerance edge; characterised, not a cause)
  rest         unexplained"""
import glob, json, os, sys
from collections import Counter
sys.path.insert(0, r'C:\Users\benpe\ClashBot')
os.environ.pop('PARITY_ATTACKS', None)
from scratchpad.gauntlet.L74.parity import fights as F  # noqa: E402
FORM = ('', ' evo', ' hero')


def load(d):
    out = {}
    for p in sorted(glob.glob(d + '/matches/*.json')):
        m = json.load(open(p, encoding='utf-8'))
        s = m['summary']
        if s.get('skipped') or not s.get('phase3b_births'):
            continue
        for r in m['fights']:
            c = r.get('card')
            if 'error' in r or not c or c['sim'][0] is None or not F.is_clean(r, 'strict'):
                continue
            out[(s['match'], r['t0'], r['anchor']['tick'], r['anchor']['name'])] = r
    return out


base = load(sys.argv[1])
cls = {}
for line in open(sys.argv[2]):
    x = json.loads(line)
    for f in x['fights']:
        if 'error' not in f:
            cls.setdefault((x['match'], f['t0'], f['lab']), []).append(f)
k8 = load(sys.argv[sys.argv.index('--k8') + 1]) if '--k8' in sys.argv else {}
arms = [a.split(':', 1) for a in sys.argv[sys.argv.index('--arm') + 1:]] if '--arm' in sys.argv else []
arms = [(n, load(d)) for n, d in arms]
fails = {k: r for k, r in base.items() if not F.card_agree(r['card']['live'], r['card']['sim'][0])[0]}
print(f'strict fights {len(base)}, failing {len(fails)} ({len(fails)/len(base):.4f})')


def sig(k, r):
    L, S = r['card']['live'], r['card']['sim'][0]
    lab = ('own ' if r['own'] else 'opp ') + r['anchor']['name'] + FORM[r['anchor']['form']]
    out = []
    if k in k8 and any(F.card_agree(k8[k]['card']['live'], s)[0] for s in k8[k]['card']['sim'][1:] if s):
        out.append('noise')
    for n, a in arms:
        if k in a and F.card_agree(a[k]['card']['live'], a[k]['card']['sim'][0])[0]:
            out.append('arm:' + n)
    if lab == 'own Skeletons' and any(b['name'] == 'Skeletons' and not b['setup'] and b['side'] == r['obs'] and (b['pos_first'] or 0) > 30
                                      for b in r['bodies']):
        out.append('formation')
    if not L['spell']:
        dl = Counter(x for x in L['own'] if x is not None)
        grp = [t for t, n in dl.items() if n >= 2]
        if grp and sum(1 for y in S['own'] if y is not None and abs(y - min(grp)) <= F.DEATH_TOL) < dl[min(grp)]:
            out.append('spell')
    cf = cls.get((k[0], k[1], lab))
    c = cf[0] if cf else None
    if c and c['bad'] and c['bad'][0]['first']:
        f = c['bad'][0]['first']
        if f['kind'] in ('appear_sim_early', 'appear_sim_late', 'presence_live_only', 'presence_sim_only'):
            out.append('spawn')
        if f['dt'] <= 40:
            out.append('early')
    if c and c.get('first_global') and c['first_global'].get('setup') and c['first_global']['dt'] <= 10:
        out.append('startstate')
    if not L['spell'] and len(L['own']) == len(S['own']) and all(
            (x is None) == (y is None) and (x is None or abs(x - y) <= 15) for x, y in zip(L['own'], S['own'])):
        out.append('nearmiss')
    return out, lab


order = ['noise'] + ['arm:' + n for n, _ in arms] + ['formation', 'spell', 'spawn', 'startstate', 'early', 'nearmiss']
sigs = {k: sig(k, r) for k, r in fails.items()}
left = set(fails)
print('pass | mechanism | fights with the signature (any order) | newly explained | unexplained after the pass (share of failing)')
for i, mech in enumerate(order):
    has = {k for k, (s, _) in sigs.items() if mech in s}
    new = has & left
    left -= has
    print(f'{i+1} | {mech} | {len(has)} | {len(new)} | {len(left)} ({len(left)/len(fails):.3f})')
print('\nunexplained by anchor card:', Counter(sigs[k][1] for k in left).most_common(15))
print('formation signature by card:', Counter(sigs[k][1] for k, (s, _) in sigs.items() if 'formation' in s).most_common(3))
