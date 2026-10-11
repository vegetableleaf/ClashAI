"""Toy-size P3 or P4 through the REAL driver.execute (review aid; production budgets are untouched in driver.py).

  smoke_phases.py P3 RESULTS    2 cycles of 1 main + 1 exploiter update, final segment clamped to 3, 2 actors, E=G=2
  smoke_phases.py P4 RESULTS    the graft, the three arms and the report on 4 games per census (not 480), 3 workers
RESULTS must hold MEMP1/pro_memory.npz(+SUCCESS) and MEMP2/memory_pretrained.pt(+SUCCESS) from a toy P1/P2.
"""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import driver as D  # noqa: E402

phase, results = sys.argv[1], Path(sys.argv[2])
PREFIX = 'smoke_mem'
real_config, real_report, real_eval = D.config, D.report, D.A.eval_command


def small_config(*a, **k):
    c = real_config(*a, **k)
    c.update(D.A.SMOKE_CFG)
    c['max_updates'] = min(c['max_updates'], 3)
    return c


def small_plans(prefix=PREFIX):
    out = D.A.cycle_plan(prefix, cycles=2, main_updates=1, exploiter_updates=1)
    for p in out:
        p['exploiter_init'] = p['frozen']
    return out


D.config, D.plans = small_config, small_plans
D.report = lambda ev, games=4: real_report(ev, 4)
D.A.eval_command = lambda ck, out, census, start, workers=3, games=4: real_eval(ck, out, census, start, 3, 4)
D.execute(SimpleNamespace(results=results, phase=phase, prefix=PREFIX, cap=256, actors=2, seed=74, workers=3,
                          init=D.A.FAST, template=D.A.DATA, corpus=None, epochs=1, kl=1.0))
print(phase, 'SMOKE_EXECUTE_OK')
