"""Live decision cadence from live_play logs (CLXIII calibration block): interval between consecutive decisions (ticks), and from a play-decision to the next decision."""
import sys, json, collections, statistics as st
from pathlib import Path
import orjson
H = Path('C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/opp_model/humanlike')
sys.path[:0] = [str(H), str(H.parent)]
import card
logs = [r['id'] for r in card.live_records('calibration')][::40][:20]
dts = []; after_play = []; plays_n = 0; dec_n = 0
for i in logs:
    ticks = []; plays = set()
    for raw in open(card.LOGS / i, 'rb'):
        if raw.startswith(b'{"event": "decision"'):
            try: j = orjson.loads(raw)
            except Exception: continue
            ticks.append(int(j['tick']))
        elif raw.startswith(b'{"event": "play"'):
            plays.add(int(orjson.loads(raw)['tick']))
    for a, b in zip(ticks, ticks[1:]):
        (after_play if a in plays else dts).append(b - a)
    plays_n += len(plays); dec_n += len(ticks)
def q(v): v = sorted(v); return [v[int(len(v) * p)] for p in (.02, .1, .25, .5, .75, .9, .98)]
print('logs', len(logs), 'decisions', dec_n, 'plays', plays_n)
print('dt between decisions, no play at the first: n', len(dts), 'quantiles', q(dts), 'mean %.1f' % st.mean(dts))
print('dt from a PLAY decision to the next decision: n', len(after_play), 'quantiles', q(after_play), 'mean %.1f' % st.mean(after_play))
c = collections.Counter(dts); print('most common dt (no play):', c.most_common(6))
c = collections.Counter(after_play); print('most common dt (after play):', c.most_common(8))
