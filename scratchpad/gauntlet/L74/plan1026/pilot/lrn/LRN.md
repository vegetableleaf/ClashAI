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
- DONE (a) LOOP-LRN identity (rec_identity.py --reuse, 33920 4090, deterministic CUDA, TF32 default as rl_royale):
  rl_royale.Learner (rollout = the captured results) vs LoopLearner (the spool) on the same 512 records. Weights, ability
  head, both Adam states and the update record (wall clocks dropped) are BIT-IDENTICAL: update 1 (critic warm-up) model
  85c759a8, opt adc50026; update 5 (policy) model 53c71d81, ability head f5deb180, opt 9cc4e8e2. Log
  /workspace/lrn/logs/id1gpu.log; /workspace/lrn/id1/result.json.
- (a) kl_stop_prev 0.02 is BINDING: the first policy update stopped at epoch 0 minibatch 145 of 622 (KL 0.0201), i.e.
  145 of 1,244 steps.
- (a) Update time on the 4090, 159k rows: warm-up 209 s (ref_terms 39 + gae/vf-share 37 + PPO 132 s, 106 ms/step);
  policy update 106 s (ref 40 + gae 39 + PPO 25 s for 145 steps, 177 ms/step).
- (a) step_probe.py: the step is compute-bound per row, NOT overhead-bound (contradicts "102 ms is overhead"):
  no-grad forward 133 ms / 512 rows vs 1,019 ms / 4,096 rows (linear); policy step 204 ms / 256 rows (1,253 rows/s) vs
  94 ms / 64 rows. A 256-row step peaks at 11.3 GB, and minibatches of 2,048-16,384 rows OOM on 24 GB. gen_batch (CPU
  memory features) is 32-42 ms of each 512-row forward.
- (a) TF32 off costs the learner nothing measurable: step 204 -> 184 ms, forward 133 -> 102 ms (sequential runs).
  rl_royale now sets cudnn + matmul allow_tf32 False under learner_deterministic. CPU smoke with
  learner_deterministic=true: crforge e816a6a4 / f060b678, SMOKE PASS (/workspace/lrn/logs/lrn_smoke_det.log).
- DONE (a) (ii) shared no-grad pass (lead-approved): with kl_ref_refresh_every 1 (and no gate_ref / card_ref /
  F6' / critic_ctx / cf), ref_terms(value=True) returns V(s), and value_rows reuses it (B["v_shared"]). share_gate.py,
  update 5 on the 512 records with TF32 off: weights, ability head, both Adam states and the update record are
  BIT-IDENTICAL to the two-pass code (model da447cc0, opt cfbefd6a). Update 115.6 -> 67.6 s (gae + vf-share 38.6 -> 0.7 s).
  Log: /workspace/lrn/logs/share_gate.log.
- (b, from code) the pilot pays a THIRD full pass per update: with kl_ref_refresh_every 1, self.ref stops being
  ref_init after u0, so one_update reruns ref_terms(ref_init) for the entropy-floor baseline (~40 s per update). My
  gates start fresh learners, so this pass is not in their timings. It only feeds a guard; a row subsample would do.
- (i) cell_refine / tower_refine on played rows only: EXACT in math. cell_feat and tower_cell_feat
  (model_gen.encode_gen) are read only by cell_logits_gen, which policy_terms calls only on the played rows (enc sliced
  by pi). No batch-wide normalisation reads them. Bit identity depends on batch-size-dependent conv kernels (b). Not built.
- (iv) evaluation (b, from the measured per-row costs on the 4090: no-grad forward ~0.2-0.26 ms/row, fwd+bwd step
  ~0.72-0.8 ms/row; 512 matches = 159k rows; kl_stop_prev binds after ~145 steps = 37k rows):
    today (refresh 1, 3 passes)   ~3 x 37 s + 27 s = ~140 s per 512 matches -> ~13k matches/h per 4090
    + (ii)                        ~2 x 37 s + 27 s = ~100 s                  -> ~18k matches/h
    + (i) (forwards ~2x, SPEED.md) ~2 x 19 s + 14 s = ~52 s                  -> ~35k matches/h
    (iv) stored lp_old + v_old    0 full passes; KL to update-start needs a ref forward on the 145 x 256 minibatch rows
                                  only (~4-8 s) + PPO 14-27 s = ~20-35 s, NEARLY INDEPENDENT of matches per update while
                                  kl_stop binds -> 512 matches/update: 50-90k/h; 2,048/update: 210-370k/h on ONE 4090
  DDP (2-4 GPUs) speeds only the PPO steps: 4-way at minibatch 256 = 64 rows/GPU, 94 vs 204 ms -> <= 2.2x (b). An RTX
  PRO 6000 at ~1.7x (b) and 96 GB: larger minibatches do not help, because the step is linear in rows (measured).
  So (iv) + more matches per update reaches 300k/h; (i) + (ii) + DDP alone does not.
  LOOP-SRV (b03c70a, measured): the server does not return value today (cheap to add: one 128->7 Linear on its kept g,
  28 B/row); value parity server vs CPU fp32 = 4.9e-7 max, lp 7.6e-6. Caveat: critic_ctx would need CtxHead in the push.
- crforge smoke with the shared-pass code (refresh 50 there, so off): e816a6a4 / f060b678 SMOKE PASS.
  Required with (iv): the server stores v (value_scalar of the same forward's value logits) per row; asked LOOP-SRV.
  The ratio stays PPO's behaviour ratio exp(lp_new - lp_old) (what rl_royale already does). The KL stop stays
  "to update-start" on the sampled minibatch rows. Stored-vs-recomputed effect on one update's record: NOT measured yet.
  lp parity is measured (server 7.6e-6); value parity is not.
- NOT DONE (proposed next tickets): (1) rows-per-forward cost: compute cell_refine / tower_refine only on played rows
  (SPEED.md estimates about 2x), and with kl_ref_refresh_every 1 the ref pass equals the value pass on the same weights
  (one no-grad pass saved, ~40 s per update); (2) DDP: from the 64-row step (94 ms), 4-way DDP at minibatch 256 gives
  at most 204 / 94 = 2.2x, compute only (b); (3) the minibatch / lr sweep needs gradient accumulation (2,048 rows does
  not fit) plus a short real run for the dynamics; (4) a loop_learner process smoke (`python -m pipeline.loop_learner`,
  max_updates 2 on /workspace/lrn/id1/keep).

## Pod 33920 layout (restartable)
- Code tree /workspace/lrn/cb = git HEAD (pipeline, tools, scratchpad/gauntlet/L74) + my files, with read-only symlinks into
  /workspace/cb_mem for everything else (links.sh). icebow/data = symlinks to cb_mem data, except
  bench/rl_royale/b0 (B0 984bf572) and the run outputs.
- venv /workspace/venvf16 (setup_fin16.sh, FIN16_OK). jpype + crforge jars come from 33308 d2/stage (/workspace/lrn/d2/stage),
  and the facade build from d2t/buildH (/workspace/lrn/buildH, CfCore.java c003fc74 = HEAD).
- env: `source /workspace/lrn/cb/scratchpad/gauntlet/L74/plan1026/pilot/lrn/env.sh`. Smoke: `bash .../smoke.sh crforge RUN`.
  Logs go to /workspace/lrn/logs.
