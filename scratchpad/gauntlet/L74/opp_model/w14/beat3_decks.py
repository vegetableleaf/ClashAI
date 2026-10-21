"""W14 arm B input: mix/decks_live_train.json with sides x3 for every deck whose win condition (clx_ranked/anatomy.wincon on the
full engine deck, the key the O4-Ranked table splits on) is in BEAT. Nothing else changes (rank, engine, order).
    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/opp_model/w14/beat3_decks.py -> w14/decks_live_train_beat3.json"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import o4r_table as T  # noqa: E402

SRC = HERE.parents[1] / 'mix/decks_live_train.json'
d = json.loads(SRC.read_text(encoding='utf-8'))
H = T.AN.H
n = s0 = s1 = 0
for x in d['decks']:
    w = T.AN.wincon({H.norm(c) for c in x['engine']})
    s0 += x['sides']
    if w in T.BEAT:
        x['sides'] = int(x['sides']) * 3
        n += 1
    s1 += x['sides']
beat_sides = sum(x['sides'] for x in d['decks'] if T.AN.wincon({H.norm(c) for c in x['engine']}) in T.BEAT)
assert beat_sides * 3 > 0 and s1 > s0
d['source'] = f"{d['source']} + w14/beat3_decks.py (BEAT win conditions: sides x3)"
(HERE / 'decks_live_train_beat3.json').write_text(json.dumps(d), encoding='utf-8')
print(f'{len(d["decks"])} decks, {n} BEAT; BEAT share of sides {(beat_sides / 3) / s0:.3f} -> {beat_sides / s1:.3f}')
