"""Association: matches where OUR king was activated (hit) by a bridge attacker while both princesses stood, vs not;
win rate and own princess loss. Live = real frames + results; pros = re-drive frames, REAL results.   python king_act.py"""
import pickle
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'habits'))
import hablib as H  # noqa: E402

R = pickle.load(open(HERE / 'rows.pkl', 'rb'))
OURS = ('CXXXVIII', 'CLIII', 'CLIX', 'CLX')
act = {r['key'] for r in R['bridge'] if r['king_hit'] and r['king_full_before']}
hog = {r['key'] for r in R['bridge'] if r['card'] == 'hog_rider'}
out = []
for g in ('pro', 'ours'):
    for lab, sel in (('all matches', lambda m: True), ('Hog matches', lambda m: m['key'] in hog)):
        ms = [m for m in R['match'] if m['group'] in (OURS if g == 'ours' else ('pro',)) and sel(m)]
        a = [m for m in ms if m['key'] in act]
        n = [m for m in ms if m['key'] not in act]
        out.append(f"{g:4s} {lab:12s} | king activated by a bridge attacker (both princesses up): {len(a) / len(ms):.3f} of "
                   f"{len(ms)} | win: activated {H.wr(a):.3f} {H.boot_ci(a, H.wr, B=400)} vs not {H.wr(n):.3f} "
                   f"{H.boot_ci(n, H.wr, B=400)}")
open(HERE / 'king_act.out', 'w').write('\n'.join(out) + '\n')
print('\n'.join(out))
