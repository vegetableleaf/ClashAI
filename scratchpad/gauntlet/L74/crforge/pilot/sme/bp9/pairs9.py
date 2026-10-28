"""pairs9.py RUNDIR M:RUN:WINNER ... -- A2c-9R: details of decisive same-run cross-side play pairs (WINNER = the side the game
created first, from the comparator run): card, x, y, given, run window, source, tap tick, deck index, own."""
import json, sys
rd = sys.argv[1]
for a in sys.argv[2:]:
    m, run, win = a.split(':'); run = int(run)
    cmds = json.load(open('%s/live_play_%s/plan.json' % (rd, m)))['cmds']
    print('==', m, run, 'game first: side', win)
    for i, c in enumerate(cmds):
        if c.get('kind') == 'play' and c['run'] == run:
            s = c.get('_src') or {}
            print('   cmd', i, 'side', c['side'], c['card'], 'xy', c['x'], c['y'], 'given', c['given'], 'win', [s.get('lo'), s.get('hi')],
                  s.get('source'), 'own', s.get('own'), {k: v for k, v in s.items() if k not in ('lo', 'hi', 'source', 'own', 'tick')})
