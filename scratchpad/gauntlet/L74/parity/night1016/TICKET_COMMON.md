# Shared context for the night-10-16 parity diagnosis workers (read fully before starting)

## Goal (owner, 2026-10-16 night)
SIM fight parity >= 97.5% overall and >= 95% for EVERY card. Metric (scratchpad/gauntlet/L74/parity/CEILING.md): per fight,
a tolerant card agreement (bodies end alive/dead the same, deaths within +-0.5 s, tower damage within 10%), normalised by
a measured NOISE CEILING (SIM-vs-SIM agreement under perturbation of unobservable state), per card judged on the 95% CI
lower bound. Your job: find WHY the SIM disagrees with live in the failing fights of your card(s), on the FULLY CAPTURED
logs first (hidden state observed there, so the ceiling is ~0.95-1.0 and almost every failure is a harness bug (H) or a
real SIM law (S), not unobservable noise (U)).

## Current numbers (royalesim 0.1.35, K=8, strict fights; captured = 27 matches with a phase-3 capture, 993 fights)
captured OVERALL raw 0.836, ceiling 0.953, normalised 0.877 [0.848, 0.901]
captured per card (raw / ceiling / normalised, n): own Log 0.765/0.997/0.768 (81); own Tesla 0.764/0.975/0.781 (55);
own Skeletons 0.744/0.900/0.817 (78); own Tornado 0.81/0.974/0.831 (21); own Knight 0.843/0.952/0.897 (70);
own Xbow 0.923/0.972/0.935 (78); own IceWizard hero 0.914/0.975/0.940 (93); own Knight evo 0.90 (20); own Tesla evo 0.778 (18)
Full scoreboards: C:/Users/benpe/pod_backup_weekend/parity1016/F35_BASE/{_cap,_old}/CEILING_strict.txt

## Data (laptop)
- Per-fight results: C:/Users/benpe/pod_backup_weekend/parity1016/F35_BASE/_cap/matches/<stem>.json (captured) and
  .../F35_BASE/matches/ (all 328). Record keys: summary, fights[]; fight keys: t_end, flags, bodies, sim_only, towers,
  stamp, card, t0, t1, anchor, own, obs, events. Scoring code in scratchpad/gauntlet/L74/parity/fights.py (HEAD 795b155):
  card_scores(r), fight_verdict(r, tower_tol), is_clean(r, 'strict'), ceiling_table(), score(), run_match(), run_fight().
- Live frame logs: scratchpad/gauntlet/L68/live_reader/live_play_<stem>.jsonl ('frame' events every ~2 ticks with all
  bodies: side, x, y, card_id, hp, max_hp, kind, ...; plus projectiles/effects/states on 10-16+ logs).
- Phase-3 captures (targets, attack progress/load/pre-attack, buffs per body; join on tick + generation id):
  icebow/data/p3_captures/<stem>/frames.jsonl and scratchpad/gauntlet/L70/reader/re_phase3/p3_*/frames.jsonl.
  These are gitignored reader outputs: NEVER copy raw rows, addresses or reader details into any tracked file; derived
  counts and per-fight summaries are fine. Exports used on pods: C:/Users/benpe/AppData/Local/Temp/claude/parity1016/{buffs,attacks}.json
- Prior diagnoses (read the relevant ones): L74/parity/DIAG2_1016.md (method, H1-H5 harness fixes, failure classes,
  killer.py), DIAG_1016.md, ATTACK_PHASE_1016.md, FIRST_HIT_1016.md, IW_SLOW_1016.md, S6_CUES_1016.md,
  READER_VALIDATION_1016.md, PARITY_SCOREBOARD.md (method + top mismatches), CEILING.md, FORK.md (patch rules).
  DIAG2 scripts (reusable): C:/Users/benpe/ClashBot/.foreman/scratch/diag2/*.py (killer.py, dossier.py, bodies.py, classify.py).
- SIM for single-fight replays on the laptop: set PARITY_SIM_PATH=C:/Users/benpe/rt_wheels/royalesim-0.1.35 and use
  C:/Users/benpe/ClashBot/research/ext/Royale/.venv/Scripts/python.exe (PYTHONPATH=C:/Users/benpe/ClashBot).
  Engine source to read (Rust): C:/Users/benpe/ClashBot/research/ext/Royale/RoyaleSim (local branch clashbot; upstream
  tags v0.1.35 / v0.1.36 are fetched: `git -C ... show v0.1.35:<path>`; do NOT switch branches or edit it).

## Compute
- LAPTOP IS SHARED and already ~80% CPU (live play + MuMu run on it): only SINGLE-fight replays, one process at a time.
- Pods (key ~/.ssh/runpod_clashbot; Linux, python3 3.12; royalesim 0.1.35 at /workspace/rs0.1.35, 0.1.36 at /workspace/rs0.1.36;
  parity code + all 328 logs at /workspace/cb_par; exports at /workspace/{buffs,attacks}.json; runner /workspace/in/run_par.sh):
  pod A = `ssh -p 18731 root@216.81.245.71`, pod B = `ssh -p 14318 root@64.247.206.76`. Your ticket names YOUR pod.
  For any batch rerun: copy /workspace/cb_par to /workspace/w_<you>/ and edit only that copy; results in
  /workspace/results/<you>_*; at most 12 workers; prefix with `nice -n 10`. Never touch /workspace/cb_par, other
  workers' dirs or results, never stop/restart a pod, never run `runpodctl`.

## Rules
- Public information only: never use opponent hand / next card / elixir (owner rule) -- you only analyse SIM vs live bodies.
- Do not edit ANY tracked repo file. Create new files only under
  C:/Users/benpe/ClashBot/scratchpad/gauntlet/L74/parity/diag_night/<you>/ (scripts, notes, patch files). No git commands
  that write (no add/commit/stash/checkout/switch).
- NEVER run `python -` / `python.exe -` with a heredoc or stdin: on this laptop it opens a hanging interactive REPL.
  Always write the script to a file and run `python file.py`. Kill processes only by exact PID, never by pattern.
- Do not run live_play, adb, MuMu, or anything touching the live account.
- One mechanism per proposed fix; every claim labelled (a) measured, (b) plausible but untested, (c) contradicted.

## Deliverable: diag_night/<you>/REPORT.md
1. Every failing strict fight of your card(s) on the CAPTURED logs: stem@t0, class H / S / U (+ sub-class), the FIRST
   divergence (tick, body, what differs, live vs SIM numbers), with evidence.
2. Clusters ranked by number of failing fights.
3. Per cluster, the proposed fix:
   - H: a patch file (diff vs fights.py at 795b155) + its measured before/after on the captured cohort for your card AND
     the overall captured score (no other card may regress; say so with numbers), run on your pod;
   - S: the law, where it lives in the engine source (file:line at v0.1.35), a minimal fixture (setup from captured
     frames + the expected live outcome), confidence (a/b/c), and how many failing fights it would explain;
   - U: exactly what the reader would have to capture.
4. Estimated gain on your card's normalised score if each fix lands, and what remains.
Report back with one status line (DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED), the summary table, and paths.
Time budget: aim to report within ~3 hours; write REPORT.md incrementally so partial results survive.
