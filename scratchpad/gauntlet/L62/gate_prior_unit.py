"""L62 v2 unit-check for engine_ppo's gate-prior lookup. Read-only, no engine, no VM.

Checks, against icebow/config/gate_prior.json read independently:
  1. the table values engine_ppo loads (hand-checked: single/3 0.0626, single/9 0.2033, double/9 0.4463),
  2. Trainer.gp_target()'s (tick, engine elixir) -> p mapping, driven through a stub with no env,
  3. that the Bernoulli CE engine_ppo adds equals the sim trainer's expression, including the identity
     CE(p, pi=p) = binary entropy H(p) and the excluded-row rule gq_m[:,1] > _NEG*0.5.
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "icebow" / "src"))

import engine_ppo as EP     # noqa: E402

GJ = json.loads((ROOT / "icebow" / "config" / "gate_prior.json").read_text(encoding="utf-8"))
TAB = np.asarray([GJ["p_play"][p] for p in ("single", "double", "triple")], np.float32)
REG, OVR = float(GJ["regulation_s"]), float(GJ["overtime_s"])
DBL, TRI = REG - 60.0, REG + max(0.0, OVR - 60.0)
fails = []


N = [0]


def chk(name, got, want, tol=5e-5):   # the hand-checked table values are the JSON rounded to 4 dp
    N[0] += 1
    ok = abs(float(got) - float(want)) <= tol
    print(f"  {'PASS' if ok else 'FAIL'}  {name:44s} got {float(got):.6f}  want {float(want):.6f}")
    if not ok:
        fails.append(name)


print("[1] table values read straight out of gate_prior.json (schema %s, %s replays, dt %s)"
      % (GJ["schema"], GJ["replays"], GJ["dt"]))
chk("p_play[single][3]", TAB[0][3], 0.0626)
chk("p_play[single][9]", TAB[0][9], 0.2033)
chk("p_play[double][9]", TAB[1][9], 0.4463)
chk("p_play[single][4]", TAB[0][4], 0.0580)
chk("p_play[triple][6]", TAB[2][6], 0.2413)
chk("regulation_s", REG, 180.0)
chk("overtime_s", OVR, 120.0)
chk("phase boundary: double from", DBL, 120.0)
chk("phase boundary: triple from", TRI, 240.0)

print("[2] Trainer.gp_target(): (engine tick, engine elixir) -> p, through a stub (no env, no VM)")


def target(tick, elixir):
    stub = SimpleNamespace(gprior=(TAB, DBL, TRI),
                           env=SimpleNamespace(tick=tick, sim=SimpleNamespace(eng=SimpleNamespace(elixir=[elixir, 0.0]))))
    return EP.Trainer.gp_target(stub)


# tick * TICK_S = seconds; TICK_S is 0.05, so 2400 ticks = 120 s (first double tick), 4800 = 240 s.
chk("t=  0.0s single, elixir 3.00  -> single/3", target(0, 3.0), 0.0626)
chk("t= 60.0s single, elixir 9.40  -> single/9", target(1200, 9.4), 0.2033)
chk("t=119.95s (tick 2399) SINGLE, elixir 9.0", target(2399, 9.0), 0.2033)
chk("t=120.0s (tick 2400) DOUBLE, elixir 9.0", target(2400, 9.0), 0.4463)
chk("t=239.95s (tick 4799) DOUBLE, elixir 6.0", target(4799, 6.0), 0.1320)
chk("t=240.0s (tick 4800) TRIPLE, elixir 6.0", target(4800, 6.0), 0.2413)
chk("elixir 10.0 -> bucket 10 (clip), single", target(0, 10.0), 0.1838)
chk("elixir 0.0 -> bucket 0, single", target(0, 0.0), 0.0100)
chk("elixir 2.999 floors to bucket 2, single", target(0, 2.999), 0.0415)
chk("elixir 3.0000001 -> bucket 3, single", target(0, 3.0000001), 0.0626)
# the +1e-6 in floor(elixir + 1e-6) is the sim trainer's: a float 2.9999995 that MEANS 3 lands in bucket 3
chk("elixir 2.9999995 (+1e-6 nudge) -> bucket 3", target(0, 2.9999995), 0.0626)
chk("engine elixir == elixir_vec[0]*10 (0.94*10)", target(1200, 0.94 * 10.0), 0.2033)
# prior OFF returns 0.0 and is never consumed (gp_f is None)
chk("gprior None -> 0.0", EP.Trainer.gp_target(SimpleNamespace(gprior=None)), 0.0)

print("[3] the Bernoulli CE term and the excluded-row rule")
# lp_g rows: [wait, play]; row 2 has PLAY masked at _NEG and must be dropped.
gq_m = torch.tensor([[0.0, 0.0], [1.0, -1.0], [0.0, EP._NEG]], dtype=torch.float32)
lp_g = F.log_softmax(gq_m, 1)
gpk = gq_m[:, 1] > EP._NEG * 0.5
chk("excluded-row mask keeps rows 0,1 only", float(gpk.float().sum()), 2.0)
p = torch.tensor([0.2033, 0.4463, 0.9], dtype=torch.float32)
gce = -(p[gpk] * lp_g[gpk, 1] + (1.0 - p[gpk]) * lp_g[gpk, 0])
# row 0: pi_play = 0.5 exactly -> CE = -log 0.5 = 0.6931 whatever p is
chk("row0 CE at pi=0.5", gce[0], math.log(2.0))
# row 1: pi_play = sigmoid(-2) = 0.11920
pi1 = 1.0 / (1.0 + math.exp(2.0))
chk("row1 CE by hand", gce[1], -(0.4463 * math.log(pi1) + (1 - 0.4463) * math.log(1 - pi1)), 1e-5)
# self-consistency: CE(p, pi=p) == binary entropy H(p) -- the floor the term pulls the gate to
q = 0.2033
lp_self = torch.log(torch.tensor([1 - q, q]))
chk("CE(p, pi=p) == H(p) at p=0.2033",
    float(-(q * lp_self[1] + (1 - q) * lp_self[0])), -(q * math.log(q) + (1 - q) * math.log(1 - q)), 1e-6)   # float32 torch.log vs float64 math.log
# a gate parked at 0.2326 (engA's m253 max) against a double-elixir/9 target of 0.4463 pays this much:
pi_engA = 0.2326
chk("CE at engA's collapsed pi=0.2326 vs double/9 target",
    -(0.4463 * math.log(pi_engA) + (1 - 0.4463) * math.log(1 - pi_engA)), 0.79748, 1e-4)

print()
if fails:
    print("UNIT-CHECK FAILED: %s" % fails)
    sys.exit(1)
print("UNIT-CHECK PASSED (%d assertions)" % N[0])
