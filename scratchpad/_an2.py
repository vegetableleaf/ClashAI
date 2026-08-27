"""Analysis for the ceiling sweep. Paired against rs_base.json on the shared 300 seeds."""
import json, math, os, sys

def load(tag):
    d = json.load(open(f'rs_{tag}.json'))
    return d, {r['seed']: r for r in d['records']}

BD, BT = load('base')

def stats(tag):
    d, t = load(tag)
    seeds = sorted(set(BT) & set(t))
    out = {'d': d, 't': t, 'n': len(seeds)}
    for key in ('tower_delta', 'crown_delta'):
        diffs = [t[s][key] - BT[s][key] for s in seeds]
        m = sum(diffs) / len(diffs)
        var = sum((x - m) ** 2 for x in diffs) / (len(diffs) - 1)
        sem = math.sqrt(var / len(diffs))
        out[key] = (m, sem, m / sem if sem else float('nan'))
    wd = [(1.0 if t[s]['outcome'] == 'win' else 0.0) - (1.0 if BT[s]['outcome'] == 'win' else 0.0)
          for s in seeds]
    m = sum(wd) / len(wd)
    var = sum((x - m) ** 2 for x in wd) / (len(wd) - 1)
    sem = math.sqrt(var / len(wd))
    out['win'] = (100 * m, 100 * sem, m / sem if sem else float('nan'))
    out['wr'] = 100 * sum(1 for s in t.values() if s['outcome'] == 'win') / len(t)
    out['tower'] = sum(r['tower_delta'] for r in t.values()) / len(t)
    out['spm'] = sum(r['wall_s'] for r in t.values()) / len(t)
    out['len'] = sum(r['t_end'] for r in t.values()) / len(t)
    out['plays'] = sum(r['plays'] for r in t.values()) / len(t)
    return out


def row(label, tag):
    try:
        s = stats(tag)
    except FileNotFoundError:
        print(f'{label:12s}  -- not finished --')
        return None
    d = s['d']
    mt, st, zt = s['tower_delta']
    mc, _, zc = s['crown_delta']
    mw, sw, zw = s['win']
    nc = d['candidates'] / max(1, d['searched'])
    clamp = ''
    if d.get('roll_total'):
        clamp = f"{100*d['roll_clamped']/d['roll_total']:5.1f}%"
    print(f"{label:12s} {s['wr']:5.1f} {s['tower']:7.3f} | {mt:+6.3f} {st:5.3f} {zt:+6.2f} "
          f"| {mc:+6.3f} {zc:+6.2f} | {mw:+5.1f} {zw:+5.2f} | {d['searched']:6d} "
          f"{100*d['disagree']/max(1,d['searched']):5.1f}% {nc:4.2f} {s['spm']:5.2f} {clamp:>6s}")
    return s


HDR = (f"{'arm':12s} {'win%':>5} {'tower':>7} | {'dTOW':>6} {'sem':>5} {'sig':>6} "
       f"| {'dCRW':>6} {'sig':>6} | {'dWIN':>5} {'sig':>5} | {'srch':>6} {'dis%':>6} {'cand':>4} {'s/m':>5} {'clamp':>6}")

if __name__ == '__main__':
    groups = {
        'HORIZON (N=5, K=4)': [('base', None), ('H=0.6', 'h06'), ('H=3', 'h3'), ('H=5', 'h5'),
                               ('H=8', 'h8'), ('H=12', 'h12'), ('H=16', 'h16'), ('H=20', 'h20'),
                               ('H=30', 'h30'), ('H=FULL', 'hfull')],
        'CANDIDATES K (H=12, N=5)': [('K=2', 'k2'), ('K=4', 'h12'), ('K=8', 'k8')],
        'INTERVAL N (H=12, K=4)': [('N=1', 'n1'), ('N=3', 'n3'), ('N=5', 'h12'), ('N=10', 'n10')],
        'MATCH POSITION (H=12,N=5)': [('early <60s', 'phE'), ('mid 60-120', 'phM'),
                                      ('late >=120', 'phL'), ('all', 'h12')],
        'CONTROLS': [('opp-reseed', 'h12ro'), ('cells=3', 'h12c3'), ('crown=0', 'h12cr0'),
                     ('crown=3', 'h12cr3'), ('force-play', 'fplay'), ('jitter', 'jit')],
    }
    for g, items in groups.items():
        print(f'\n=== {g} ===')
        print(HDR)
        for label, tag in items:
            if tag is None:
                bwr = 100 * sum(1 for r in BT.values() if r['outcome'] == 'win') / len(BT)
                bt = sum(r['tower_delta'] for r in BT.values()) / len(BT)
                print(f"{'base':12s} {bwr:5.1f} {bt:7.3f} |      --")
                continue
            row(label, tag)
