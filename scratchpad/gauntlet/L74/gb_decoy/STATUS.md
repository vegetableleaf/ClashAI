# GB-DECOY status (ticket GB-DECOY; worker doc for re-dispatch)

## Done
- Measurement (a): `scan.py` over live_play_2026102[5-8]_* (893 logs) -> `results/casts_clxiii.jsonl` (559 casts);
  `measure.py` -> `results/measure_clxiii.txt`; CLXIII: evo first answer in the real lane 30/50, plain 446/467.
- Cause (a): `tokens.py` (80/80 evo in-flight decisions: two card-42 tokens, identical but mirrored x);
  `inflight.py` (real barrel = lower generation key 50/50; same first/last frame 50/50).
- Fix: `pipeline/barrel_decoy.py` + `pipeline/tests/test_barrel_decoy.py` (4 tests);
  `wiring.diff` = the first plan; superseded by the flag wiring 464b32d (below).

- Checks (a): `mark_check.py` -> decoy_indices marks the landing-labelled decoy on 50/50 evo casts, 0/501 plain;
  `rule_replay.py` (rules only, model card/timing held fixed) -> real-lane first answers 30/50 -> 49/50 (Log 9 by
  log_barrel, troops 10 by barrel_lane; 1 Tesla left).

- Owner go 10-28 (via lead; creation order accepted as the colour-cue stand-in). Wiring 464b32d: --barrel-decoy
  off|on (default off). LIVE_OPTIONS NOT yet edited (deploy step, after the blind verifier's PASS).
- Model replay (step 1): pod 32657 /workspace/gbdecoy (cp -al of cb_mem + HEAD pipeline overlay + local catalog / cue
  table), 56 logs in replay_logs/ (replay/windows.json: 32 evo matches + 24 no-evo matches, 102 plain casts), out/ per
  log. Restart (resumable): `bash /workspace/gbdecoy/run_all.sh`. Summary: `python replay/analyze.py OUT windows.json`.
- LOOP-INT a9ec050f10f6a04be messaged the interface note (Java obs rename).

- Model replay DONE (a) (`results/model_replay.txt`, outputs `replay/out/`): fidelity replay-off == logged live
  19,904 / 20,132 decisions (play, card, cell); evo first answer in the real lane: logged 29/50, off 29/50, ON 43/50
  (answered 47); plain casts 231 (102 in no-evo matches): 1,572 / 1,572 decisions identical off vs on; all 163 off/on
  differences (99 p_play only, 64 decisions) lie inside evo windows, none elsewhere.

- Blind verifier PASS_WITH_NOTES (lead 10-28); fixes 809f3f0: F1 adjacent generation keys (`gen_adj.py`: 52/52 two-barrel
  casts gap 1, same first frame), F2 malformed rows never marked / never raise (one warning per match), F3 --check JSON
  barrel_decoy, F5 docs. Re-run (a): model replay r2 byte-identical to r1 on all 56 logs (`results/model_replay_r2.txt`);
  --check with the flag on: LIVE_CHECK_PASS, barrel_decoy true, reader merged_sf.

- DEPLOYED 10-28 11:45 EDT (owner go via lead; verifier PASS_WITH_NOTES + fixes): `--barrel-decoy on` appended to
  scratchpad/gauntlet/L70/live/LIVE_OPTIONS; backup scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_gbdecoy_20261028.
  Deploy --check: LIVE_CHECK_PASS, barrel_decoy true, merged_sf. First 3 matches (114527, 115053, 115543): start event
  barrel_decoy true, from_file on, merged_sf; normal stops; 0 tracebacks / decoy warnings in overnight.out since the start.
  Entry live_play.py (HAND_READER_ENABLED 0). Watch: `python .foreman/scratch/gb_decoy/newlogs.py 20261028_1144`.

## Post-deploy watch (LIVE-OPS, 10-28 13:50 EDT; 33 finished logs since 11:45, all started with barrel_decoy true)
- (a) measured: `postdeploy.py` (re-runnable, any day: `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/gb_decoy/postdeploy.py [STAMP]`)
  -> `post/results/{casts_post.jsonl,measure_post.txt,newlogs_post.txt}`. 33 finished logs, 15 opponent barrel casts: 14 plain, 1 evo.
  - evo (n = 1): live_play_20261028_130522 tick 3237, real lane L (landing labels BarrelGoblin x2 / GoblinDummy x3); the model's
    `model_projectiles` in all 3 in-flight decisions list ONE opponent card-42 barrel aimed at x = 0.194 (the real lane); the mirrored
    decoy (x = 0.806) is gone from the model input (pre-deploy: two card-42 tokens in 80/80 in-flight decisions). First answer
    Skeletons at tick 3237 (centre-left, in flight), then Log L (3261) and Knight L (3287): all in the real lane. 1 / 1 vs 30/50
    before; n = 1 proves nothing about the rate, it only shows the filter is live and the lane was right.
  - plain (n = 14): first answer in the real lane 13 / 13 answered (pre-deploy 446 / 467 = 95.5%); all answers 25 / 27 real lane.
    No change visible; the replay already showed 1,572 / 1,572 plain decisions identical off vs on.
  - base rate: evo casts are rare (50 in the 893 pre-deploy logs = 1 per 18 matches; 1 in the first 33 post-deploy). To tell
    30/50 (60%) from 43/50 (86%) needs ~30 evo casts = ~540 matches = ~2.5 days at 13 matches / hour; n = 10 (~20 h) only
    shows direction. Re-run the script daily; judge at n >= 30 evo casts.
  - errors: 0 tracebacks, 0 decoy warnings, 0 `err*` / `exc*` events in 33 logs (overnight.out since the 11:45 start: 0 "Traceback",
    1 "decoy" = the LIVE_OPTIONS applied line); the 12:15 nav stop is an adb transport failure, not the decoy (see
    liveops/STATUS.md); the run after it (12:16 restart) also logs barrel_decoy true.
  - win rate since the deploy 8 / 27 (29.6%, Wilson 95% [15.9, 48.5]) vs 32.7% [29.1, 36.5] over 629 matches since CLXIII returned: no drift
    (liveops/results/health_table.md).

## Next
- Watch evo-barrel casts live: `postdeploy.py` daily (it replaces the scan.py + measure.py + newlogs.py chain; note the old pattern
  `1[2-9]*` misses the 11:45-11:59 logs); judge at n >= 30 evo casts; compare plain first answers (446/467) and the play metrics.
- Rollback: `cp scratchpad/gauntlet/L70/live/LIVE_OPTIONS.pre_gbdecoy_20261028 scratchpad/gauntlet/L70/live/LIVE_OPTIONS`;
  `bash scratchpad/gauntlet/L70/live/stop_live.sh`; wait for '[sup] done' in supervisor.log;
  `bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --ranked`.
- Successor: `goblin-barrel-decoy` in the card vocab; Java obs rename (LOOP-INT notified).
- Post-landing: GoblinDummy bodies still read as `goblins`; barrel_lane abstains while they live.

## SIM side (LOOP-DECOY, 10-28 ~16:40 EDT): `barrel_decoy_sim: true` = the SIM shows what live's --barrel-decoy on shows
- Change: `pipeline/crforge_core.barrel_decoy_sim_objects` (CRFORGE_BARREL_DECOY_SIM=1, set by rl_royale `barrel_decoy_sim:
  true` via `barrel_decoy_sim_cfg`; absent = unset = today's spellObj) maps spells_evolved GoblinBarrel_EV1's Projectile
  GoblinBarrelSpell_EV1 -> GoblinBarrel FLIGHT. The decoy (GoblinBarrelSpell_EV1_Decoy, actions GoblinBarrel_EV1_CreateDecoy)
  stays unmapped = a crown-tower shot that projectile_observation.objects drops. No Java change: CfTrain copies the template
  core's spellObj, so the fast loop gets the same map. pilot.yaml sets the key.
- (a) probe `pilot/loop/decoy_probe.py` (33308, private tree /workspace/decoy/cb, fe364ceb + 16.635.3, B0 vocab), seeds 5-10:
  6 evo casts: key off 0/144 in-flight ticks with a barrel token; key on 144/144 ticks exactly one token, = the live relabel
  of the same board (reader rows, real first) 144/144; 22 plain casts identical off/on; entity rows identical on 1,056/1,056 ticks.
  Results: .foreman/scratch/a2/decoy/probe_s{5..10}.json.
- (a) compare.py lint_pn2 msg (32 matches, 8 with evo GB decks), GPU 1: key off 32/32 identical; key on 32/32 identical
  (lp max 1.4e-6 card / 2.3e-6 cell), 6/32 matches play differently from key off (both paths agree in each).
- (a) smokes (succ48_x_s101 --smoke): base tree (HEAD) and key-absent tree log the same u0000 batch_sha 1258dce43c686622;
  key on d0fdbde9f2ed131e (expected); u0001 base = off 6639f4986ccd0c49, on 2c2d81f70c225d5b; config sha base = off
  b5e2a2bbafef, on 5cefd49d1734; all 3 SMOKE PASS (resume check), 0 tracebacks. Laptop + pod tests: pipeline/tests/test_barrel_decoy_sim.py (5) + test_barrel_decoy.py.
- Known limit (b): a successor whose vocab adds DECOY_KEY sees the decoy live, not in the SIM (needs a name -> card for the
  decoy in sim_objects / royale_env.names: outside this ticket). Same gap, untested: Snowball_EV1 (projectile SnowballSpell_EV1)
  and Zap_EV1 (area) are spells_evolved rows spell_objects does not walk; GoblinDummy bodies' SIM card not checked.
- Eval / gate runs outside rl_royale (e1_eval, compare.py) must export CRFORGE_BARREL_DECOY_SIM=1 to use the same SIM.
- Restart: `33308: cd /workspace/decoy/cb; . /workspace/decoy/env.sh; python scratchpad/gauntlet/L74/plan1026/pilot/loop/
  decoy_probe.py --seed 5 --ckpt icebow/data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt --out /workspace/decoy/probe.json`;
  compare `DECOY=1 CPUS=236-247 GPU=1 bash /workspace/decoy/cmp.sh MSG OUT.json --in-flight 8 --matches 8 --threads 4`;
  smoke `CPUS=a-b bash /workspace/decoy/smoke.sh TREE RUN [barrel_decoy_sim=true]`.
- Codex: LOOP-DECOY_1 (medium) BLOCKED correctly (GPU 0 busy, not covered); LOOP-DECOY_2 (medium) DONE: smokes + compares on GPU 1 (.foreman/scratch/a2/decoy/codex2_result.md; checked here).
