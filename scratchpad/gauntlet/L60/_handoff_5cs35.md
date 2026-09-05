
### §5cs.35 -- L60c (2026-09-05 14:1x-14:2x UTC): ARM E READ AT m3.85k AND STOPPED (owner: "run an eval on E right now and determine whether it's worth to stop right now") -- the entropy floor 0.05 did NOT resist the collapse: knight@426 35/39, 35/37, 35/40 (3 probe seeds), tesla distinct 8/6/4, pro-cell agreement 2.59/9.36 (baseline 3.49/11.75), cell head back to 82.4% at the tanh rails 3,850 matches after the guard's x0.043 rescale; E killed at 3,975 episodes; box free (9.8 GB available)

Owner (14:1x UTC): "Run an eval on E right now and determine whether it's worth to stop right now. E is
running on a fundamentally incorrect sim that is only 1/4 parity with the real game." Done as a mechanism
read, not a winrate eval (150 greedy matches = +-8pp, and in a 26%-parity sim it measures the wrong game).

**Read (snapshot `data/bench/armE_m3k85_now.pt` = `policy_armE_20260905.pt` at 14:16 UTC, sha 09e581e8...,
3,850 episodes; `L60/reads_armE_m3k85_now.txt`, `L60/baseline_armE_m3k85.json`, `L60/rails_read.py`). (a),
one training seed.**
- place_probe (greedy card+cell, 6x400 steps, seeds 0/1/2): knight@426 **35/39, 35/37, 35/40** (distinct
  4/3/2); tesla@234 19/29, 19/25, 25/28 (distinct **8/6/4**); skeletons@423 52/52, 50/51, 52/52; x_bow@234
  6/10, 7/8, 2/4; the_log distinct 22/16/18; ice_wizard distinct 14/16/16. Reference: c2r_best s0 knight
  19/39 (8 distinct), tesla 14/24 (9); G m5k knight 18/36, 22/38, 16/36 (13/9/10), tesla 11/7/14 distinct.
- Pro-cell agreement on the 1,004 held-out rows (same instrument as §5cs.34): **top-1 2.59 / top-5 9.36**
  vs c2r_best 3.49 / 11.75; knight 0.0/3.2, tesla 1.0/1.9, x_bow 0.0/0.0, the_log 9.8/32.9; masked entropy
  1.148 nats (baseline 0.950); top-1 histogram 423 x207, 235 x174, 374 x92, 341 x86.
- Rails: masked raw cell logits |raw| > 8 on **82.4%** (mean -15.3, min -86.6, p99 42.8) vs c2r_best 92.2%
  (mean -23.3, p99 62.0). The resume guard had rescaled the head x0.043 at m0 (p99 ~2.7); it re-saturated
  to 82% within 3,850 matches WITH the entropy floor at 0.05.

**Decision: stopped now.** (a) On 3/3 probe seeds the placements are already more concentrated than the
baseline and than G at m5k, pro agreement fell, and the head is back at the rails; another 1,150 matches
to m5k could only confirm a trend already visible. Killed 14:19 UTC at **3,975 episodes** (6%, avg_rew
-17.7, 203W-2942L-2D, 0.8 ep/s); trees 64040 (launcher), 21472 (watchdog), 3492 (arm_gates) via taskkill
/T /F from PowerShell; python 21 -> 3 (2 = the L60 board_value agent's jobs, 1 = Nucleo uvicorn 63608);
available RAM 9.83 GB. Final weights = `policy_armE_20260905.pt` (untouched since 14:16); state file
`L60/armE_stop_state.txt`. Monitor outputs `armE_run_watchdog.out`, `armE_gates.out` left in place.

**What E establishes / does not.** (a) The cell-entropy floor 0.05 (vs 0.008) does not keep the head off
the rails or the placements spread when resuming from c2r_best: same collapse as G, faster to read. Combined
with §5cs.34's rails finding, the entropy bonus is being applied to a head whose gradient is ~0 -- so a
larger coefficient cannot help. (b) Whether ANY resume from c2r_best can avoid this is now the untested
default assumption: the next PPO must start from a rescaled or re-initialised head (and, per the plan,
from a BC init). E vs G was one seed each; no control run existed for either -- neither arm attributes
anything to its reward/entropy change beyond "did not prevent the collapse".

**Trap.** The trainer's own "ent=0.06" log field is the sampled policy entropy over all heads, not the
masked cell-map entropy; it read 0.05-0.06 throughout while the cell head went to 82% rails. Use
`L60/rails_read.py <ckpt>` (val split, ~3 s on cuda) as the instrument for head health from now on.
