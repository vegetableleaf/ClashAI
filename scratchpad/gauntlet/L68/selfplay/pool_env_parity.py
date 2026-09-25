"""T12a: RoyalePoolEnv after the self-play addition == RoyalePoolEnv at HEAD (a0f7c20), ghost-only matches.

    research/ext/Royale/.venv/Scripts/python.exe scratchpad/gauntlet/L68/selfplay/pool_env_parity.py
Compares the state hash + raw() every 10 ticks, and the episode, on the first 20 loadable held-out + train entries.
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.e1_pool import load_pool_v1  # noqa: E402
from pipeline.royale_env import RoyalePoolEnv, UnsupportedDeck  # noqa: E402

spec = importlib.util.spec_from_file_location("royale_env_head", HERE / "_royale_env_HEAD.py")
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

a, b = RoyalePoolEnv(), old.RoyalePoolEnv()
n = checks = 0
for e in load_pool_v1():
    try:
        a.reset(e)
    except UnsupportedDeck:
        continue
    b.reset(e)
    while not a.terminated and a.tick < a.tail_cap:
        a._advance_to(min(a.tick + 10, a.tail_cap))
        b._advance_to(min(b.tick + 10, b.tail_cap))
        assert a.core.state_hash() == b.core.state_hash() and a.raw() == b.raw(), (e["tag"], a.tick)
        checks += 1
    assert (a.episode, a.tick, a.ghost_ok, a.ghost_rejected) == (b.episode, b.tick, b.ghost_ok, b.ghost_rejected)
    n += 1
    if n == 20:
        break
print(f"PARITY OK: {n} entries, {checks} state/raw checks identical")
