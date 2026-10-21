# W11 PREP: four pods for tonight's successor arms (2026-10-20, ~20:40-20:55 UTC). Nothing was launched.

Code = git HEAD 88cd3573d5e96f54ea3fad831094f2e13469c36b (committed tree only, `git archive` per stepd/w6_arm.sh header;
2841 files, per-file manifest in /workspace/in/code.sha on each pod), shipped with
stepd/ship_stepd.sh HOST PORT into /workspace/cb_stepd. All four pods were idle first (no rl_royale / gap.py / stepd_chain
process, /workspace/stepd/claim.lock free by `flock -n`).

| pod | yaml | CODE_OK | FIN15_OK | w7opp.pt sha256 (full, = ea1d080496b3...) | ckpts/data (11 files) | smoke | disk free |
|---|---|---|---|---|---|---|---|
| 13396 (64.247.206.76) | tn_base_s74 | yes | yes (venvf36 intact) | ea1d080496b3413cf15d31ac149567024e8c727d7241ae5289f665736a087909 | present, sha identical | SMOKE PASS | 36 GB |
| 14009 (64.247.206.76) | tn_base_s75 | yes | yes (see note) | same | present, sha identical | SMOKE PASS | 25 GB |
| 19899 (64.247.206.76) | tn_lead_s74 | yes | yes (venvf36 intact) | same | present, sha identical | SMOKE PASS | 11 GB (>= 10, tight) |
| 40548 (64.247.206.80) | tn_rocket_s74 | yes | yes (re-run; venvf15 existed from W8) | same | present, sha identical | SMOKE PASS | 14 GB |

- fin15 install: setup_fin15.sh with FIN15_SHA=88f3fdcb... FIN15_PIN=305aaafc..., CB=/workspace/cb_stepd -> `fin15-linux` pins
  RoyaleSim 305aaafceb7b28bf5108c9fe028fafae97d32676, RoyaleGym a7deb6e4..., embedded cards table, `SMOKE_FIN15_OK`, then
  /workspace/stepd/fin15/FIN15_OK. The wheel was copied from the laptop (sha 88f3fdcb... verified by the script on each pod).
- Note 14009: it has no /workspace/venvf36 (only venvf13, a real 6.6 GB dir, same royalegym 0.1.23 / torch 2.11.0+cu128 / numpy
  2.5.4). venvf15 was built with `SRCV=/workspace/venvf13 SKIP36=1`; venvf13 still activates under fin13-linux (pin a697d1f9...).
  Any 14009 launcher that needs fork36 evals (stepd_chain.sh P36) has no venvf36 there.
- Checkpoints/data: tn_*.yaml reference init rlarm_succ_levels_u0065.pt (05d42da7...), s1_icebow_v6aug_s1.pt (287dda04...),
  gen_dataset_v32_fv5.npz (29ecefa9...), s1_dataset.npz (43401900...), pool_env_v1.jsonl (c37cb7bd...), decks_rl.json (b43dd085...),
  wk_adapt_exp1/2/3 u0015 (3e019ae9 / efe5e3f6 / ead818a8), newsim_base_exp1/2 u0015 (d0ef0ea3 / 24cbbe3f). The 11-file sha
  list is byte-identical on all four pods; the 4 files that exist on the laptop match it. No CLX/CLIII checkpoint is referenced
  by the tn_* yamls.
- w7opp.pt came from C:/Users/benpe/pod_backup_weekend/w7/rlarm_oppC1_icemix_s74_u0100.pt (read-only), at
  icebow/data/pipeline/o2/w7opp.pt in /workspace/cb_stepd; full sha verified on each pod.
- Smoke: `tonight1020/pod_smoke15.sh` (= l16/pod_smoke.sh with python /workspace/venvf15/bin/python and
  ROYALE_RUNTIME=fin15-linux; l16/pod_smoke.sh itself hardcodes venvf13/fin13 and was not edited), run as
  `RUN=<tn_*> bash /workspace/pod_smoke15.sh`. It runs the real `pipeline.rl_royale --smoke critic_warmup_updates=1`. Logs on each
  pod: /workspace/stepd/tn_smoke_<arm>/smoke.log (+ status.log, SMOKE_OK).
- W7 opponent played: the smoke log's league line carries `exploiter_league` = the league_exploiters draw (w7opp.pt):
  13396 0.75/4 games at u0000, 19899 0.75/4, 40548 0.75/4, 14009 0.00/2 (so 4 / 4 / 4 / 2 games, all > 0).
  (13396/19899/40548 print the same numbers: same seed 74 and same recipe except the one key, which the 1-update smoke does
  not move; 14009 is seed 75.)
- The stepd chain also reads `/workspace/stepd/smoke/SMOKE_OK` (stepd_chain.sh); it exists on all four pods (older) and
  was not touched. The tn arms need GO files with RT=fin15-linux VENV=/workspace/venvf15 (the launcher's job).
- Not done / not touched: no training chain, no GO file, no pod stop, pods 48148 and 15617 not touched.

## Addendum: pod 15617 (216.81.151.5, tn_tornado_s74), 22:05-22:17 UTC

- Idle first (no rl_royale / gap.py / stepd_chain, claim.lock free). Code = git HEAD b74ef20 (includes tn_tornado_s74.yaml with
  tornado_king_w 0.1); CODE_OK. NOTE: the four pods above hold the earlier HEAD 88cd357; only this pod has b74ef20.
- fin15: FIN15_OK (no venvf36 on this pod either: venvf15 built from venvf13 with SRCV=/workspace/venvf13 SKIP36=1).
- w7opp.pt full sha256 ea1d080496b3413cf15d31ac149567024e8c727d7241ae5289f665736a087909. The 11 ckpt/data shas are
  identical to 40548's list.
- Smoke (pod_smoke15.sh, RT fin15-linux): SMOKE PASS 22:17:08Z, log /workspace/stepd/tn_smoke_tn_tornado_s74/smoke.log;
  exploiter_league 0.75/4 games (> 0, the W7 opponent played).
- DISK: 5.6 GB free (target was >= 12 GB; the stop-and-report floor is 10 GB). NOT cleaned: I do not permanently delete data,
  even backed-up trees. Candidates for the lead/owner to delete by hand: /workspace/w_v7_r7c_ht (5.5 GB) alone gives ~11 GB;
  with w_r7c (582 MB) / w_r5d (570 MB) ~12 GB. I did not verify their backups. READY except for the disk target.

## Addendum 2: pod 48148 (64.247.206.80 -p 48148, tn_redirect_s74), 22:20-22:39 UTC -- PREPARED AND LAUNCHED (lead-authorised)

- Idle first (no rl_royale / gap.py / stepd_chain, claim.lock free); disk 23 GB free (>= 10).
- Code = git HEAD 4ec11f2 (the W7 FINAL commit), CODE_OK. W7's files were protected: ship_stepd.sh would `rm -rf` the code dirs
  (incl. scratchpad/gauntlet/L74, where W7's uncommitted work may live), so the tar was extracted OVER the tree with no rm
  (GNU tar unlinks before writing, so hard links to cb_tt are not written through); nothing was deleted.
- fin15: FIN15_OK (venvf36 present; "venvf36 intact"). Checkpoint/data shas identical to 40548's list.
- w7opp.pt = R6 u20, sha256 3452256458450fcc8fc4848445e5c06c64970ad0b1b8a60c1a915208509c475b (verified before and after the
  launch script's identical-byte cp; w7opp_R4u100.pt and gen_live_b.pt untouched next to it).
- Smoke tn_redirect_s74 (pod_smoke15.sh): SMOKE PASS 22:38:15Z; exploiter_league 0.50/4 games (> 0).
- LAUNCHED 22:38:59Z with the lead's launch.sh: /workspace/stepd/GO_tn_redirect_s74 = RT=fin15-linux VENV=/workspace/venvf15
  EVAL_LEVELS=all16 DECODE='--ability-head-decode=sample --crown-log' NO36=1; chain pid 21909 under claim.lock; log
  /workspace/stepd/rl_tn_redirect_s74/chain.log.

## Addendum 3 (W17, 2026-10-21 21:00-22:10 UTC): four NEW empty pods prepared for tn_* arms -- nothing launched

| pod | GPU / cgroup CPU quota / disk | smoke tn_otstart_s74 | smoke tn_base_s74 | free disk after |
|---|---|---|---|---|
| 157.157.221.29:32621 | RTX 4090 / 54.4 / 200 GB | SMOKE PASS 21:41:26Z | SMOKE PASS 21:54:53Z | 185 GB |
| 64.247.206.120:22539 | L40 / 27.2 / 60 GB | SMOKE PASS 21:37:43Z | SMOKE PASS 21:48:40Z | 45 GB |
| 157.157.221.29:32525 | RTX 4090 / 54.4 / 60 GB (lead: two arms at once) | SMOKE PASS 21:39:34Z | SMOKE PASS 21:51:34Z | 45 GB |
| 213.192.2.125:40144 | RTX 4090 / 31.1 / 60 GB | SMOKE PASS 21:38:35Z | SMOKE PASS 21:49:38Z | 45 GB |

Same layout as 13396/14009 (which were only read):

- **Code.** /workspace/cb_stepd = `git archive origin/main` at **c8aa969** (includes W16's remote_actors.py, ot_start_share and
  league_deck_weights in rl_royale.py). L67, video-analytics and */templates are left out (not read by the trainer or the eval).
  It has 7,884 files; every one was checked with `sha256sum -c` against the laptop's extract (/workspace/in/code.sha).
- **Venv.**
  - /workspace/venvbase was rebuilt with uv from 13396's venvf15 freeze, with royalesim left out. The freeze is the same
    52 pins (torch 2.11.0+cu128, numpy 2.5.4, royalegym 0.1.23 from PyPI, ...); the diff is empty.
  - /workspace/venvf15 is a hard-link copy of venvbase made by setup_fin15.sh with `SRCV=/workspace/venvbase SKIP36=1`
    (no venvf36 or fork36: the GO file's NO36=1). The fin15 wheel's sha256 is 88f3fdcb... (FIN15_SHA), and the fork pin is
    305aaafc. The result is FIN15_OK.
  - `activate()` checks royalegym's bytes against the manifest: they pass, with pins RoyaleSim 305aaafc and RoyaleGym
    a7deb6e4. `import royalesim, royalegym, torch` works and CUDA is available.
- **Data.** 25 files were copied from 13396's cb_stepd through the laptop to 22539, then fanned out from 22539 to the other
  three with a temporary key, which was removed afterwards. sha256 equals 13396 on all files and 14009 on the shared ones
  (14009 holds the same files plus some extras).
  - init rlarm_succ_levels_u0065 05d42da7 (+ grafted edc82ada);
  - the s1 specialist 287dda04; s1_dataset 43401900; gen_dataset_v32_fv5.npz 29ecefa9;
  - pool_env_v1 c37cb7bd; decks_rl b43dd085;
  - wk_adapt_exp1/2/3 u0015 3e019ae9 / efe5e3f6 / ead818a8; newsim_base_exp1/2 u0015 d0ef0ea3 / 24cbbe3f;
  - **o2/w7opp.pt = R6 u20 3452256458450fcc8fc4848445e5c06c64970ad0b1b8a60c1a915208509c475b** (w7opp_R4u100.pt ea1d0804 next
    to it, as on 13396);
  - for the eval and graft: rlarm_gae_u0250_grafted 00c845c0 (stepd_chain U250), gen_v1_s0/gen_s0.pt 05db85a0 (livecal GEN)
    and rdef_e4_u0020_barrel2k_cellref_towerref_w2 430faaee (the E4 opponent);
  - also gen_v32_s0/*, card_ids.json and pool_env_v1_split.json.
  - /workspace/w7opp_R6u20.pt, /workspace/launch.sh and /workspace/pod_smoke15.sh are byte-equal to 13396's.
- **Also needed: research/ext** (38 files, 17 MB, byte-equal on 13396 and 14009). The first smoke CRASHED without it:
  decision_options reads research/ext/Royale/RoyaleSim/data/derived/cards.json for the all16 level table. Copied and verified.
- **Smokes.** `RUN=<arm> bash /workspace/pod_smoke15.sh` as above. Logs: /workspace/stepd/tn_smoke_<arm>/smoke.log.
  - After both smokes passed, /workspace/stepd/smoke/SMOKE_OK was written (stepd_chain.sh needs it).
  - The crashed first attempts were moved to /workspace/failed_smoke1/.
- **Eval / graft dependency check (22539).**
  - The chain's own ev() command ran gap.py D3 on u250 grafted (fin15-linux, `--levels all16`, the GO DECODE + EV_EXTRA,
    decks_live_eval census, 26 workers). It wrote 15 match rows in 30 s with no traceback; it was stopped on purpose.
  - graft_generic.py grafted a probe checkpoint (fv 6) with u250: 42 tensors.
  - Output: /workspace/gaptest.
- **Not done.** No GO file, no chain, nothing launched. The transfer tars (/workspace/in/{code,data,ext}.tar, ~1 GB) were kept.
  Two arms on ONE pod: stepd_chain.sh trains AND evaluates under `flock /workspace/cpu.lock` (launch.sh also holds
  claim.lock), so a second arm on 32525 waits for the first unless its launcher uses other locks. Disk is not the limit: one
  finished arm on 13396 uses ~0.65 GB (bench 517 MB + stepd 117 MB + L68 11 MB).

**Speed (a): seconds per PPO update.** W16's S1 probe (distrib/run_learner.sh flags: tn_base_s74, n_actors 24, E 64 x G 4,
max_updates 3, screens and proagree off, critic_warmup 0, RL_PROFILE=1) on fin15-linux. Log: /workspace/stepd/probe_speed.log.

| pod | rollout s u0/u1/u2 | learner s | roll + learn s/update (mean of 3) | ppo ms/step |
|---|---|---|---|---|
| 14009 (W16 S1, **fin13**, L40) | 117 / 140 / 132 | 41 / 43 / 41 | 158 / 183 / 173 = **171** (W16 wall total 176) | 57 |
| 22539 (L40, quota 27.2) | 127 / 143 / 173 | 42 / 44 / 45 | 169 / 187 / 218 = **191** | 58-63 |
| 32621 (4090, quota 54.4) | 151 / 162 / 153 | 40 / 40 / 40 | 191 / 202 / 193 = **195** | 56.5-57 |
| 32525 (4090, quota 54.4) | 144 / 144 / 148 | 40 / 41 / 40 | 184 / 185 / 188 = **186** | 56.5-57 |
| 40144 (4090, quota 31.1) | 132 / 156 / 132 | 38 / 39 / 39 | 170 / 195 / 171 = **179** | 53-54 |

- Production (fin15, screens every 10, proagree every 5): the median wall time between updates over 130 updates is 199 / 204 s
  on 13396 (tn_base_s74 / s76) and 197 / 201 s on 14009 (s75 / s77).
- Reading: the 4090 learner equals the L40's (38-41 s). The new pods' rollouts are 0-25 % slower than 14009's, with n = 3
  updates each, so this is noisy. The runtime also differs (fin15 here, fin13 in S1), and that effect was not measured.
  - Expect about 180-195 s per update without screens, so roughly 205-225 s in production (b).
  - The CPU quota is not the limit at 24 actors: 40144 (31 cores) is the fastest.
- u0 is identical on all four pods (154/102, 71,212 rows). batch_sha differs, as W16 found: the log-prob float bits.
- **Code refresh, 22:20Z.** origin/main had moved to 93c68de: 16 files, no pipeline/ change, only yamls and L74 analysis
  (tn_otstart_s75/s76, tn_bait_s74-76, tn_w14_s74-76). They were overlaid on all four pods and pass `sha256sum -c`; the
  tn_base_s74 and tn_otstart_s74 yamls did not change, so the smokes still hold.
  - **tn_w14_*** needs icebow/data/pipeline/o2/w14opp.pt (W14 B u20, 40275759). It is **NOT on these pods**: install it the way
    launch.sh installs w7opp.
  - tn_bait_* uses league_deck_weights, which is in the code. It was not smoked here.
