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

## Next
- After PASS: append `--barrel-decoy on` to scratchpad/gauntlet/L70/live/LIVE_OPTIONS; start_live.sh icebow
  --no-fast-plays --ranked --check; stop_live.sh (wait 'done'); no live_play.py left; start_live.sh icebow
  --no-fast-plays --ranked; start event barrel_decoy true + reader merged_sf. Rollback: remove the line, same restart.
- Model-level replay of the 50 evo windows (baseline vs barrel_decoy.objects) through the real GenPilot, as
  `scratchpad/gauntlet/L74/speed/live_profile.py` does; run on a pod (not the live laptop). Not started.
- Successor: add `goblin-barrel-decoy` to the card vocab; crforge Java obs (CfPubObj) must rename the decoy.
- Post-landing: GoblinDummy bodies map to `goblins` (vocab._SPELL_BODY; the "81-hp body" = GoblinDummy 32 x 2.56 at
  L11); barrel_lane abstains while they live. Not changed.
