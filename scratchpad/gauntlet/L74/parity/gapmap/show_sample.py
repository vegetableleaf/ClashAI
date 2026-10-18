"""Compact first-divergence view of the sample fights (sample.txt) from the dossiers (divS/*.json, r7d div.py output):
events, card views, the first N non-benign divergences (firstdiv.py's filter) and the anchor bodies' hp timelines' ends.
usage: python show_sample.py sample.txt divS [N] > SAMPLE_VIEW.txt"""
import json, sys
from pathlib import Path
TOW = {'T0K', 'T0L', 'T0R', 'T1K', 'T1L', 'T1R'}
N = int(sys.argv[3]) if len(sys.argv) > 3 else 7
dos = {}
for p in Path(sys.argv[2]).glob('*.json'):
    dos.update(json.load(open(p)))
for ln in open(sys.argv[1]):
    k, card, aK, ceil = ln.rstrip('\n').split('\t')
    name = card.split()[1]
    x = next((v for kk, v in dos.items() if kk.split(':')[0] == k and v['anchor']['name'] == name), None)
    if x is None:
        print(f"## {k} {card} aK={aK} ceil={ceil} -- no dossier"); continue
    t0 = int(k.split('@')[1])
    ev = ' '.join(f"{e[0]-t0}:{e[1][0]}{e[2]}{'+'*(e[3] or 0)}" for e in x['events'])
    print(f"## {k} {card} aK={aK} ceil={ceil} | L {x['card']['live'].get('own')} S {x['card']['sim'].get('own')} "
          f"tw {x['card']['live']['tower']}/{x['card']['sim']['tower']} | flags {','.join(sorted(x.get('flags', {}))[:12]) if isinstance(x.get('flags'), dict) else ''}")
    print(f"   ev {ev}")
    n = 0
    for t, kind, nm, sd, bid, info, anc in x['div']:
        if kind == 'tgt' and (info[0] or '').split(':')[0] in TOW and info[1] is None:
            continue
        if kind == 'hp' and isinstance(info[0], (int, float)) and isinstance(info[1], (int, float)) and abs(info[0]-info[1]) <= 3:
            continue
        print(f"    {t-t0:+d} {kind} {nm}{'*' if anc else ''}/{sd} {str(info)[:90]}")
        n += 1
        if n >= N:
            break
