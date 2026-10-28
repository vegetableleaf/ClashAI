"""rowcensus9.py TRACEDIR OUT.log -- A2c-9R: is the reader's row order the game's entity order (= crforge's holder order apart from
same-tick creations)? For every recorded frame with an AimRun trace line: recorded character rows matched to exactly one sim
character (same side, x, y); for each pair of matched rows, whether the reader order agrees with crforge's holder order. Disagreeing
pairs are split by whether the two sim characters were born on the same tick (from plays of the two sides, or otherwise)."""
import collections, glob, json, os, sys
from concurrent.futures import ProcessPoolExecutor
td, outp = sys.argv[1], sys.argv[2]


def one(f):
    m = os.path.basename(f).replace('.o.jsonl', '')
    sim, born = {}, {}
    for l in open(f):
        o = json.loads(l)
        sim[o['t']] = o['C']
        for c in o['C']: born.setdefault(c[0], (o['t'], c[2]))
    c = collections.Counter(); ex = []
    for l in open('/workspace/pilot/sme_live/frames2/' + m + '.jsonl'):
        fr = json.loads(l)
        C = sim.get(fr['t'])
        if not C: continue
        pos = collections.defaultdict(list)
        for k, x in enumerate(C): pos[(x[2], x[3], x[4])].append((k, x[0]))
        seq = []
        for e in fr['E']:
            h = pos.get((e[0], e[1], e[2]))
            if h and len(h) == 1: seq.append(h[0])
        for i in range(len(seq)):
            for j in range(i + 1, len(seq)):
                (ka, ia), (kb, ib) = seq[i], seq[j]
                if ka < kb: c['agree'] += 1; continue
                ba, bb = born[ia], born[ib]
                kind = 'same_tick_cross_side' if ba[0] == bb[0] and ba[1] != bb[1] else 'same_tick_same_side' if ba[0] == bb[0] else 'other'
                c[kind] += 1
                if kind == 'other' and len(ex) < 5: ex.append((m[10:], fr['t'], ia, ib, ba, bb))
    return c, ex


tot = collections.Counter(); exs = []
with ProcessPoolExecutor(32) as pool:
    for c, ex in pool.map(one, sorted(glob.glob(td + '/live_play_*.o.jsonl'))):
        tot += c; exs += ex
with open(outp, 'w') as w:
    w.write('row pairs (reader order vs crforge holder order): %s\n' % dict(tot))
    for e in exs[:40]: w.write('other %s\n' % (e,))
print(open(outp).read()[:3000])
