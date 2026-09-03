"""Where does a reference (x, y) actually land after cell_at -> deploy_clamp -> cell_center?"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "icebow", "src"))
from clashrl.config import Config
from clashrl.sim import aggro_drills
from clashrl.sim.drill_env import DrillEnv
env = DrillEnv(Config.load(), aggro_drills.TANK_FOR_BOW, seed=5); env.reset()
A = env.actions
print("grid", A.gw, A.gh, "min_own_gy", A.min_own_gy, "first own row centre y", A.cell_center(0, A.min_own_gy)[1], "action_latency", env.action_latency)
for x, y in [(0.26, 0.50), (0.26, 0.55), (0.74, 0.50), (0.80, 0.52), (0.20, 0.52), (0.26, 0.60), (0.15, 0.50), (0.35, 0.50), (0.26, 0.47)]:
    c = A.cell_at(x, y); cc = A.deploy_clamp(False, c)
    print(f"ref ({x:.2f},{y:.2f}) -> cell {c} (gx{c%A.gw},gy{c//A.gw}) -> clamp {cc} -> lands {tuple(round(v,3) for v in A.cell_center(cc%A.gw, cc//A.gw))}")
print("own rows y:", [round(A.cell_center(4, gy)[1], 3) for gy in range(A.min_own_gy, A.gh)])
print("cols x:", [round(A.cell_center(gx, A.min_own_gy)[0], 3) for gx in range(A.gw)])
