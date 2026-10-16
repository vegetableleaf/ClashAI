"""Own troop plays: (first-seen mid-gap tick - tap tick) minus the match median -> how much per-play latency varies."""
import sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from scratchpad.gauntlet.L74.parity import fights as F
from scratchpad.gauntlet.L74.parity.core import load_catalog, ps
import statistics
catalog, _ = load_catalog(); dev = Counter(); n = 0
for p in sorted(ps.LIVE.glob('live_play_2026101[5-9]_*.jsonl')):
    m, why = F.read_match(str(p))
    if not m: continue
    ev, delay = F.deployments(m, catalog)
    d = [e['tick']-e['tap'] for e in ev if e['source'] == 'own_tap']
    for x in d:
        dev[round((x-delay)/2)*2] += 1; n += 1
print(n, 'own troop plays; (delay - match median), 2-tick bins:', sorted(dev.items()))
