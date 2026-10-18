"""card_use.results: a match whose result line is missing gets its change from the trophy readings around it."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import card_use

L = ['[ladder] trophies: 13000 total',
     '{"log": "x/live_play_1.jsonl"}', '[ladder] result: LOSS  (session) trophies +0',
     '{"log": "x/live_play_2.jsonl"}',                                   # no result line (trophy-road screen)
     '[ladder] trophies: 13033 total',
     '{"log": "x/live_play_3.jsonl"}', '[ladder] result: WIN  (session) trophies n/a',   # n/a -> inferred
     '[ladder] trophies: 13061 total',
     '{"log": "x/live_play_4.jsonl"}', '{"log": "x/live_play_5.jsonl"}',  # two unknowns between readings: left out
     '[ladder] trophies: 13100 total']
r = card_use.results(L)
assert r['live_play_1.jsonl'] == ('LOSS', 0), r
assert r['live_play_2.jsonl'] == ('WIN', 33), r
assert r['live_play_3.jsonl'] == ('WIN', 28), r
assert 'live_play_4.jsonl' not in r and 'live_play_5.jsonl' not in r, r
print('ok')
