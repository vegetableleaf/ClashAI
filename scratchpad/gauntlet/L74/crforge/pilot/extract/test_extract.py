"""Ground-truth check of extract.py on the 10-26 replay-recorded match (both sides' exact hands from tick 0).

    icebow/.venv/Scripts/python.exe -I scratchpad/gauntlet/L74/crforge/pilot/extract/test_extract.py
Fails if the inputs (decks, slot flags, our deal) drift from the recording, or the play match falls below EXTRACT.md's.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[5]
sys.path.insert(0, str(HERE))
import extract  # noqa: E402

v = extract.validate(ROOT / 'scratchpad/gauntlet/L68/live_reader/live_play_20261026_130453.jsonl',
                     ROOT / 'icebow/data/replay_rec/rec_20261026_130926.jsonl')
assert all(v['deck_ok'].values()) and all(v['slot_flags_ok'].values()) and v['own_deal_ok'], v
assert v['truth_plays'] == 72 and v['truth_cycle_bad_frames'] == {0: 0, 1: 0}, v['truth_cycle_bad_frames']
for role, n in (('us', 37), ('opp', 35)):
    s = v[role]
    assert s['truth'] == s['matched'] == n and s['extra'] == 0, (role, s)
assert v['us']['window_ok'] >= 36 and v['opp']['window_ok'] == 35, (v['us'], v['opp'])
assert v['us']['tap_exact'] == 37 and v['opp']['tile_ok'] == 35, (v['us'], v['opp'])
# A2b-1b: the log-only derivation reproduces the API's levels and towers on this match (opponent's IceSpirits L15 included)
r, _ = extract.match(ROOT / 'scratchpad/gauntlet/L68/live_reader/live_play_20261026_130453.jsonl')
for s in ('0', '1'):
    A, D = r['sides'][s], r['derived'][s]
    assert sorted(zip(A['deck'], A['levels'])) == sorted(zip(D['deck'], D['levels'])), (s, A['levels'], D['levels'])
    assert A['towers'] == D['towers'], s
print('ok',{r: {k: v[r][k] for k in ('matched', 'window_ok', 'exact_tick', 'tile_ok')} for r in ('us', 'opp')})
