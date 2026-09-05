
### §5cs.31 -- L59b (2026-09-05 05:1x-05:4x UTC; box local = EDT = UTC-4): owner ruling "timing + placement is an AND gate" -> `_geo_credit` REWRITTEN to the multiplicative form; arm G v1 (additive) STOPPED at 725 episodes and RELAUNCHED 05:13 UTC as v2 from a re-seeded c2r_best; Chrome closed (owner-permitted) but the box still fits ONE 12-worker arm (G costs 7.4 GB of available RAM, measured); G+E stays QUEUED

**Owner rulings (05:0x UTC, verbatim intent):** "You have my permission to close Chrome. Also for the timing +
placement payment, it should be 2-way (good timing, bad placement is not rewarded, and neither should good
placement, bad timing). So it's basically an AND gate, but with some nuance. Everything else looks good."

**The reward change (`sim/env.py::_geo_credit`, uncommitted -> this commit):**
- v1 (§5cs.30, additive): `w_time*P5 + w_geom*place*gate`, paid when `place > 0`. Defect the owner caught: a
  perfect placement at a bad time still collected `w_geom*place` = up to +2.0 (scenario row hog tile 12.3:
  P5 0.07, credit +2.07), i.e. "good placement, bad timing" WAS rewarded.
- v2 (AND): `credit = (w_time + w_geom) * place * P5 * gate` when `place > 0`, else 0. Both factors in
  [0, 1] multiply, so either one at 0 pays 0 and a partial one scales the whole credit (the "nuance" = P5's
  1.5 s bands and the graded P1/P3). Max unchanged at 3.0. `gate` is P5's window widened by `pre_place_s` on
  the early edge, so it is 1.0 wherever P5 > 0 -- redundant now, kept so the config key means what it says.
  Comments in `config.yaml`, `armG_run.yaml`, `armGE_run.yaml` updated to the new formula.
- Tests: `tests/test_geometry_wiring.py` +`GeometryCreditIsAnAndGate` (5 cases: both good = 3.0; bad
  placement + good timing = 0; good placement + bad timing = 0; P5 0.07 -> 0.21 not 2.07; gate 0.5 halves).
  `test_geometry_reward` + `test_geometry_wiring` = 34 tests OK (the disabled path is still byte-identical to
  HEAD's reward on the 2 fixed-stream matches, 1e-9). (a)
- Hog-vs-Tesla(9,21) scenario rerun (`geo_scenario_v3.txt`): credit +2.54 / +3.0 / +3.0 at hog tile 14.7 /
  15.9 / 17.1 (v1: +2.85 / +3.0 / +3.0), 0 at 18.3+ and 0 at 12.3/13.5 (env sees no threat yet, `tid0` 0) --
  the paid window is the SAME, only the early-edge row scaled down (P5 0.85). (a)
- Baseline rerun (`geo_ledger_c2rbest_s0_AND.txt`, c2r_best seed 0 greedy, same 6x400 steps): `geo_credit`
  23 fires (identical set -- `place > 0` is unchanged) sum +38.5 (v1 +47.9, -20%); every per-term P value
  identical (p1 13/+6.03, p2 41/+20.5, p3 25/+18.3, p5 78/+65.4, p6 9/+9.0). Per card: tesla 24 scored /
  2 paid, mean paid +0.84 (v1 +1.56), mean P1 0.039; tesla_evo 9/4 +1.56; ice_wizard 47/10 +1.44 (v1 +1.80);
  knight 39/4 +2.43; x_bow 13/2 +2.57; skeletons 53/0. THIS is the baseline the m5k/m10k reads compare
  against (same instrument, same form). (a)

**Arm G v1 STOPPED (state at the kill, from the archived log `armG_run_20260905_v1_additive_STOPPED.log`):**
725 episodes, winrate 10% (35W-533L-1D), avg_rew -15.9, 0.8 ep/s, rail guard x0.0430; the curve was c2r's
resume shape. Killed by `taskkill /PID <root> /T /F` on the 3 tree roots (bash 26376, nohup 50388, nohup
2800); python procs 19 -> 1 (the owner's uvicorn), 0 matching. Watchdog archived `armG_run_watchdog_v1.out`.
Its 725 episodes of additive-reward gradient went into `data/policy_armG_20260905.pt` (sha b3f41602...), so
that file was RE-COPIED from `data/bench/c2r_best_36k_backup.pt`; all three (backup, armG, armGE) verified
sha256 d209b41e... before the relaunch. (a)

**Chrome closed (owner-permitted) -- what it bought, measured:** before: available 11.0 GB (Chrome 30 procs
gone, nothing training; sum of working sets 18.2 GB: VS Code 2.84, msedgewebview2 1.4, compression 1.39,
crosvm 1.32, Discord 1.16, docker-desktop WSL VM running). After arm G v2 warmed up: available **3.6 GB** ->
one 12-worker arm costs **7.4 GB of available RAM** (the §5cs.30 "9.7 GB RSS" was a working-set sum that
double-counts the shared torch/CUDA pages across 13 processes). A second 12-worker arm would need ~7.4 GB
more than exists. CPU 80% with G alone (16 cores, 12 workers + learner). (a)

**ARM G v2 RELAUNCHED 05:13 UTC** (`armG_run_launch.sh`, log `armG_run_20260905.log`, `.launched`
1788585192): the c2r CLI exactly as §5cs.30 (`--resume --matches 40000 --envs 96 --workers 12 --size 432
--device cuda --seed 41 --search-interval 4`), the ONE change vs c2r still `env.geometry.enabled: true`.
Rail guard x0.0430 (raw 105) -- identical to v1, as it must be (same seed file). 125 episodes: 10% (5W-98L),
avg_rew -21.6, 0.7 ep/s, ent 0.05 (v1 at 125: -29.4; c2r's resume -31.2 -- within the resume-shape noise,
not a reading). Detached: trainer (learner 31656 under 36260), `ppo_watchdog` (`armG_run_watchdog.out`),
`arm_gates.py --run armG_20260905` (`armG_gates.out`; m5k/m10k/m20k snapshot + place_probe x3 + geo ledger
x2 + gate_prior_probe -> Discord). Both monitor outputs are empty for the first minutes (python stdout
buffering, not a failure -- the v1 watchdog file filled the same way). m5k ETA ~07:1x UTC at 0.7 ep/s.

**Decisions taken on the owner's behalf (veto in the morning):**
1. G+E NOT launched alongside G. Two 12-worker arms do not fit (3.6 GB available with G running). The
   alternative -- two half-size arms (`--envs 48 --workers 6`) -- was rejected because `--envs` sets the PPO
   batch (one update per horizon across K envs, `train_sim_ppo.py` ~1852), so it would make G differ from
   c2r in TWO ways (reward + batch) and halve each arm's speed; the owner's "two at a time" is a scheduling
   wish, "one change per experiment" is a rule. G+E launches when G is stopped or done; yaml + launcher ready.
2. v1's 725 episodes were discarded rather than continued under the new formula: a checkpoint that spent
   725 episodes learning the additive credit is not "c2r_best + one change".
3. `gate` kept in the product (harmless: 1.0 wherever P5 > 0) rather than deleted, so the `pre_place_s`
   config key keeps its meaning for a later pre-place doctrine arm.
4. Chrome closed with `taskkill /IM chrome.exe /F` (30 -> 0 procs); nothing else of the owner's touched
   (docker-desktop WSL, crosvm, Discord, Steam, Nucleo uvicorn 8765 all left alone).

**What this does NOT establish:** whether the AND form (or any graded form) moves the placement
distribution -- the m5k read is the first data point, one seed, a screen. The v1 -> v2 baseline difference
(-20% credit sum on the same 23 fires) is arithmetic on a fixed rollout, not a training result.

**Traps found.** (1) `taskkill` from Git-Bash mangles `/IM` into a path (`C:/Program Files/Git/IM`) -- run
it from PowerShell, or `taskkill //IM`. (2) HANDOFF times in §5cs.30 and here are UTC (`date -u`); the box's
local clock is EDT = UTC-4 (`.launched` 1788585192 = 05:13:12 UTC = 01:13 local). (3) `FreePhysicalMemory`
and "Available MBytes" agree here (standby cache only 1.4 GB) -- but the "python RSS" figure from a
working-set SUM overstates a multi-process arm by ~2 GB; measure an arm's cost as the DROP in available
RAM after it warms up. (4) The paid SET under `place > 0` is form-independent -- switching additive -> AND
changes only the amounts, so fire counts alone cannot tell the two forms apart in a ledger.
