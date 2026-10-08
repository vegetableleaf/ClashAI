"""Owner's live test 2026-10-08: default input vs --fast-input vs --fast-input --tap-gap-ms 0 (groups from the start event)."""
import glob, json, sys
import numpy as np

groups = {}
for f in sorted(glob.glob(sys.argv[1] if len(sys.argv) > 1 else
                          'scratchpad/gauntlet/L68/live_reader/live_play_20261008_1[6-8]*.jsonl')):
    key, plays, rows = None, [], dict(lock=[], tap=[], decide=[], err=[], unconf=0, played=0, confirmed=0, tap_end=[])
    for line in open(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        e = d.get('event')
        if e == 'start':
            key = ('fast' if d.get('fast_input') else 'default') + '/gap%s' % d.get('tap_gap_ms', 50)
        elif e == 'play':
            plays.append(int(d['tick'])); rows['played'] += 1
        elif e == 'tap_timing':
            rows['tap'].append(d['tap_ms']); rows['decide'].append(d['decide_ms'])
            if d.get('tap_end_ms') is not None:
                rows['tap_end'].append(d['tap_end_ms'])
        elif e == 'confirmed' and plays:
            rows['lock'].append(int(d['tick']) - plays[-1]); rows['confirmed'] += 1
            if d.get('err_tiles') is not None:
                rows['err'].append(d['err_tiles'])
        elif e == 'unconfirmed':
            rows['unconf'] += 1
    if key is None:
        continue
    g = groups.setdefault(key, dict(lock=[], tap=[], decide=[], err=[], unconf=0, played=0, confirmed=0, tap_end=[], n=0))
    g['n'] += 1
    for k in ('lock', 'tap', 'decide', 'err', 'tap_end'):
        g[k] += rows[k]
    for k in ('unconf', 'played', 'confirmed'):
        g[k] += rows[k]
for k, g in groups.items():
    med = lambda v: round(float(np.median(v)), 2) if v else None
    print(k, 'matches', g['n'], 'plays', g['played'], 'confirmed', g['confirmed'], 'unconfirmed', g['unconf'],
          '| decision->confirm ticks median', med(g['lock']), 'mean', round(float(np.mean(g['lock'])), 2) if g['lock'] else None,
          '| tap_ms median', med(g['tap']), '| decide_ms median', med(g['decide']), '| err_tiles median', med(g['err']),
          'p90', round(float(np.percentile(g['err'], 90)), 2) if g['err'] else None)
