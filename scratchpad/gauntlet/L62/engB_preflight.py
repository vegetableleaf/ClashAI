"""Preflight for engB: prove each engine slot can do what the TRAINER does -- construct a battle
and return an obs -- not just answer a socket. (The first version called observe() with no battle
and died on IndexError, which read as 'slots down' when the service was healthy.)"""
import sys
sys.path.insert(0, r"C:\Users\benpe\ClashBot\scratchpad\gauntlet\L62")
sys.path.insert(0, r"C:\Users\benpe\ClashBot\icebow\src")
from engine_env import EngineMatchEnv
bad = []
for port in (38031, 38032):
    try:
        env = EngineMatchEnv(port=port, seed=41)
        obs = env.reset(index=0)
        print("slot ok: %d obs %s tick %s" % (port, getattr(obs, "shape", "?"), getattr(env, "tick", "?")))
        try: env.close()
        except Exception: pass
    except Exception as ex:
        bad.append("%d %s: %s" % (port, type(ex).__name__, ex))
if bad:
    print("SLOTS DOWN: " + " | ".join(bad)); sys.exit(2)
print("SLOTS OK")
