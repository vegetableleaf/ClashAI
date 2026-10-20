"""Per matchup archetype: P(we lose >= 1 princess), P(we take >= 1), win -- live from real frames, pros from the REAL final
crowns (pro_sides.jsonl, not the re-drive).   python matchup_crowns.py -> matchup_crowns.out"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402  (re-runs analyze's tables; cheap enough, keeps ONE archetype definition)

real = {}
for line in open(HERE.parent / 'habits/pro_sides.jsonl', encoding='utf-8'):
    r = json.loads(line)
    if r['icebow8']:
        real[r['tag']] = (r['crowns'], r['opp_crowns'])
out = ['arch | group | n | win | P(lose >= 1 princess) | P(take >= 1) | P(both)  (pros: real final crowns; live: frames)']
for a in ('EQ', 'SIEGE', 'HOG', 'BEATDOWN', 'OTHER'):
    for g in ('pro', 'ours'):
        ms = [m for m in A.R['match'] if m['arch'] == a and m['group'] in (A.OURS if g == 'ours' else ('pro',))]
        if g == 'pro':
            cr = [real[m['key']] for m in ms if m['key'] in real]
        else:
            cr = [(m['our_cr'], m['their_cr']) for m in ms]
        lose = sum(t >= 1 for o, t in cr) / len(cr)
        take = sum(o >= 1 for o, t in cr) / len(cr)
        both = sum(o >= 1 and t >= 1 for o, t in cr) / len(cr)
        out.append(f"{a:8s} | {g:4s} | {len(cr):4d} | {A.H.wr(ms):.3f} | {lose:.3f} | {take:.3f} | {both:.3f}")
open(HERE / 'matchup_crowns.out', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
