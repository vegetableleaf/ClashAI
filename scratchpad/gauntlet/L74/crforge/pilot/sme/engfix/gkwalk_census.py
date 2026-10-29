"""ENG-FIX5 census for SME_GK_WALK: every Golden Knight ability of the given (OFF, SME_BP_GK on) records with its source,
dating, the burst-pair and next-pair Euclidean speeds (bp_rules._gk_move pairing) and whether gk_walk drops it (undated
gk_dash casts only). python -I gkwalk_census.py LIVE_DIR INPUTS.jsonl [...]"""
import json, os, sys
from pathlib import Path
S = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(S))
import bp_rules  # noqa: E402
import live_frames  # noqa: E402
n = drop = 0
for f in sys.argv[2:]:
    for l in open(f):
        r = json.loads(l)
        gk = [p for p in r['plays'] if p.get('card') == 'GoldenKnight' and p['kind'] == 'ability']
        if not gk:
            continue
        fr = {x['t']: x for x in live_frames.convert(os.path.join(sys.argv[1], r['match'] + '.jsonl'))}
        for p in gk:
            n += 1
            a, b = p['run_ticks'][0] + 1, p['run_ticks'][1] + 2
            c = min((t for t in fr if t >= b + 2), default=None)
            sp = []
            for u, v in ((a, b), (b, c)):
                e0, mv = bp_rules._gk_move(p, fr, u, v) if u in fr and v in fr else (None, None)
                sp.append(round((mv[0] ** 2 + mv[1] ** 2) ** 0.5 / (v - u)) if e0 else None)
            d = p.get('source') == 'gk_dash' and not p.get('dated') and bp_rules.gk_walk(p, fr)
            drop += d
            print(Path(f).name.split('_')[0], r['match'][10:], r.get('rng_free'), p['tick'], p.get('source'), p.get('dated'),
                  'burst', sp[0], 'next', sp[1], 'DROP' if d else 'keep')
print('casts', n, 'dropped', drop)
