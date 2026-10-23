"""Build habits-format pickles for CLX live matches missing from habits/cache (idle priority, laptop).
  python build_extra.py LIST.txt   (one log stem per line) -> cache_extra/<stem>.pkl"""
import ctypes, pickle, sys
from pathlib import Path
try:
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x40)
except Exception:
    pass
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'habits'))
import build_cache as B, livelog
OUT = HERE / 'cache_extra'
for s in open(sys.argv[1]).read().split():
    if (B.HERE / 'cache' / f'{s}.pkl').exists() or (OUT / f'{s}.pkl').exists():
        continue
    m = livelog.read(B.LOGS / f'{s}.jsonl')
    if m is None:
        print('NOFRAMES', s, flush=True); continue
    pickle.dump(B.compact(m, dict(mark='ICEBOW Mark CLX: PARITY', log=f'{s}.jsonl')), open(OUT / f'{s}.tmp', 'wb'))
    (OUT / f'{s}.tmp').replace(OUT / f'{s}.pkl')
    print('ok', s, flush=True)
