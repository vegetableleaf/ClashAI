import json, glob, sys
from statistics import mean
for d in sys.argv[1:]:
    el = [json.load(open(f)) for f in glob.glob(d + '/elixir/*.json')]
    el = [e for e in el if 'per_phase' in e]
    def agree(e, ph=None):
        pp = e['per_phase'] if ph is None else {ph: e['per_phase'][ph]} if ph in e['per_phase'] else {}
        n = sum(v['n'] for v in pp.values())
        return sum(v['ok'] for v in pp.values()) / n if n else None
    clean = [e for e in el if e['unmatched_drops'] == 0]
    dirty = [e for e in el if e['unmatched_drops'] > 0]
    print(d, 'all', round(mean(agree(e) for e in el), 3), len(el), '| no unmatched drop', round(mean(agree(e) for e in clean), 3), len(clean),
          '| with', round(mean(agree(e) for e in dirty), 3), len(dirty))
    for ph in ('1x', '2x', 'ot2x', 'ot3x'):
        v = [agree(e, ph) for e in clean if agree(e, ph) is not None]
        print('   clean', ph, round(mean(v), 3), len(v), ' perfect matches', sum(x == 1 for x in v))
