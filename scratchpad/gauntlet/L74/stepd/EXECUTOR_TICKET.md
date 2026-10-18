# Step d executor ticket (lead, 2026-10-18 ~10:45 EDT; runs as a headless API-key worker)

You are the step-d EXECUTOR for ClashBot. Repo C:\Users\benpe\ClashBot (Windows laptop; Git Bash). Read these first, in order:
1. scratchpad/gauntlet/L74/stepd/PLAN.md: the plan you execute (D1 data, D2 imitation, RL arms, gates)
2. HEAD's HANDOFF.md, the top entries: `git show HEAD:HANDOFF.md | head -400`; the working copy is stale
3. the memory index C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\MEMORY.md and the files it lists for
   stepd-started-exception, owner-decisions-1017-night, iw-press-train-mismatch, stop-idle-pods and api-key-workers

## Owner decisions on the plan (10-18)
1. commit the in-flight rl_royale code after a real pod smoke
2. re-score CLIII on fin13 for the gate
3. D1 on a temporary pod
4. the LEAGUE arm yes, lowest priority
5. APPLY the 3x unfavourable-matchup weighting in imitation too
6. REB leash = the CARD choice only, anchored to CLIII, VERY loose (no other heads leashed)

Owner doctrine to measure: offensive bridge X-Bow only in a punish window; Rocket / Rocket + Tornado vs heavy pushes.

The owner's view: the strongest candidate is the new imitation build + the current best RL recipe (live levels, the live IW
press rule in training) + realistic opponents (Stage 2). Make that the REB arm. Also run CTRL (CLIII + the same updates) for
attribution.

## Pods (ssh -i ~/.ssh/runpod_clashbot root@HOST -p PORT)
- NEW for you now: 64.247.206.80:30988 (27.2 CPU, L40, empty, KEEP set). Do D1 + D2 here first.
- Then for RL: 64.247.206.76:13396 and 64.247.206.120:19834, once their Stage 2 Phase D runs finish (~17:00-18:00 EDT; the
  results go to C:\Users\benpe\pod_backup_weekend\stage2\; check /workspace/s2/chain.log for CHAIN_DONE). The Stage 2
  checkpoints s2_all_il_sA / sB are your league opponents.
- 64.247.206.76:14009 runs the ability arms (c3_ab), so don't use it until its worker is done: no rl_royale / gap.py processes
  running.
- Parity pods 216.81.151.5:15617 and 64.247.206.76:19899 are NOT yours.

## Rules
- Never commit except as owner decision 1 says (rl_royale after a real pod smoke). Explicit paths only. No secrets. Push to main.
  HANDOFF entries go via scratchpad/gauntlet/L74/parity/night1016/add_handoff.sh ENTRY_FILE "subject".
- Never touch the live process, MuMu, LIVE_OPTIONS or CKPT_OVERRIDE. Do NOT deploy: report candidates. The owner's bar is a
  clear, significant gain vs CLIII (CI low > 0 on the standard AND fresh seeds). Measured caveat: CLIII was +4.4 in the SIM and
  ~0 live, so SIM passes are weak evidence; say so.
- Never stop a pod and never arm a watchdog / deadline / runpodctl timer. Keep >= 8 GB free on pod disks; delete your own cargo
  / build caches.
- Never run "python -" (hook-blocked). Kill only by exact PID / process group, after checking what the process is.
- The laptop is CPU-starved by live play: heavy work on pods only.
- After any rl_royale / royale_env / eval edit: pyflakes + a REAL rl_royale --smoke on a pod.
- Copy every result back to C:\Users\benpe\pod_backup_weekend\stepd\<job>\ with sha256 verified (laptop "hash *path" vs pod
  "hash  path").
- Write progress to scratchpad/gauntlet/L74/stepd/STATUS.md after every milestone: what runs where, PIDs, ETAs, results so far.
  Another Claude session (the owner's other account) will pick this up.
- Whenever a result lands, post a one-paragraph Discord update with the existing poster:
  `icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L69/discord/post.py MSGFILE`.

Return a plain-English final report when D2 is evaluated and the RL arms are launched, or earlier if blocked.
