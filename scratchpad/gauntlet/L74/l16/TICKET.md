# Codex ticket L16 (lead Claude, 10-19 evening). Owner: put the 4 idle pods to work now; Codex sets them up.
Repo C:/Users/benpe/ClashBot. Pods (ssh -i ~/.ssh/runpod_clashbot): 13396 = root@64.247.206.76 -p 13396,
14009 = root@64.247.206.76 -p 14009, 15617 = root@216.81.151.5 -p 15617, 19899 = root@64.247.206.76 -p 19899.
Read first: scratchpad/gauntlet/L74/stepd/STATUS.md (top entries), overnight1018/LOG.md, stepd/{stepd_chain.sh,arm_waiter.sh,ship_stepd.sh}.

Owner ruling 10-19: model EVERY card AND tower at level 16 on BOTH sides (ladder 13k ~ 15-16; Ranked = all 16).
Facts: training already uses `live_levels: true` (measured table, L74/levels/live_levels.json). gap.py evals pass NO levels,
so they run at the engine default, level 11.

AUTHORITY: fix MECHANICAL problems yourself: paths, quoting, missing helper scripts on a pod, env vars, re-running a failed copy.
STOP and write to l16/STATUS.md only on a DESIGN question (anything not specified here) or a failing test or smoke you cannot fix
mechanically. Keep l16/STATUS.md updated with timestamps.

## 1. Code (laptop; small and opt-in; absent = byte-identical behaviour)
a. pipeline/rl_royale.py: `live_levels` also accepts the string "all16".
   - It returns the synthetic table {"own": {"cards": {}, "default": 16, "tower": 16}, "opp_profiles": [[None, 16, [16]]]}.
   - draw_live_levels then gives every card 16 (clamped by card_level) and both towers 16.
   - Use that table wherever _live_level_table() is used for the match levels (around line 1683).
   - config hash (around lines 3011-3014): for "all16" keep the string itself in the hashed cfg (not the file sha).
   - true / false / null behave exactly as before.
b. scratchpad/gauntlet/L74/gap/gap.py: add `--levels {none,all16}` (default none = unchanged).
   - With all16, every evaluated match spec gets spec["levels"] in the draw_live_levels format, all 16.
   - Use rl_royale.draw_live_levels with the all16 table, so card ranges are clamped the same way.
   - e1_eval already applies spec["levels"] (around e1_eval.py:1927).
c. stepd/stepd_chain.sh: an optional env EVAL_LEVELS (from the GO file). When set, pass `--levels $EVAL_LEVELS` to every gap.py
   call. Unset = unchanged.
d. Checks:
   - pyflakes undefined names empty on the changed .py files;
   - existing tests pass: pipeline/tests/test_rl_royale.py, test_rl_gae.py, test_cue_inputs.py, and the gap tests if any;
   - add a small test: "all16" table -> draw_live_levels gives 16s; config hash differs from true; absent unchanged;
   - a REAL `python -m pipeline.rl_royale --smoke` with live_levels=all16 on a POD (laptop is shared), printing SMOKE PASS.
   Commit the explicit paths, push.

## 2. Pods (ship the committed code exactly as ship_stepd.sh / the earlier arms did; reuse each pod's existing tree where present)
- 13396: arm stepd_l16_s74 = stepd/cfg/stepd_ctrl_nos2.yaml with ONLY `live_levels: all16` and seed 74.
  GO: EVAL_LEVELS=all16, DECODE as the CLX arm's GO.
- 14009: arm stepd_l16_s75 = the same with seed 75. GO adds NO36=1 (as before on this pod).
- 15617: REF chain (eval only) NAME=clx_l16 = ICEBOW Mark CLX (rlarm_stepd_ctrl_nos2_u0130_grafted.pt) with EVAL_LEVELS=all16,
  fin13 std + fresh, the same decode as the CLX chain. Stage the pod with ship_stepd.sh as 10757 was staged (STATUS 14:10 / 15:05).
- 19899: REF chain NAME=cliii_l16 = ICEBOW Mark CLIII with EVAL_LEVELS=all16, fin13 std + fresh.
- Verify for each: SMOKE PASS (arms) or the first eval rows (REF). Record PIDs + yaml sha in l16/STATUS.md.
- Never stop any pod. No live changes, no deploys.

## 3. Report
Append to l16/STATUS.md:
- the code commit;
- the per-pod launch state;
- ETAs (training ~5.5 h + evals).
Exit after all four pods are verified running.
Rules:
- no `git add -A` (explicit paths; check the staged count);
- never print keys / webhook / reader internals;
- no `python -` with stdin;
- kill only by exact PID.
