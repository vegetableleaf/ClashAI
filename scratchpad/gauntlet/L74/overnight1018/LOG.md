# Overnight 10-18 -> 10-19 orchestrator log (times EDT)

- 19:25 survey: 6 step-d arms training (13396 ctrl, 19834 reb, 14009 rebc3, 30988 ctrl_s75, 34210 ctrl_nos2, 10757 reb_s75);
  15617 / 19899 (KEEP, parity) idle since 12:43 / 14:53; 19400 idle since 14:04; 38758 already stopped (connection refused).
  Executor + round-7 closer finished earlier; doctrine worker running (laptop).
- 19:44 19400: stepd_rebc3_s75 (twin seed 75) started; same code tar as the twin (7150edc0), smoke PASS.
- 19:48 twin (14009) HARD guard stop at u50: gate_bal 0.7215 < 0.7737 - 0.05. 20:00 resumed at u50 with hard_gate_bal 0.08
  (diagnosis in stepd/STATUS.md: the CLIII card anchor pulls gate to CLIII level 0.732). 19400 yaml same edit.
- 00:16 stepd_ctrl_nos2 packed + pulled (sha 251c85b2). readout: std 674/960, fresh 686/960 vs CLIII 633 / 619:
  std +4.27 [+0.73, +7.92], fresh +6.98 [+3.54, +10.31], pooled +5.62 [+3.12, +8.12]; fork36 std +4.79 [+1.35, +8.23];
  u65 std -0.10 [-3.75, +3.54]. Same code (pipeline+gap hash a44649dc), same fin13 binary (2ec5ec39), same eval flags
  except the head decode (sample; CLIII has no head). -> BAR PASS.
- 00:19 PROMOTED: ICEBOW Mark CLX: PARITY (rlarm_stepd_ctrl_nos2_u0130_grafted.pt 5d212358) via deploy_ckpt.sh.
  LIVE_OPTIONS: + `--iw-press-head-decode sample` (as evaluated; backup LIVE_OPTIONS.pre_clx_20261019_0019);
  CKPT_OVERRIDE backup CKPT_OVERRIDE.pre_20261019_0019 (= cue_ab2). Verified: 00:25 log header = nos2 ckpt, iw_press head,
  decode sample, X-Bow in hand. Registered: CLIX: PRESS = cue_ab2 u65 (was unregistered), CLX: PARITY = nos2.
- Rule for the rest: if another arm passes with a higher pooled delta, re-switch (owner: highest pooled delta).
- 00:27 34210: stepd_ctrl_nos2_s75 (Mark CLX's seed-75 replicate = its run-to-run noise; cfg = nos2 yaml with seed 75) via
  arm_waiter (smoke -> chain); ~08:00 train end + evals ~09:15. readout.py pairs it with stepd_ctrl_nos2.
- 00:39 cue_ab2 (CLIX) final live record 18:10-00:19: 49-54 = 47.6% [37.9, 57.2], net 0 trophies (103 matches).
- 01:17 twin stepd_rebc3 (resumed) pulled (sha e8cd314a): std 642, fresh 610 -> +0.94 [-2.81, +4.58] / -0.94 [-4.58, +2.71],
  pooled +0.00 [-2.55, +2.60] -> no pass. From the IL init's -26 pp to CLIII level in 130 upd; u65 -5.10. early X-Bow 44.5% vs 65.7%.
- 01:18 14009: CLX greedy-decode re-score (REF chain, NAME clx_greedy, fin13 std+fresh, NO36) -- checks the live decode choice.
- 01:28 REB stepd_reb pulled (sha 5a8ea20a): std 583, fresh 533 -> -5.21 [-8.96, -1.56] / -8.96 [-12.81, -5.10], pooled
  -7.08 [-9.69, -4.43] -> CLEARLY WORSE, no pass; fork36 std -6.15; u65 -11.56. early X-Bow 45.1% vs 65.7%.
  cue_ab2 stays replaced by CLX (owner: REB not passing -> cue_ab2 would stay; moot since CLX passed).
- 01:29 19834 (temporary, REB copied): stepd_ctrl_nos2_s76 (third CLX seed) -> results ~10:30 EDT for the next session.
- 01:48 REB s75 pulled (sha 393b2434): std 556, fresh 539 -> pooled -8.18 [-10.89, -5.52], no pass. s75 - reb: -2.81 / +0.62 (n.s.).
  twin - REB: std +6.15 [+2.50, +9.69], fresh +8.02 [+4.38, +11.56] -> the CLIII card anchor beats the IL anchor.
- 01:52 10757 STOPPED via stop_pod.sh (stepd logs saved to pod_backup_weekend/stepd/pod_logs/10757); Discord note posted.
- 01:56 CTRL s75 pulled (sha d27d615d): std 639, fresh 624 -> pooled +0.57 [-1.98, +3.07], no pass.
- 02:00 30988 STOPPED via stop_pod.sh (D1/D2 artifacts already on laptop by sha; logs to pod_logs/30988); Discord posted.
- 02:02 CLX greedy-decode re-score pulled: greedy 672 / 675 vs sample 674 / 686; greedy - sample pooled -0.68 [-2.03, +0.68]
  (n.s.); greedy vs CLIII pooled +4.95 [+2.45, +7.45] (also passes). The live decode choice (sample) is not a risk.
  14009 (KEEP) idle after this.
- 02:04 CTRL (13396) pulled (sha ed5d2829): std 632, fresh 627 -> pooled +0.36 [-2.19, +2.92], no pass. CTRL - nos2:
  std -4.38 [-8.12, -0.83], fresh -6.15 [-9.58, -2.71] -> the Stage-2 exploiter opponents HURT (2 CTRL seeds agree).
  REB - CTRL raw (like-for-like): -7.71 / -10.73. CTRL raw - CTRL grafted std +2.60 [-0.94, +6.15].
- 02:06 14009: CLX RAW (ungrafted u130 0452c619) re-score, NAME clx_raw, fin13 std+fresh: is the graft costing CLX?
- 02:15 plan1019 'NOW' item 3 (lead's plan 8f75a67): Codex slices task launched (ticket plan1019/SLICES_TICKET.md; new file
  stepd/slices.py only, report plan1019/SLICES_REPORT.md; status SLICES_STATUS.md). Lead's takeover watch: see this log.
- 02:19 Codex slices DONE: stepd/slices.py (selftest PASS) + plan1019/SLICES_REPORT.md (16 SIM pools / 24,960 rows; live CLIII 168,
  CLIX 104, CLX 31). SIM rows lack crown order / heavy-push history -> several slices n/a; report only, no gate.
- 02:34 CLX RAW pulled (sha a18e91e9): raw - grafted (both greedy) pooled -1.61 [-4.01, +0.83] (n.s.); raw - CLIII +3.33
  [+0.89, +5.83]. The deployed config (grafted + sample decode) is the best measured point. 14009 (KEEP) idle.
- 03:57 twin s75 pulled (sha 9a4e44d4): std 632, fresh 611 -> pooled -0.47 [-3.02, +2.08], no pass; no guard trip, no resume;
  s75 - twin: -1.04 / +0.10 (n.s.). - 04:00 19400 STOPPED via stop_pod.sh (logs to pod_logs/19400); Discord posted.
- 05:20 par_eval.sh (+ par_eval_pod.sh) validated on 14009: CLX seed 741200 re-run = 348/480, outcome sequence IDENTICAL to
  the chain's rows (deterministic eval). Plan: when seed 76 grafts (~09:00) run its fresh/std seeds on 13396 + 14009 in parallel.
- 09:02 stepd_ctrl_nos2_s75 pulled (sha ec209d8c): std 647/960, fresh 598/960 -> vs CLIII std +1.46 [-2.29, +5.00] / fresh -2.19 [-5.73, +1.35] / pooled -0.36 [-2.92, +2.19]; pooled vs stepd_ctrl_nos2 (CLX) -5.99 [-8.33, -3.59]; u65 std vs CLIII -0.21 [-3.96, +3.54] -> no pass.
