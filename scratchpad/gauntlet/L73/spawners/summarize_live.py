"""Aggregate live_audit_raw.json -> live_summary.json (+ printed tables). Split by checkpoint feature version."""
import json, os, collections
HERE = os.path.dirname(os.path.abspath(__file__))
res = [r for r in json.load(open(os.path.join(HERE, 'live_audit_raw.json'))) if 'error' not in r]
out = {'logs_with_frames': len(res), 'by_ckpt': dict(collections.Counter(f"{r['ckpt']}|fv{r['fv']}" for r in res))}
# A: model batch (decisions with public audit)
model = collections.defaultdict(collections.Counter)
for r in res:
    grp = 'fv4_legacy' if r['fv'] == 4 else ('fv5plus_corrected' if (r['fv'] or 0) >= 5 else 'no_audit')
    for k, v in r['model'].items():
        model[grp][k] += v
out['model_batch'] = {g: dict(sorted(c.items())) for g, c in model.items()}
# B: observer replica plays
plays = collections.Counter(); el = collections.defaultdict(list); hp0 = collections.Counter(); logs_with = collections.Counter()
for r in res:
    fams = set()
    for p in r['plays']:
        if p['cls'] != 'nonfamily':
            plays[(p['card'], p['cls'])] += 1; fams.add(p['card'])
    for f in fams:
        logs_with[f] += 1
        el[f].append(r['elixir'])
    if not fams:
        el['NO_FAMILY'].append(r['elixir'])
    for k, v in r['hp_le0_body_frames'].items():
        hp0[k] += v
out['observer_plays'] = {f'{k}|{c}': v for (k, c), v in sorted(plays.items())}
out['hp_le0_body_frames'] = dict(hp0)
agg = {}
for f, xs in sorted(el.items()):
    n = sum(x['n'] for x in xs)
    w = lambda key: sum(x[key] * x['n'] for x in xs) / max(1, n)
    agg[f] = dict(logs=len(xs), frames=n, phantom_plays=sum(x['phantom_plays'] for x in xs),
                  phantom_elixir=sum(x['phantom_elixir'] for x in xs), mean_estimate_shift_from_phantoms=w('replica_minus_cf_mean'),
                  worst_shift=min(x['replica_minus_cf_max'] for x in xs), logged_bias=w('logged_bias'), logged_mae=w('logged_mae'))
out['elixir'] = agg
json.dump(out, open(os.path.join(HERE, 'live_summary.json'), 'w'), indent=1)
print(out['by_ckpt'])
for g, c in out['model_batch'].items():
    print('\nMODEL BATCH', g)
    fams = sorted({k.split('|')[0] for k in c})
    for f in fams:
        print(f'  {f:16s}', {k.split('|')[1]: v for k, v in c.items() if k.split('|')[0] == f})
print('\nOBSERVER PLAYS (replica of live PublicObserver):')
for k, v in out['observer_plays'].items(): print(' ', k, v)
print('\nHP<=0 opponent family body-frames live:', out['hp_le0_body_frames'])
print('\nELIXIR')
for f, v in agg.items(): print(f'  {f:16s}', {k: (round(x, 3) if isinstance(x, float) else x) for k, x in v.items()})
