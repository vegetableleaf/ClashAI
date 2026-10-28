"""firstdiv9.py TRACEDIR FROM_TICK M ... -- A2c-9R quick proxy (not the comparator): first recorded frame >= FROM_TICK where a sim
character (AimRun C rows: side, x, y) has no exact recorded body, and the count of frames with every character exact."""
import glob, json, sys
td, t0 = sys.argv[1], int(sys.argv[2])
for m in sys.argv[3:]:
    sim = {}
    for l in open(glob.glob(td + '/live_play_' + m + '.o.jsonl')[0]):
        o = json.loads(l)
        sim[o['t']] = [(c[2], c[3], c[4], c[1]) for c in o['C']]
    first, ok, n = None, 0, 0
    for l in open('/workspace/pilot/sme_live/frames2/live_play_' + m + '.jsonl'):
        f = json.loads(l)
        if f['t'] not in sim: continue
        rs = {(e[0], e[1], e[2]) for e in f['E']}
        bad = [s for s in sim[f['t']] if s[:3] not in rs]
        n += 1
        if not bad: ok += 1
        elif first is None and f['t'] >= t0: first = (f['t'], bad[:3])
    print(m, 'frames', n, 'all-exact', ok, 'first>=%d' % t0, first)
