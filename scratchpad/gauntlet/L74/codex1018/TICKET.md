# Codex worker ticket 10-18 (owner-authorized; Codex does the usage-heavy work, Claude coordinates)
Repo C:\Users\benpe\ClashBot. Read HEAD's HANDOFF.md top entries (git show HEAD:HANDOFF.md; the working-copy file is STALE, never stage it) and the memory dir C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\ (MEMORY.md index first).

TASKS, in order (= HANDOFF next steps 1-2 plus the report):
1. Check every running job: the step-d executor (L74/stepd/executor.log, STATUS.md, local PID 10448), the round-7 closer (L74/parity/diag_night/R7_STATUS.md, R7_SUMMARY.md, r7_closer.log, PID 26708), the combo relay (PID 41080) and every pod in the "SESSION HANDOVER" table (ssh -i ~/.ssh/runpod_clashbot). Record alive / done / failed for each.
2. The step-d executor ticket (L74/stepd/EXECUTOR_TICKET.md) still anchors the KL leash to CLIII, but the owner's final guidance favours pro-imitation. Correct the ticket text only, and log the change in STATUS.md. Do NOT restart the executor unless it has died.
3. Collect finished results (Stage 2 A/B, combo ctl/reward, cue_ab2 / c3_ab / c3_ctl, round 7). Copy them to C:\Users\benpe\pod_backup_weekend\ with sha256 verification; normalise Git-Bash "hash *path" before comparing. Score candidates with the existing tools (L74/mix/live_cmp.py, gap.py) against ICEBOW Mark CLIII (edc82ada) on standard + fresh seeds.
4. Pods: keep 15617, 19899, 13396, 14009. Stop any other pod ONLY when its results are copied back and no further delegable pod work exists, and only via L74/deploy/stop_pod.sh.
5. Write L74/codex1018/REPORT.md: per-job status, every result with CIs, findings, the recommended next action. Prepend a short dated section to HANDOFF via `git show HEAD:HANDOFF.md`, cat, `git hash-object -w`, `git update-index --cacheinfo`. Commit explicit paths only; push to main. Post a <= 900-char summary with python scratchpad/gauntlet/L69/discord/post.py FILE.

HARD RULES:
- Do NOT deploy or switch the live checkpoint and do NOT start live runs: report candidates instead.
- Never `git add -A` or `git add .`. Before each commit, check the staged count and grep the staged diff for secrets.
- Never print, log or commit API keys (C:\Users\benpe\.anthropic_key.txt), the Discord webhook, icebow/data/reader_config.json, or any reader internals (offsets, hashes, sampler commands, binary names).
- Never run `python -` with stdin. Kill processes only by exact PID, never by name pattern. Never touch overlayed_replays.
- The laptop is shared: no long CPU/GPU jobs on it. Heavy compute runs on the pods.
- No hard-coded play rules in live.
- Write SIM numbers as they are: a SIM gain has not transferred to live (CLIII +4.4 pp SIM but 47.8% live).
