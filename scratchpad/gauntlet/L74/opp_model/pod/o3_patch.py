"""Pod-local telemetry patch for /workspace/o3/cb/pipeline/search_s0.py (an UNLINKED copy; cb_stepd is never touched).
With env O3_PLAYS=1 each eval row gets o3_plays = {learner, opp}: [[landing tick, card slug]] of every ACCEPTED play
(SelfPlaySide.accepted). Absent env = byte-identical rows. Idempotent; refuses if the anchor line moved.
    python o3_patch.py PATH/search_s0.py"""
import sys
from pathlib import Path

p = Path(sys.argv[1])
t = p.read_text(encoding='utf-8')
ANCHOR = '    rec["opp_deck_name"] = name\n'
ADD = ("    if __import__('os').environ.get('O3_PLAYS'):   # O3 pod-local telemetry (opp_model/pod/o3_patch.py)\n"
       "        rec['o3_plays'] = {k: [[int(a), str(c)] for a, c in getattr(getattr(m, k, None), 'accepted', [])]\n"
       "                           for k in ('learner', 'opp')}\n")
if ADD in t:
    print('already patched')
    sys.exit(0)
if t.count(ANCHOR) != 1:
    sys.exit(f'anchor found {t.count(ANCHOR)} times: refusing')
p.write_text(t.replace(ANCHOR, ANCHOR + ADD), encoding='utf-8')
print('patched', p)
