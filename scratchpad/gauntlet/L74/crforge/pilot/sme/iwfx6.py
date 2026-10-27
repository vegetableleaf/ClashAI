"""Hero Ice Wizard ability area (card 203000023) first sightings vs the extracted ability casts (ticket A2c round 6).
    icebow/.venv/Scripts/python.exe -I iwfx6.py INPUTS.jsonl OUT.jsonl
Per area generation: side, first tick, remaining ms at first sighting, the max remaining seen, and the nearest
extracted IceWizard ability cast of that side (tick, source, dated, run window)."""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'extract'))
import extract  # noqa: E402
fights = extract.fights

IW_AREA = 203000023
with open(sys.argv[2], 'w') as w:
    for l in open(sys.argv[1]):
        r = json.loads(l)
        m, why = fights.read_match(extract.LIVE / (r['match'] + '.jsonl'))
        if m is None:
            continue
        g = {}
        for t in sorted(m['fx']):
            for e in m['fx'][t]:
                if e[3] == IW_AREA:
                    d = g.setdefault(e[6], dict(side=e[0], first=t, rem0=e[4], maxrem=e[4], x=e[1], y=e[2]))
                    d['last'] = t; d.setdefault('rows', []).append([t] + list(e[4:6])) if len(d.get('rows', [])) < 4 else None
        casts = [p for p in r['plays'] if p['kind'] == 'ability' and p['card'] == 'IceWizard']
        for gen, d in g.items():
            c = min((p for p in casts if p['side'] == d['side']), key=lambda p: abs(p['tick'] - d['first']), default=None)
            w.write(json.dumps(dict(match=r['match'], my_side=r['my_side'], gen=gen, **d,
                                    cast=c and dict(tick=c['tick'], src=c.get('source'), dated=c.get('dated'), win=c['run_ticks']))) + '\n')
