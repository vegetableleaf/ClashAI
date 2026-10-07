"""next_alternate_tau alternates and survives a restart (fresh process = re-read state file)."""
import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from live_play import next_alternate_tau

with tempfile.TemporaryDirectory() as d:
    st = Path(d) / "alt.json"
    got = [next_alternate_tau(st, (0.35, 0.45)) for _ in range(5)]
    assert got == [0.35, 0.45, 0.35, 0.45, 0.35], got
    assert next_alternate_tau(st, (0.35, 0.45)) == 0.45      # state persisted across calls (as across restarts)
print("tau_alternate tests passed")
