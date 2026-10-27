"""Extra per-run numbers for SME.md: exact-share quantiles, persistent vs healed, torn per match, first-div tick spread.
    python3 stats_live.py RUNDIR"""
import json, os, statistics, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agg_live import mech  # noqa: E402

rs = [json.loads(l) for l in open(os.path.join(sys.argv[1], 'results.jsonl'))]
ok = [r for r in rs if 'error' not in r]
sh = sorted(r['exact_share'] for r in ok)
q = lambda p: sh[min(len(sh) - 1, int(p * len(sh)))]  # noqa: E731
print('matches scored', len(ok), 'errors', len(rs) - len(ok))
print('exact share: min %.3f p25 %.3f median %.3f p75 %.3f max %.3f' % (sh[0], q(.25), statistics.median(sh), q(.75), sh[-1]))
persist = [r for r in ok if r['episodes'] and not r['episodes'][-1]['healed']]
print('matches ending in a divergence that never heals:', len(persist))
only_healed = [r for r in ok if r['episodes'] and r['episodes'][-1]['healed']]
print('matches whose every divergence heals:', len(only_healed), '; of them all-1-frame:',
      sum(all(e['frames'] == 1 for e in r['episodes']) for r in only_healed))
print('episodes per failing match: median', statistics.median(len(r['episodes']) for r in ok if r['episodes']))
fd = sorted(r['first_div'] for r in ok if r['first_div'] is not None)
print('first true divergence tick: median', statistics.median(fd), 'p25', fd[len(fd) // 4], 'p75', fd[3 * len(fd) // 4])
torn = [len(r['torn_ticks']) for r in ok]
print('torn frames per match: total', sum(torn), 'matches with any', sum(1 for t in torn if t),
      'torn_t1 total', sum(len(r.get('torn_t1_ticks', [])) for r in ok))
pm = {}
for r in persist:
    e = next(e for e in r['episodes'] if not e['healed'])
    k = mech(e['detail'], any(e['start'] - 30 <= p[1] <= e['start'] for p in r['refused_plays'])) if e['detail'] else 'beyond 12 described'
    pm[k] = pm.get(k, 0) + 1
print('the never-healing episode, by mechanism:', sorted(pm.items(), key=lambda kv: -kv[1]))
offs = sum(len(r['nonzero_offset']) for r in ok)
cmds = sum(r['commands'] for r in ok)
print('commands', cmds, 'kept at a run tick other than the extractor tick', offs)
