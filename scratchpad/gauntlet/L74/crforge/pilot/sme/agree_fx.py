"""Does the extractor's new fx dating equal sme_live's SME_FX_SHIFT on the given matches?
    icebow/.venv/Scripts/python.exe -I agree_fx.py INPUTS.jsonl MATCH ...   (laptop: re-extracts from the live logs)"""
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'extract'))
import extract  # noqa: E402

FX = {'Lightning', 'Earthquake', 'Poison', 'Freeze', 'Vines', 'Graveyard', 'Clone', 'DarkMagic', 'GoblinCurse', 'Zap'}
recs = {json.loads(l)['match']: json.loads(l) for l in open(sys.argv[1])}
ROOT = HERE.parents[5]
same = diff = 0
for m in sys.argv[2:]:
    new, _ = extract.match(ROOT / 'scratchpad/gauntlet/L68/live_reader' / (m + '.jsonl'))
    old = recs[m]
    want = sorted((p['side'], p['card'], p['tick'] + (1 if p['card'] in FX and p['source'] == 'spell_seen' and
                   p['run_ticks'][0] == p['run_ticks'][1] else 0)) for p in old['plays'] if p['kind'] == 'play')
    got = sorted((p['side'], p['card'], p['tick']) for p in new['plays'] if p['kind'] == 'play')
    ok = want == got
    same += ok; diff += not ok
    print(m, 'agree' if ok else 'DIFFER', [x for x in got if x not in want][:5], [x for x in want if x not in got][:5])
print('agree', same, 'differ', diff)
