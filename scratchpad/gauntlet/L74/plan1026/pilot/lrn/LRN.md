# LOOP-LRN (+ LOOP-REC): trajectory record, standalone PPO learner, tower_phat Phi, kl_stop_prev

Labels: (a) measured, (b) untested, (c) contradicted. Spec: ../LOOP_SPEC.md.

## STATUS (keep current)
- DONE (a): `kl_stop_prev` in pipeline/rl_royale.py (opt-in, lead-approved 10-28). Unit test pipeline/tests/test_kl_stop_prev.py
  3/3: the stop fires at the first minibatch over the limit and never otherwise; off and never-firing give byte-identical
  params. The off path equals HEAD's rl_royale (tiny-model update, weights sha e7dc8fd8 both; scratch off_vs_head.py).
- DONE (a): `shaping: tower_phat` in pipeline/reward_shaping.py. Fit: fit_phi.py on hfE.npz (33308 /workspace/rx23);
  result in phi_fit.json; held-out AUC .662/.812/.915, ECE .016/.012/.011 at 60/120/180 s. Unit test
  pipeline/tests/test_shaping_tower_phat.py 5/5 (telescoping through rl_royale.shaping_rewards: sum F = -Phi(0), and the
  discounted return-to-go = -Phi(s_t) with per-row gamma_tick).
- DONE (a): production is unchanged with the new code off. smoke.sh on 33920 (HEAD + only my rl_royale hunks, venvf16
  fin16-linux, CPU learner), succ48_x_s101, config sha b5e2a2bbafef (= D2-T's): crforge u0000 e816a6a499f7c706,
  u0001 f060b678c497bfe6; royalesim (fin16) u0000 d4ef5467f45f2f06, u0001 6cd7292f29717638; SMOKE PASS on both
  (logs /workspace/lrn/logs/lrn_smoke_{crforge,royalesim}.log).
- DONE (a) LOOP-REC: pipeline/loop_records.py (the format is in its docstring). rec_identity.py --capture-only on 33920:
  rl_royale's own rollout(0) on crforge, pilot.yaml (B0, tower_phat rows, n_actors 40), 512 matches in 309 s,
  159,499 kept rows. collate of the originals vs collate of the decoded record files is byte-identical (batch sha
  814d631ce437a1b8, 56 keys), and so are the collate stats, rollout_monitors and league_monitors. Mean record size is
  4.95 MB. Records: /workspace/lrn/id1/keep; result: /workspace/lrn/id1/result_rec.json.
- DONE (a) timing, update 0 (critic warm-up), 512 matches / 159,499 rows / 1,248 steps on the 4090, deterministic:
  204 s = ref_terms 38.7 + gae/vf-share 37.4 + PPO 127.7 s (102 ms/step). A 512-match batch arrives every 6.1 s at
  300k/h, so one GPU is ~33x too slow. Lead 10-28: sweep the minibatch (2048-16384, lr x sqrt(mb/256)), vectorise
  ref_terms / gae, DDP up to 4 GPUs, more matches per update allowed; record any PPO-setting change in pilot.yaml's header.
- DONE (a) on-policy gap: rl_royale's u0 assert fails on B0 with a CUDA learner (lp_cell 5.8e-4 > 1e-4). Cause:
  cuDNN TF32 convolutions (torch default cudnn.allow_tf32 True). Max |recompute - stored|, 16 records (lp_numerics.py):
  CPU cell 1.2e-5; CUDA default 1.46e-3; CUDA with cudnn + matmul allow_tf32 False 1.5e-5. The fix is one flag in the
  learner AND the server (proposed to the lead).
- Second capture with B0's ability head adopted in the actors (id1, 159,070 rows): LOOP-REC PASS again (1bea99d7).
- RUNNING (33920 GPU): rec_identity.py --reuse (learner identity, update 0 + policy update 5, RL_PROFILE timings)
  -> /workspace/lrn/logs/id1.log, /workspace/lrn/id1/result.json. Restart: `bash /workspace/lrn/run_id.sh --reuse`.
- NEXT: step_probe.py (step time vs minibatch size, for the DDP projection); a loop_learner process smoke (max_updates 2
  on the kept records); then the DDP decision.

## Pod 33920 layout (restartable)
- Code tree /workspace/lrn/cb = git HEAD (pipeline, tools, scratchpad/gauntlet/L74) + my files, with read-only symlinks into
  /workspace/cb_mem for everything else (links.sh). icebow/data = symlinks to cb_mem data, except
  bench/rl_royale/b0 (B0 984bf572) and the run outputs.
- venv /workspace/venvf16 (setup_fin16.sh, FIN16_OK). jpype + crforge jars come from 33308 d2/stage (/workspace/lrn/d2/stage),
  and the facade build from d2t/buildH (/workspace/lrn/buildH, CfCore.java c003fc74 = HEAD).
- env: `source /workspace/lrn/cb/scratchpad/gauntlet/L74/plan1026/pilot/lrn/env.sh`. Smoke: `bash .../smoke.sh crforge RUN`.
  Logs go to /workspace/lrn/logs.
