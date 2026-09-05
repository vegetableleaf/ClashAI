
### §5cs.32 -- L59c (2026-09-05 12:4x-13:2x UTC): ARM G v2 READ at m5k/m10k (3 seeds each) -- placements COLLAPSED between m5k and m10k (knight 426 on 41/41, 36/36, 35/36; tesla 5 distinct cells on every seed; credits fired 23 -> 8-9); owner order "No control ... Go straight to E" -> G STOPPED at 15,750 episodes, ARM E (c2r + entropy floor 0.05, geometry OFF) LAUNCHED 13:0x UTC; the gauntlet wakeup FAILED to fire overnight (05:4x -> 12:45 UTC unattended; the detached arm_gates.py took and posted both reads)

**Owner (12:5x UTC, after the morning summary):** "No control. We've already wasted enough time because your
wakeup keeps on failing to fire overnight. Go straight to E." Applied as written. The limit this imposes,
stated once so nobody over-reads the E result later: E vs G can show whether the entropy floor RESISTS the
m5k->m10k collapse; neither arm can show whether the graded reward CAUSED it (that needed the geometry-off
resume). (b)

**Arm G v2 reads (`L59/reads_armG_20260905_m5k.txt`, `_m10k.txt`; place_probe greedy card+cell, 3 seeds;
geo_ledger_probe 2 seeds; gate_prior_probe seed 0). Baseline = c2r_best under the same AND instrument
(`geo_ledger_c2rbest_s0_AND.txt`, seed 0): tesla@234 14/24 (9 distinct), knight@426 19/39 (8 distinct),
skeletons@423 53/53, 23 credits sum +38.5, tesla mean P1 0.039.**
- m5k (snapshot 03:35 local = 07:35 UTC): tesla@234 13/27, 20/28, 16/31 -- distinct 11 / 7 / 14; knight@426
  18/36, 22/38, 16/36 -- distinct 13 / 9 / 10; skeletons 51/51, 46/46, 49/49 at 423. Ledger (s0/s1): credits
  16/+26.1, 16/+30.4; tesla paid 2 / 4, mean P1 0.104 / 0.153; knight paid 8 / 7, mean P3 0.361 / 0.263.
  Gate prior: P(play) 0.148 all / 0.172 affordable, elixir >=6 3.4%. Reading: at m5k the distribution is at
  least as spread as the baseline (more distinct cells on 2 of 3 seeds) and tesla P1 is up 2.6-3.9x. (a, one
  training seed)
- m10k (06:07 local = 10:07 UTC): tesla@234 21/28, 27/31, 24/28 -- distinct 5 / 5 / 5; **knight@426 41/41,
  36/36, 35/36 -- distinct 1 / 1 / 2**; skeletons 52/52, 48/48, 52/52. Ledger: credits 8/+18.6, 9/+16.8
  (baseline 23); tesla paid 1 / 4, P1 0.091 / 0.160; knight paid 2 / 0, P3 0.037 / 0.028. Gate prior:
  P(play) 0.170 / 0.201, elixir >=6 1.9%. (a)
- Watchdog (`armG_run_watchdog_v2.out`, 6 alerts): CELL HEAD COLLAPSED 1.16 / 1.08 / 1.15 of 5.08 nats
  (33 / 43 / 38 distinct cells) at m7350 / m12700 / m13350; cell-structure drift 49% below the run median at
  m6000; elixir>=6 drift 49% below at m11450. (a)
- Eval (150 greedy matches each): ladder 37 / 39 / 27 / 23 / 36 / 27 / 35 % at m2k..m14k; fair 25 / 29 /
  25 / 14 / 24 / 19 / 27 %. Wobble inside the +-8pp band; winrate is not a discriminator. (a)
- Stopped 12:5x UTC at **15,750 episodes** (8% rolling, 1180W-11345L-2D, avg_rew -16.7, 0.6 ep/s). Trees
  killed by `taskkill /PID /T /F` on the roots 27544 (launcher), 70132 (watchdog), 48740 (arm_gates); python
  19 -> 1 (Nucleo uvicorn), nohup 1 (Nucleo). Final weights snapshotted: `data/bench/armG_m15k7_final.pt`
  (sha 3d7713b7..., = `data/policy_armG_20260905.pt` at the kill); m5k/m10k snapshots `armG_m5k.pt`,
  `armG_m10k.pt`. Monitor outputs archived `_v2`. State file `L59/armG_stop_state.txt`.

**What G establishes / does not.** (a) Under the graded AND reward, ONE training seed, placements got
MORE concentrated between m5k and m10k (knight to a single cell on 3/3 probe seeds; tesla to 5 cells on
3/3) and the number of placements the geometry module was willing to pay fell from 23 to 8-9 per 6x400
steps. (b) Whether that is the reward or the resume dynamics (rail guard x0.043 then re-saturation -- c2r
itself collapsed the same way late) is NOT attributable: no geometry-off control was run, by owner order.
Design fault recorded against the L59 plan: the arm was compared to a baseline CHECKPOINT, not a baseline
RUN. A suspect, untested: the credit pays only once a threat is visible, so the cheapest policy that
collects it is the one tile the module already scores highest -- a reward that grades placement can still
narrow it. (b)

**ARM E LAUNCHED 13:0x UTC** (`data/bench/armE_run_launch.sh`, log `armE_run_20260905.log`): `armE_run.yaml`
= `armGE_run.yaml` with `env.geometry.enabled: false` and the armE checkpoint/continuation paths; loaded
values checked through `Config.load`: `sim.ppo_cell_entropy_floor` 0.05 (c2r 0.008; read at
`train_sim_ppo.py:567` from `sim:`), geometry False, gate prior coef 2.0, hazard 0.5. Seeded from
`c2r_best_36k_backup.pt` (sha d209b41e... verified on both files). Same CLI as G/c2r. Rail guard x0.0430
(raw 105) -- identical, same seed file. 125 episodes: 6%, avg_rew -32.0, 0.8 ep/s, ent 0.03. The log's
"cell entropy coefficient 0.05" line is the START coef and reads the same for c2r -- the floor is not
printed; the yaml value is the evidence. Detached: trainer, `ppo_watchdog` (`armE_run_watchdog.out`),
`arm_gates.py --run armE_20260905` (`armE_gates.out`; m5k/m10k/m20k reads -> Discord), both started with
`python -u` this time so the outputs are not buffered. Available RAM 8.3 GB before launch. m5k ETA ~15:0x
UTC at 0.7 ep/s.

**The wakeup failure (owner's complaint, correct).** `ScheduleWakeup` at 05:4x UTC (delay 3600 s) never
fired; the session sat idle 7 h until the owner's message. Same failure mode as earlier nights. The reads
were not lost because `arm_gates.py` is a detached process that snapshots, probes and posts to Discord on
its own -- that design is the mitigation, and every arm must have it. Open: whether a `CronCreate` job is
more reliable than `ScheduleWakeup` in this harness (untested; the owner is awake today, so the loop is
paced by the arm_gates posts).

**What to compare at E's m5k / m10k (same instrument as G's reads):** knight@426 share and distinct cells
(G: 18/36 -> 41/41), tesla@234 share and distinct (G: 13/27 -> 21/28, 11 -> 5), watchdog cell-head nats
(G: 1.08-1.16 of 5.08 by m7k), gate P(play) (G: 0.148 -> 0.170). If E holds the m5k spread to m10k where G
lost it, the entropy floor resists the collapse (one seed -- a screen). If E collapses the same way, the
collapse is the resume, not the reward -- and G+E is the next arm, not another reward change.

**Traps.** (1) `taskkill /PID <root> /T` from PowerShell kills the tree; from Git-Bash the `/T` and `/F`
flags are mangled into paths (use `//`). (2) `Get-Process python` count 1 = the owner's Nucleo uvicorn; the
Nucleo `nohup.exe` (38408) is also the owner's -- leave both. (3) `arm_gates.py` derives the checkpoint from
`--run` (`data/policy_<run>.pt`) and its state file `L59/gates_<run>.progress` -- a rerun on the same run
name resumes at the next gate. (4) Available RAM dipped to 0.77 GB minutes after E's launch while the
watchdog's first probe overlapped the trainer's warm-up -- transient, see the follow-up reading in L59c's
log block.
(5) RAM leak found, NOT cleared (classifier blocked the kill): powershell PID 22200 = `scratchpad/bb/stt.ps1`,
a speech-to-text helper from a 2026-09-04 21:43 session, hung after writing its transcript (21:56) and holding
2.3 GB for 15 h. With E + monitors running, available RAM is 0.6-1.2 GB; the owner should kill it
(`taskkill /PID 22200 /T /F`). Until then E runs with ~1 GB headroom (pagefile 6% -- not swapping yet).
