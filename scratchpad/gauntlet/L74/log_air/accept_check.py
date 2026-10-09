"""Are the re-aimed Logs accepted by the SIM?  plays_attempted - plays_accepted per candidate game, base vs arm."""
import glob, json, os, sys
D = sys.argv[1]


def rows(p):
    out = {}
    for f in glob.glob(p):
        for l in open(f):
            r = json.loads(l)
            out[(r['tag'], os.path.basename(os.path.dirname(f)).split('_')[1])] = r
    return out


base = rows(f'{D}/base_*/matches.jsonl')
for arm in ('retarget', 'block'):
    res = rows(f'{D}/{arm}_*/matches.jsonl')
    ks = [k for k in res if k in base]
    rej = lambda r: r['plays_attempted'] - r['plays_accepted']
    print(arm, len(ks), 'rejected plays per game: base %.2f, arm %.2f; accepted plays base %.1f arm %.1f; end_tick base %.0f arm %.0f' % (
        sum(rej(base[k]) for k in ks) / len(ks), sum(rej(res[k]) for k in ks) / len(ks),
        sum(base[k]['plays_accepted'] for k in ks) / len(ks), sum(res[k]['plays_accepted'] for k in ks) / len(ks),
        sum(base[k]['end_tick'] for k in ks) / len(ks), sum(res[k]['end_tick'] for k in ks) / len(ks)))
allbase = [r for k, r in base.items()]
print('all base games: rejected per game %.2f' % (sum(r['plays_attempted'] - r['plays_accepted'] for r in allbase) / len(allbase)))
