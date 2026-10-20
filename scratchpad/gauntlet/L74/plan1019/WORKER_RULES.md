# Rules for every worker on the 10-20 plan (lead: Claude; plan: plan1019/TUESDAY.md + PLAN.md)

Repo C:\Users\benpe\ClashBot (main). Memory (read the index, then the files your ticket names):
C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\MEMORY.md. HANDOFF: use `git show HEAD:HANDOFF.md`
(the working-copy HANDOFF.md is a STALE uncommitted copy -- never stage it).

- Git:
  - commit only explicit paths; never `git add -A` or `git add .`;
  - check the staged file count and grep the staged diff for secrets before each commit;
  - commit + push to main when your deliverable is done.
- Secrets: never print, log or commit API keys (C:\Users\benpe\.anthropic_key.txt), the Discord webhook
  (icebow/data/discord_webhook.txt), icebow/data/reader_config.json, or any reader internals (offsets, hashes, sampler commands,
  binary names). Private notes only under the gitignored icebow/data/reader_notes/.
- Never run `python -` with stdin (a hook blocks it). Write scripts to files.
- Kill processes only by exact PID, never by name pattern.
- LAPTOP IS SHARED and runs live play: single-process analysis only, no training, no multi-worker SIM runs on the laptop.
- Pods (ssh -i ~/.ssh/runpod_clashbot): 13396 = root@64.247.206.76 -p 13396, 14009 = root@64.247.206.76 -p 14009,
  15617 = root@216.81.151.5 -p 15617, 19899 = root@64.247.206.76 -p 19899. Until ~06:00 EDT 10-20 they run the L16 successor
  seeds (stepd_l16_s74..s77): do NOT disturb them. After that, ask the lead (report NEEDS_CONTEXT) before using a pod.
  Never stop a pod.
- No live-play changes, no deploys, no edits to scratchpad/gauntlet/L70/live/* or L68/live_reader/* unless your ticket says so.
- Trainer edits (pipeline/rl_royale.py, royale_env.py, e1_eval.py, gap.py):
  - opt-in config keys only; absent = byte-identical behaviour + config hash, proven by a test;
  - pyflakes undefined names empty;
  - a REAL `python -m pipeline.rl_royale --smoke` printing SMOKE PASS before you report;
  - the laptop smoke uses research/ext/Royale/.venv; a 0.1.35+ runtime may be needed -- if it cannot run on the laptop within
    15 min, mark the smoke UNVERIFIED and say so.
- Learned behaviour only: no hard-coded play rules for live. One change per experiment.
- Measured vs untested: label every claim (a) measured with the number, (b) plausible but untested, (c) contradicted.
  Do not fit the model to average pro numbers: the owner rejects matchup-blind averages. Analyse situations in context.
- Report starting with exactly one status: DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED. Keep the report under
  ~600 words; put detail in your deliverable files.
