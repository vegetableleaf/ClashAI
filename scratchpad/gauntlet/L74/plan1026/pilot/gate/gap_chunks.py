"""gap_chunks.py -- gap.py with the 480-game schedule cut to its first GAP_CHUNKS chunks (12 seeds each): DRY RUNS ONLY.
Same CLI as gap.py (gate.sh: GATE_GAP=<this file> GAP_CHUNKS=3 = 36 games per block). Everything else is gap.py's code."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'gap'))
import gap  # noqa: E402

N = int(os.environ['GAP_CHUNKS'])
_schedule = gap.livecal.schedule


def schedule(*a, **k):
    plan = _schedule(*a, **k)
    plan['jobs'] = plan['jobs'][:N]
    plan['games'] = sum(len(j['seeds']) for j in plan['jobs'])
    return plan


gap.livecal.schedule = schedule
if __name__ == '__main__':
    raise SystemExit(gap.main())
