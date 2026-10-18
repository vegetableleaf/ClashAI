"""Cube hp trajectories from live_freeze.json: is the hp loss a timer (linear decay) or enemy damage?"""
import json, statistics as st
from pathlib import Path
R = json.loads(Path(__file__).with_name('live_freeze.json').read_text())
rate = [(r['cube_max_hp'] - r['cube_hp_last']) / max(1, r['life_ticks']) for r in R]
print('hp lost per tick: median', round(st.median(rate), 2), 'deciles', [round(x, 2) for x in st.quantiles(rate, n=10)],
      '(timer-only decay over 100 ticks would be max_hp/100 =', round(st.median([r['cube_max_hp'] for r in R]) / 100, 2), ')')
print('max_hp values', sorted({r['cube_max_hp'] for r in R}))
full = [r for r in R if r['life_ticks'] >= 94]
print('cubes living >= 94 ticks', len(full), 'their last hp/max median', round(st.median([r['cube_hp_last'] / r['cube_max_hp'] for r in full]), 3) if full else None)
short = [r for r in R if r['life_ticks'] < 70]
print('cubes < 70 ticks', len(short), 'last hp/max median', round(st.median([r['cube_hp_last'] / r['cube_max_hp'] for r in short]), 3))
