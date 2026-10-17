import json, sys
R = json.load(open(sys.argv[1]))
print({k: R[k] for k in ('rc', 'ckpt', 'sha', 'cue_inputs', 'reader', 'cues_attached', 'feature_version')})
for L in R['logs']:
    rows = L['rows']
    n = len(rows)
    cue = [r['cue'] for r in rows if r.get('cue')]
    deg = sum(1 for c in cue if c.get('degraded'))
    known = [c['known'] for c in cue if not c.get('degraded')]
    nz = [0] * 22
    for c in cue:
        for i, v in enumerate(c.get('nz') or []):
            nz[i] += v
    tw = [r for r in rows if 'twin' in r]
    dplay = sum(r['play'] != r['twin']['play'] for r in tw)
    dsame = [r for r in tw if r['play'] and r['twin']['play']]
    dcard = sum(r['name'] != r['twin']['name'] for r in dsame)
    dcell = sum(r['name'] == r['twin']['name'] and r['xy'] != r['twin']['xy'] for r in dsame)
    dp = sorted(abs(r['p'] - r['twin']['p']) for r in tw)
    print(L['log'], 'frames', L['frames'], 'decisions', n, 'plays', sum(r['play'] for r in rows), 'twin plays', sum(r['twin']['play'] for r in tw),
          'ms/dec', L['ms_per_decision'], 'twin ms', L['ms_per_twin'])
    print('  cue logs', len(cue), 'degraded', deg, 'mean known tokens', round(sum(known) / max(1, len(known)), 2),
          'decisions with >=1 cue row', sum(k > 0 for k in known))
    print('  nonzero counts per float (summed over decisions):', nz)
    print('  vs cue-blind twin: gate decision differs', dplay, '/', len(tw), '; both play: card differs', dcard, 'cell differs', dcell, 'of', len(dsame),
          '; |dp_play| median %.4f p90 %.4f max %.4f' % (dp[len(dp) // 2], dp[int(len(dp) * .9)], dp[-1]) if dp else '')
