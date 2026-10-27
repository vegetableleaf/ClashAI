"""Mechanism class of every divergence onset of a run (ticket A2c round 6.0), from diag6.py + sweep6.py output.
    python3 cls6.py RUNDIR DIAG.jsonl SWEEP.jsonl RESULTS_FLAGS_INPUTS OUT.tsv
Rules, first match wins (each one a measured pattern, SME.md round 6.0):
  cmp:torn_cmd_3x     only our elixir differs, by whole elixir, and sim t+1 is reached by one 3x regen (536-538):
                      the round-2.1 command-pass read at triple elixir, which cmd_pass_read's 178/357 test misses
  cmp:step_clock      step_read passes once our elixir (sim t+1's, not sim t's) stands in for the two-mover count
  cmp:tower_label     a recorded card -1 body (read as a tower) at the same (side, x, y, hp) as a sim unit
  ext:own_press       moving one of our ability casts earlier makes the onset go away (sweep, first None)
  ext:own_play        moving one of our card plays makes it go away
  ext:valk_charge     moving a hero Valkyrie cast >= 2 ticks earlier makes it go away
  ext:gk_dash         moving a Golden Knight dash cast makes it go away
  crf:rage_chain      moving Rage 1 tick earlier makes it go away (crforge makes RageDamage 1 tick after the area)
  ext:hero_cast       moving another hero's ability cast makes it go away
  ext:play_dating     moving another play makes it go away
  partial:<kind>      a single-command move delays the onset but does not remove it
  open:<mech>         nothing above; mech() of the onset detail"""
import json, os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

run, diagp, sweepp, inputs, outp = sys.argv[1:6]
flags = {json.loads(l)['match']: json.loads(l)['flags'] for l in open(inputs)}
res = {json.loads(l)['match']: json.loads(l) for l in open(os.path.join(run, 'results.jsonl'))}
sw = collections.defaultdict(list)
for l in open(sweepp):
    r = json.loads(l)
    sw[(r['match'], r['t0'])].append(r)
plans = {}


def card(m, k):
    if m not in plans:
        plans[m] = json.load(open(os.path.join(run, m, 'plan.json')))
    c = plans[m]['cmds'][k]
    if c.get('card'):
        return c['card'], 'play'
    return plans[m]['cmds'][int(c['unit'][3:].split('_')[0])]['card'], 'ability'


def detail_of(m, t0):
    return next((e['detail'] for e in res[m]['episodes'] if e['start'] == t0), None)


def classify(r):
    m, t0, me, d0 = r['match'], r['t0'], r['me'], r['d0'] or []
    nxt = dict((t, v) for t, v in r['sim_el']).get(t0 + 1)
    if d0 and all(x[0] == 'S%d_elixir' % me for x in d0):
        rr, ss = d0[0][1], d0[0][2]
        if (ss - rr) % 10000 == 0 and ss > rr and nxt is not None and 536 <= nxt - rr <= 538:
            return 'cmp:torn_cmd_3x'
    if r.get('step_read_clock') is True:
        return 'cmp:step_clock'
    sim_u = {tuple(x[1]) for x in d0 if x[0] == 'U_sim_only'}
    if any(x[0] == 'T_rec_only' and tuple(x[1]) in sim_u for x in d0):
        return 'cmp:tower_label'
    hits = sw.get((m, t0), [])
    full = [h for h in hits if h['first'] is None]
    for h in (full or hits):
        h['c'], h['k'] = card(m, h['cmd'])
    pre = '' if full else 'partial:'
    for h in sorted(full or hits, key=lambda h: (h['first'] is not None, -(h['first'] or 0))):
        own = h['side'] == me
        if h['k'] == 'ability' and own:
            return pre + 'ext:own_press'
        if h['k'] == 'play' and own:
            return pre + 'ext:own_play'
        if h['c'] == 'Valkyrie' and h['k'] == 'ability' and h['dR'] <= -2:
            return pre + 'ext:valk_charge'
        if h['c'] == 'GoldenKnight':
            return pre + 'ext:gk_dash'
        if h['c'] == 'Rage' and h['dR'] == -1:
            return pre + 'crf:rage_chain'
        if h['k'] == 'ability':
            return pre + 'ext:hero_cast:' + h['c']
        return pre + 'ext:play_dating:' + h['c']
    det = detail_of(m, t0)
    return 'open:' + mech(det, False)


rows = []
for l in open(diagp):
    r = json.loads(l)
    rows.append((r['match'], r['t0'], classify(r)))
with open(outp, 'w') as w:
    for m, t0, c in rows:
        w.write('%s\t%d\t%s\n' % (m, t0, c))
first = {}
for m, t0, c in rows:
    if m not in first or t0 < first[m][0]:
        first[m] = (t0, c)
cf = collections.Counter(c for _, c in first.values())
ca = collections.Counter(c for _, _, c in rows)
print('first onsets (%d matches):' % len(first))
for k, v in cf.most_common():
    print('%4d  %s' % (v, k))
print('all onsets (%d):' % len(rows))
for k, v in ca.most_common():
    print('%4d  %s' % (v, k))
