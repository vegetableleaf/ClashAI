# Codex ticket (lead Claude, 10-20 ~07:00): set up two NEW pods as full step-d pods. MECHANICAL work only.
Pods (key ~/.ssh/runpod_clashbot; the owner's id_ed25519 does not exist on this laptop):
  P1 = root@64.247.206.80 -p 48148, P2 = root@64.247.206.80 -p 40548. Both empty: 27.2 CPU (cgroup), L40, 50 GB.
Goal: each pod ends up exactly like the existing step-d pods 13396 / 14009, so that
  (a) stepd/w6_arm.sh and stepd_chain.sh (EVAL_LEVELS=all16) run on it, and
  (b) a GPU fine-tune of the pro-imitation net (pipeline/ training code) runs on it.
How (read these first; follow what was done before, do not invent):
  - base bundles: C:/Users/benpe/AppData/Local/Temp/claude/C--Users-benpe-ClashBot/c11d06f6-d4d0-44d7-aa99-0f9ff1579dd8/scratchpad/pod1015/up.sh
    (`bash up.sh HOST PORT none`: data bundles + pod_setup_l74.sh + stage);
  - the fin13 runtime + step-d tree: stepd/STATUS.md milestones 5-6 (setup_fin13.sh, ship_stepd.sh, how 10757 / 30988 were
    staged) and l16/STATUS.md (how 15617 got its dependencies);
  - code: ship from the COMMIT (git archive), as the header of scratchpad/gauntlet/L74/stepd/w6_arm.sh shows
    (stage + stepd_code.tar + code.sha, then ship_stepd.sh HOST PORT -> CODE_OK);
  - checkpoints: copy, sha-verified, the files the arms need:
    - the init icebow/data/bench/rl_royale/rlarm_succ_levels/rlarm_succ_levels_u0065.pt;
    - CLX icebow/data/bench/rl_royale/rlarm_stepd_ctrl_nos2/rlarm_stepd_ctrl_nos2_u0130_grafted.pt;
    - CLIII;
    - the IL / S2 checkpoints stepd_l16_s74.yaml references.
    Take them from the laptop's icebow/data or pod_backup_weekend, or from pod 13396.
AUTHORITY: fix mechanical problems yourself (paths, quoting, missing helpers, re-copies). STOP only on a design question.
VERIFY on each pod:
  - `l16/pod_smoke.sh` with stepd/cfg/stepd_l16_s74.yaml -> SMOKE PASS;
  - `python -c "import torch; print(torch.cuda.is_available())"` -> True.
Then mark each pod READY in pods1020/STATUS.md (timestamps, shas, what was installed). Do NOT start any training or eval job:
the lead assigns jobs. Never stop a pod; no live changes. Rules: scratchpad/gauntlet/L74/plan1019/WORKER_RULES.md (no
`git add -A`, no `python -` stdin, no secrets). Commit pods1020/STATUS.md + any script you add (explicit paths), push.
Report: per pod READY / not, with the evidence.
