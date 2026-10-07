"""Print the report tables from live_results.json / native_results.json / cf_fv4.json / cf_fv5.json -> tables.txt."""
import json, os, statistics
from collections import Counter, defaultdict
H = os.path.dirname(os.path.abspath(__file__))
out = []
P = out.append


def outc(l):
    o = l.get('skel_outcomes')
    if o is None:
        return 'no_roll_data'
    if not o:
        return 'no_skel_tracked'
    return 'killed>=1' if o.get('killed_at_crossing') else 'passed_before_spawn' if o.get('band_passed_before_spawn') else 'no_kill_other'


def q(xs):
    xs = sorted(xs)
    return f"n={len(xs)} median={statistics.median(xs):.0f} p10={xs[len(xs)//10]:.0f} p90={xs[9*len(xs)//10]:.0f}" if xs else 'n=0'


cols = ['killed>=1', 'passed_before_spawn', 'no_kill_other', 'no_skel_tracked', 'no_roll_data']
for label, path, sel in (('LIVE R1e (rseries_r1e31_u0155)', 'live_results.json', lambda l: 'r1e31' in l['ckpt']),
                         ('LIVE all models', 'live_results.json', lambda l: True),
                         ('NATIVE pros (re-drive)', 'native_results.json', lambda l: True)):
    d = json.load(open(os.path.join(H, path)))
    logs = [l for l in d['logs'] if sel(l)]
    P(f'\n## {label}: aimed Logs n={len(logs)}')
    for key in ('phase', 'phase_at_rs'):
        P(f'by {key} (rows) x outcome (cols {cols})')
        t = defaultdict(Counter)
        for l in logs:
            if key in l:
                t[l[key]][outc(l)] += 1
        for ph in ('balloon_alive', 'drop_pending', 'skeletons_on_ground'):
            P(f'  {ph:20s} ' + '  '.join(f'{t[ph][c]:4d}' for c in cols) + f'   total {sum(t[ph].values())}')
    cs = [l['cross_minus_spawn_hi'] for l in logs if l.get('cross_minus_spawn_hi') is not None]
    P(f'roll band crosses the drop point BEFORE first skeleton sighting: {sum(c < 0 for c in cs)}/{len(cs)}')
    hv = Counter((l['cross_minus_spawn_hi'] >= 0, outc(l)) for l in logs if l.get('cross_minus_spawn_hi') is not None and l.get('skel_outcomes'))
    P(f'  outcome | crossed after spawn: {dict((k[1], v) for k, v in hv.items() if k[0])};  before: {dict((k[1], v) for k, v in hv.items() if not k[0])}')
    for k in ('tp_minus_balloon_last', 'rs_minus_balloon_last', 'rs_minus_spawn_hi', 'cross_minus_spawn_hi'):
        P(f'  {k:24s} ' + q([l[k] for l in logs if l.get(k) is not None and l.get('spawn_hi') is not None]))
    early = [l for l in logs if l.get('cross_minus_balloon_last') is not None and l.get('skel_outcomes')]
    for lo, hi in ((-999, 0), (0, 12), (12, 999)):
        g = [l for l in early if lo <= l['cross_minus_balloon_last'] < hi]
        P(f'  band crosses drop point at death{lo:+d}..{hi:+d} ticks: n={len(g)} ' + str(dict(Counter(outc(l) for l in g))))
    if 'native' not in path:
        full = [l for l in logs if l['phase'] == 'balloon_alive' and l.get('model_sb_tokens')]
        P('  balloon-alive R1e decisions, model view of the balloon token (cls, x, y, hp_frac): ' +
          '; '.join(f"{l['file'][10:25]}@{l['tick']} {[t for t in l['model_sb_tokens'] if t[0] == 111]} other_in_corridor={l['other_enemy_in_corridor']} -> {outc(l)}" for l in full))
d = json.load(open(os.path.join(H, 'live_results.json')))['summary']
P('\n## drop timing (live, 2-tick frame logs): first frame without the balloon -> first skeleton frame (ticks): ' +
  str(d['balloon_gone_to_skeletons_seen_ticks_2tick_frames']))
P('decision -> Log roll start (ticks, audited): ' + str(d['decision_to_roll_start_ticks']))
for f in ('cf_fv4.json', 'cf_fv5.json'):
    p = os.path.join(H, f)
    if not os.path.exists(p):
        continue
    c = json.load(open(p))
    P(f"\n## counterfactual {f}: rows={c['rows']} eligible balloon rows={c['eligible_balloon_rows']}")
    P('bin d=tick-spawn | n | phases | pro P(Log now) | ' + ' | '.join(f'{m} P(Log now)' for m in c['models']))
    for b, v in c['bins'].items():
        P(f"  {b:10s} {v['n']:5d} {v['phases']} pro={v['pro_log_rate']} " +
          ' '.join(f"{m}={r['bins'].get(b, {}).get('p_log_now')}" for m, r in c['models'].items()))
    for m, r in c['models'].items():
        P(f'  {m} interventions (eligible balloon rows): {r["interventions_on_eligible_balloon_rows"]}')
        P(f'  {m} by phase: {r.get("by_phase")}')
        for k, v in r.items():
            if k.startswith('balloon_rows_d'):
                P(f'  {m} {k}: {v}')
open(os.path.join(H, 'tables.txt'), 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
