"""RECON-7 pace probe worker (pod): gap.py's D3 --worker-all16 worker with each row's refusal reasons added.
usage (as the command gap.command builds, with this file in place of gap.py): python rr_wrap.py --worker-all16 --out ... """
import sys
CB = '/workspace/opp/cb'
sys.path[:0] = ['/workspace/smeR6/ov', CB, CB + '/scratchpad/gauntlet/L74/gap', CB + '/scratchpad/gauntlet/L74/livecal', CB + '/scratchpad/gauntlet/L74/heroiw']
from pipeline import search_s0 as S
_orig = S._run_job
def _rj(job):
    rec = _orig(job)
    lr = getattr(S._W.get('runner'), 'last_result', None) or {}
    if 'skipped' not in rec:
        rec['refuse_reasons'] = dict(lr.get('refuse_reasons') or {})
        rec['own_reasons'] = [[q['tick'], q.get('land_tick'), q['card'], q['accepted'], q.get('reason'), q.get('elixir_exact')] for q in lr.get('plays', [])]
    return rec
S._run_job = _rj
import gap
raise SystemExit(gap.main())
