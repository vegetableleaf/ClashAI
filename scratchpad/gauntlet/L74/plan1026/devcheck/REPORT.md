# Plan 10-26 device checks (G-R2, G-R3) -- 2026-10-26 13:03-13:20 EDT, owner present, model played the match

Match: live CLXIII NOLEAK, Ranked, main account (towers 4858), 1-0 WIN in overtime vs 902b; live log
`L68/live_reader/live_play_20261026_130453.jsonl` (live run started 13:03, STOP after this one match, supervisor exit 13:08).
Replay: battle log (menu -> Battle Log -> Watch) recorded by `L74/replay_rec/recorder.py --device`
(`icebow/data/replay_rec/rec_20261026_130926.jsonl`, local data, not committed).

## G-R2: does the replay viewer reproduce the live reader's board? (a) YES
`cmp_live_replay.py` -> cmp_live_replay.out:
- live frames 1,983 (ticks 151-4136, 2-tick sampling), replay frames 2,068 (ticks 0-4136); common ticks 1,017.
- Exact board on 1,014 / 1,017 common ticks = 0.9971; tower rows equal 1,015 / 1,017.
- Paired bodies 11,014: position identical on 11,012, HP identical on 11,012; live-only 2, replay-only 1.
- So the reader's own frame-to-frame error is ~0.3% of ticks, far below the ~0.008 noise ceiling the engine audit assumed.
- The replay adds what live cannot see: BOTH players' deck_card_ids + forms, hands, cycle (deal) order from tick 0 and
  exact elixir (4,118 full-hand rows over 2,068 frames x 2 sides). Both deal orders = direct input for G1 seed recovery.

## G-R3: does the client cache an official replay file? (a) NO (on disk)
Root `find` of /data/data/com.supercell.clashroyale + /sdcard/Android/data/... before and after watching (1,401 files both
times): no new file; only cache / telemetry mtimes changed (files_changed_during_replay.txt: event images,
cache/manifest.json, cache/loading/info, update/fingerprint.json, sentry breadcrumbs). The replay streams into memory; the
crforge ReplayScenario shortcut is not available from disk. The reader-recorded replay (above) is the route.

## Menu facts for harvesting
Main screen menu (top right, 820,170) lists Battle Log (540,110) and **TV Royale** (540,350). Battle Log entry -> Watch
(750,765 for the newest). The replay plays at x1 with a speed control on the left.
