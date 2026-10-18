# API worker: OVERNIGHT ORCHESTRATOR 2026-10-18 -> 10-19 10:00 EDT (owner asleep)
You are the decision-maker overnight. Use Codex (codex exec -m gpt-6-astra -s danger-full-access) for heavy mechanical work
(copy-backs, evals, log crunching). Read first: memory index C:\Users\benpe\.claude\projects\C--Users-benpe-ClashBot\memory\MEMORY.md
(esp. stop-idle-pods, checkpoint-naming-convention, icebow-keep-both-towers-doctrine, overnight-2026-10-17-auto-promote),
HEAD's HANDOFF.md top entries (git show HEAD:HANDOFF.md; working copy is stale), L74/stepd/STATUS.md, L74/codex1018/REPORT.md.

Owner orders for tonight (verbatim intent):
1. MONITOR all runs until 10:00 EDT. Poll in loops of <= 9 min per command (pods via ssh -i ~/.ssh/runpod_clashbot).
   The step-d executor (API worker) and round-7 closer (API worker) own their jobs: coordinate through their STATUS files;
   do not duplicate their work. The doctrine worker (L74/doctrine/) is also running.
2. PODS: a pod that will sit idle for several hours -> copy back its results (sha-verified; normalise Git-Bash "hash *path")
   then stop it ONLY via L74/deploy/stop_pod.sh. A pod that opens up and has useful work available -> put the next run on it
   (priority: step-d arms/evals the executor needs; FIN13/parity work the closer needs; doctrine measurements; then
   seeds of the strongest pending arm). Keep 15617, 19899, 13396, 14009 unless the owner list in memory says otherwise.
3. AUTO-PROMOTE: a successor that beats ICEBOW Mark CLIII (edc82ada) with paired 95% CI low > 0 on BOTH standard
   (741200+742000) and fresh (743000+744000) seeds, 960 games each, same code/runtime for both models -> promote with
   L74/deploy/deploy_ckpt.sh CKPT SHA16 "why" (NOT wire mode). If several pass, the highest pooled delta. A head (ability_head)
   model needs `--iw-press head` in L70/live/LIVE_OPTIONS (it is there now); a model without a head needs it removed first
   (back up LIVE_OPTIONS). Name it per the naming convention ("ICEBOW Mark <Roman>: <ONE WORD>").
   Currently live: cue_ab2 u65 (fb777048), an owner-approved TRIAL until REB is ready; it is not the bar -- CLIII is.
   If REB finishes and does NOT pass, leave cue_ab2 live and report in the morning.
   KNOWN BUG: deploy_ckpt.sh / restart_live.py report "restart failed" when the Discord post times out; check the real
   state (live_play processes, CKPT_OVERRIDE, the newest live_play_*.jsonl shows the icebow deck) instead of trusting it.
4. Keep usage minimal: no new research directions beyond the above.
5. At 09:30 EDT write L74/overnight1018/MORNING.md (what finished, every result with CIs, pods started/stopped, promotion
   verdicts, live match record of cue_ab2 since 18:10 with win rate, next steps), prepend a short HANDOFF section
   (git show HEAD:HANDOFF.md + cat + hash-object + update-index), commit explicit paths, push, post <= 900 chars to Discord
   (python scratchpad/gauntlet/L69/discord/post.py FILE). Also post a short Discord note on each promotion or pod stop.
Rules: never `git add -A`; never print/commit API keys, the webhook, reader_config.json or reader internals; no `python -`
with stdin; kill only by exact PID; laptop is shared (no heavy compute on it); never touch overlayed_replays;
no hard-coded play rules in live; never revert an owner-chosen live model except via the promotion rule above.
