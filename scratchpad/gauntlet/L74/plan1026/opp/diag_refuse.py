"""P2-OPP diagnostic: run gap.py's worker command IN PROCESS with search_s0.hab_plays patched to append each play's refusal
reason (hab rows get an 11th column). smoke_closed.py --diag uses it; run from the code-copy root:
    python scratchpad/gauntlet/L74/plan1026/opp/diag_refuse.py <the gap.py worker argv after the script path>"""
import sys
from pathlib import Path

ROOT = Path.cwd()
sys.path[:0] = [str(ROOT), str(ROOT / "scratchpad/gauntlet/L74/gap")]
from pipeline import search_s0 as S  # noqa: E402

orig = S.hab_plays
S.hab_plays = lambda side: [row + [q.get("reason")] for row, q in zip(orig(side), side.plays)]
import gap  # noqa: E402

sys.argv = ["gap.py"] + sys.argv[1:]
raise SystemExit(gap.main())
