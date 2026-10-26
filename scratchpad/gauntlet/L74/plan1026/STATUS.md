# plan1026 STATUS -- start here (updated 2026-10-26 ~14:25 EDT, account 1 handing over)

Read in order: this file -> PLAN.md (owner-approved) -> the HEAD HANDOFF top entries (`git show HEAD:HANDOFF.md | head -80`).

## Where things stand
- PLAN APPROVED 10-26 with owner revisions (non-win-only reward, no KL leash, macros, barrel_lane kept, NO-DISCARD rule).
- Step 0 DONE: pods 32657 + 33920 kept IDLE (ssh -i ~/.ssh/runpod_clashbot -p PORT root@157.157.221.29); 33458 + 33411
  stopped; arm records in C:/Users/benpe/pod_backup_weekend/night1025/.
- Owner decisions: 1 (99.9% definitions) default; 2 CLXIII = fixed live data config; 3 barrel_lane kept for successors;
  4 battle-log polling APPROVED + RUNNING; 5 device checks DONE (devcheck/REPORT.md); 6 pods as above; 7 TV Royale
  harvesting APPROVED (not started).
- LIVE ON since 14:14 EDT (owner request): icebow Ranked, CLXIII NOLEAK (8d328a43), main account verified. Keep the Mark
  fixed. Stop: bash scratchpad/gauntlet/L70/live/stop_live.sh.
- Battle-log poller: scratchpad/gauntlet/L74/crapi/own_poll.sh (background, every 15 min, tag #20Q0UV0GPQ, key in
  ~/.cr_api/key -- never commit / print; proxy fallback) -> crapi/data/own_battlelog.jsonl. Restart after a reboot.

## Device-check facts that change the plan (devcheck/REPORT.md)
- Battle-log replay read by the reader = live board on 0.9971 of ticks, AND gives both decks + forms, both hands, both deal
  orders from tick 0, exact elixir. Use replays (recorder.py) for: G1 seed recovery (both deals known), opponent live rows
  with exact opponent state, and engine SME inputs. No replay file on disk (G-R3 no).
- Menu: top-right menu (820,170) -> Battle Log (540,110) -> Watch (750,765 newest); TV Royale (540,350). 900x1600 screen.

## NEXT (days 0-3; wait for the owner's go -- they said "do not start the plan yet" at 12:50)
- A1 fin16 build + A/B + register fin16-linux (pod 32657).
- A2 crforge pin + G0 random-draw census + G1 seed recovery, now using replay deal orders (pod 33920).
- B unified decide() for rollouts / forks / SIM eval / live + identity tests + SIM config from LIVE_OPTIONS (laptop; live
  path -> blind verifier; fix the stale test_ability_live PRE-8c70811 test: taps identical, only new log fields differ).
- C opponent scorecard A/B/D on old baselines + THRESHOLDS.json pre-registered before any training.
- Battle-log replay harvesting of our own live matches (new, cheap): after each live match or in batches, Watch + record.
- TV Royale harvest (approved): replay_rec/harvest.py needs menu templates from the menu facts above.
- Owner rule: invoke the fable-foreman skill for multi-file work; tickets were planned but none dispatched; no ledger yet.

## Parked / traps
- Fork-credit WIP: wip_cf_credit/ (patch + cf_credit.py; git apply at the cf_credit review, days 8-22; 6 test failures unsorted).
- brT10_s121 / s122 / brT05_s123 "DRIFT FAIL" = startup crash (shaping_critic_scale 3.5 < 3.7 bound), not drift.
- ~15k dirty files in the tree: stage explicit paths only; HANDOFF only via codex1018/stage_handoff.sh.
