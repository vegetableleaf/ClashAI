# VERIFY: ticket B (plan1026 Pillar 3 P1, one `decide()`)

Run from `C:\Users\benpe\ClashBot` in Git Bash. `PY=icebow/.venv/Scripts/python.exe`, `RP=research/ext/Royale/.venv/Scripts/python.exe`.
These are read-only checks. None of them starts, stops or touches the running live process.

1. Undefined names (expect nothing printed):
   `$RP -m pyflakes pipeline/decision_options.py pipeline/live_gen_v2.py pipeline/e1_eval.py scratchpad/gauntlet/L74/livecal/livecal.py pipeline/tests/test_decide_identity.py | grep "undefined name"`
2. Identity of every path against BASE `a76f57e` (the decision stack the live run imported). Takes about 15 min on CPU.
   It needs the 4 pinned live logs in `scratchpad/gauntlet/L68/live_reader/` and the CLXIII checkpoint, and it skips if they are missing.
   `$PY -m pytest -q -s -p no:cacheprovider pipeline/tests/test_decide_identity.py`
   - `test_live_recorded_decisions_identical_to_base`: recorded CLXIII matches run through BASE's and the new GenPilot.decide. Every decision dict, every tap (play, hand_pos, xy, follow_ups) and the decision-RNG state are identical.
   - `test_live_stress_rule_paths_identical_to_base`: the same frames with the gate logit +3, overtime and enemy princesses at 60 HP or less (lethal_rocket fires). Identical.
   - `test_sim_rows_identical_to_base`: SIM `decide_batch` (6 option sets, including the deployed one) gives the same decision on every row. The RNG state is identical on every row where no finisher fired. The rollout `sample_decide_batch` gives identical draws, log-probs, records and rng_behave states.
   - `test_one_live_row_through_decide_batch_gives_the_same_action`: a live row's `decide()` inputs, run through `decide_batch`, give the same play, slot and cell.
   - `test_sampled_decide_runs_the_finishers_and_marks_forced_rows`.
3. The stale IW test is fixed. adb taps and should_press calls are byte-identical to PRE. Events are compared on PRE's keys only.
   `$PY -m pytest -q -p no:cacheprovider scratchpad/gauntlet/L74/ability_live/test_ability_live.py -k identical_to_pre`
4. The SIM config is generated from LIVE_OPTIONS, and LIVECAL's worker refuses a command that differs from it:
   `cd scratchpad/gauntlet/L74/livecal && ../../../../$PY -m pytest -q -p no:cacheprovider . ; cd -`
   (`test_sim_decision_config_is_the_deployed_live_options_file`)
5. Regression suites of the decide stack. The expected failures are the 6 pre-existing ones listed below; they fail identically at BASE.
   `$PY -m pytest -q -p no:cacheprovider pipeline/tests/test_live_decision_options.py pipeline/tests/test_decision_options.py pipeline/tests/test_lethal_rocket.py pipeline/tests/test_lethal_log.py pipeline/tests/test_lethal_quiet_1025.py pipeline/tests/test_rocket_value2.py pipeline/tests/test_rocket_tornado_v2.py pipeline/tests/test_log_barrel.py pipeline/tests/test_log_air.py pipeline/tests/test_xbow_dead_lane.py pipeline/tests/test_rocket_dead_target.py pipeline/tests/test_gate_decode.py pipeline/tests/test_tau_threatened.py pipeline/tests/test_card_levels.py pipeline/tests/test_barrel_lane_1025.py pipeline/tests/test_posture_live.py pipeline/tests/test_e1_batch.py pipeline/tests/test_branching.py`
   Pre-existing failures at BASE: test_adaptive_opponents::test_spell_delay_lands_later_only_for_styled_opponent, test_live_options::test_checked_in_file_holds_the_deployed_options, test_live_options::test_checked_in_file_applies_every_bundle_option, test_r8_extrapolate::test_sim_prepare_and_live_decide_use_advanced_tokens, live_reader/test_live_entry::test_preflight_loads_default_without_adb, live_reader/test_live_entry::test_manual_run_records_locally_and_explicit_wins.
   Royale venv (`$RP`): 21 failures, every one also failing at BASE (list: `git stash`-run in the ticket report); mostly test_live_options / test_search_s0 needing cv2 / live_play.
6. The live wiring check loads the deployed model offline and has no ADB or emulator side effects:
   `bash scratchpad/gauntlet/L70/live/start_live.sh icebow --no-fast-plays --check` (expect `PASS`)
7. Trainer smoke (memory: trainer-edit-preship-check), ~5 min CPU:
   `$RP -m pipeline.rl_royale --run smoke_ticketB_verify --smoke advantage=gae critic_warmup_updates=1 actor_device=cpu learner_device=cpu` (expect `SMOKE PASS`)
8. Single trunk pass in live (coordinator request, S1 SPEED.md a1). `GenPilot._policy_forward` computes the policy heads and every cell head of a decision from ONE `encode_gen`; BASE ran the whole model again for each cell head. Step 2's live identity covers this: the dicts are bit-identical, so the cell logits are identical. Measured on CPU with 1 thread, log 20261027_033228, 442 decisions: BASE p50 82.8 / p90 103.6 ms, new p50 42.8 / p90 60.8 ms.
