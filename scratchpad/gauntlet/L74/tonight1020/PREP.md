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
