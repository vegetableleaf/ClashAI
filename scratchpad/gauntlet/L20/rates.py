"""Pass rates of the two aggro drills: nothing / scripted / late or wrong-lane variants, 40 reps, ladder roll."""
import dataclasses, sys; sys.path.insert(0, "src")
from clashrl.config import Config
from clashrl.sim import aggro_drills
from clashrl.sim.drill_env import run_drill, scripted_policy, report
cfg = Config.load(); aggro_drills.register_all()
def r(sc, pol=None, level=None):
    d = run_drill(cfg, sc, policy=pol, reps=40, seed=5, level=level)
    return f"pass {d['pass_rate']*100:.0f}% (p{d.get('pass')}/f{d.get('fail')}/t{d.get('timeout')})"
T, B = aggro_drills.TANK_FOR_BOW, aggro_drills.BOW_LANE_CHOICE
print("tank_for_bow nothing        :", r(T))
print("tank_for_bow scripted       :", r(T, scripted_policy(T)))
print("tank_for_bow scripted L16   :", r(T, scripted_policy(T), 16))
for t in (1.8, 3.0, 4.2):
    v = dataclasses.replace(T, reference=(("knight", 0.25, 0.5625, t),)); print(f"tank_for_bow knight@{t}      :", r(v, scripted_policy(v)))
v = dataclasses.replace(T, reference=(("knight", 0.25, 0.646, 0.6),)); print("tank_for_bow knight behind@0.6:", r(v, scripted_policy(v)))
v = dataclasses.replace(T, reference=(("knight", 0.75, 0.5625, 0.6),)); print("tank_for_bow knight far lane  :", r(v, scripted_policy(v)))
print("bow_lane_choice nothing     :", r(B))
print("bow_lane_choice scripted    :", r(B, scripted_policy(B)))
print("bow_lane_choice scripted L16:", r(B, scripted_policy(B), 16))
v = dataclasses.replace(B, reference=(("x_bow", 0.25, 0.5625, 0.6),)); print("bow_lane_choice same lane   :", r(v, scripted_policy(v)))
v = dataclasses.replace(B, reference=(("x_bow", 0.806, 0.5625, 0.6),)); print("bow_lane_choice x0.806      :", r(v, scripted_policy(v)))
v = dataclasses.replace(B, reference=(("x_bow", 0.917, 0.604, 0.6),)); print("bow_lane_choice row 0.604   :", r(v, scripted_policy(v)))
v = dataclasses.replace(B, setup=None); print("bow_lane_choice WITH noise  :", r(v, scripted_policy(v)))
print("\n-- report() (nothing / scripted / doctrine) --")
report(cfg, names=["tank_for_bow", "bow_lane_choice"], reps=40, seed=5)
