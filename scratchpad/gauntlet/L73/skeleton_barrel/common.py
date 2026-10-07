"""Shared helpers: low-priority CPU setup and Skeleton Barrel / Log constants (read-only analysis)."""
import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'
for k in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[k] = '4'
try:
    import psutil
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception:          # pragma: no cover -- priority is best effort; thread caps above still hold
    pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
SB_IDS = {26000056, 13000056}        # base / evo Skeleton Barrel (balloon AND its skeletons carry the card id)
LOG_ID = 28000011
BALLOON_MIN_HP = 300                 # balloon max_hp 532..773+ ; skeletons 81..130
ROLL_MT_PER_TICK = 200               # measured below (live Log rows): rolling Log advances 200 millitiles / tick
ROLL_RANGE = 10100                   # catalog LogProjectileRolling.projectile_range_milli
HALF_W, HALF_D = 1950, 600           # catalog rolling hitbox half-width (x) / half-depth (y)
