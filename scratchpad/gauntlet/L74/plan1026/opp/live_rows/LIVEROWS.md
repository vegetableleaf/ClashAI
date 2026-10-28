# V1-LIVEROWS: live opponent-seat slot rows for opponent v1's live fine-tune (plan1026 Pillar 2, step 3)

How humans play against OUR bot, as training rows in the HF slot format (same builder: pipeline.dataset_gen fv 5, wait_stride 10,
play_window 0, slot_redrive sidecars + memory tables, rows_to_npz unchanged). Pod 33553, `/workspace/v1live`.

## Pipeline (code here; pod copy /workspace/v1live/cb = git archive + this dir + the laptop's live_card_catalog.json + RoyaleSim data)
1. `select.py` (laptop, metadata only): icebow, non-dry, graded logs in the train / calibration blocks by NAME (sealed never
   opened); band R = Ranked ('trophies n/a' result line), L = ladder 12.0-12.9k, M = ladder >= 13k -> `select.json`.
   `copy_list.txt` = the 2,546 with 2-tick frames (>= 10-15 17:26). `bl_decks.json` = Ranked battle log -> log (laptop:
   `live_records.py --write-bl`), 575 calibration logs.
2. `live_records.py`: log -> driven-corpus record (o1_records helpers): every frame, a frame on every grid tick (exact or snapped
   <= 2 ticks), opponent act tick = first sighting - 20 (-1 if on the grid), opponent elixir = live counter minus acted-unsighted
   costs, cycle-rule hand (+ fitted deal for plays 1-4, hand_inferred), deck seen8 / battlelog / HF+census completion.
3. `live_rows.py`: per chunk dataset_gen.build (wait rows on grid frames only) -> self-check on OUR seat (`selfcheck.py`) ->
   opponent-seat rows only -> slot_redrive._slot_n2p (parquet + slot sidecar + memory tables).
4. `live_npz.py`: rows_to_npz (keep_wait 1, HF v0 deck map) -> extracted dir; ctx_band 4/5/6, ctx_mode, ctx_era 2, split by time
   (train 0, newest 10% of train matches 1, calibration 2), ab_ok 0.
Run all (resumable): `ssh -p 33553 ... 'cd /workspace/v1live && setsid nohup bash cb/scratchpad/gauntlet/L74/plan1026/opp/live_rows/run_live.sh 32 16 final > run_final.log 2>&1 < /dev/null &'`

## STATUS (2026-10-28 ~23:10 UTC): DELIVERED. Nothing of mine is running on 33553 (the loop ended: LOOP_DONE).
- 33903 `/workspace/opp/live/live_train`, `live_cal` (+ `_memory.npz`, `.sizes.json`, selfcheck*.json); sha256 of all 92 files
  identical to 33553 `/workspace/v1live/out` (live_calibration there = live_cal). Copied pod-to-pod (ssh -A).
- live_train: 1,023 matches / 445,031 rows / 31,788 play rows (27,642 card_ok); band L 194, M 565, R 264 matches; split 0 = 921
  matches, split 1 = the newest 102 (from live_play_20261022_191313). live_cal: 708 matches (all R), 323,649 rows, 24,100 play
  rows, split 2. Archetypes (train / cal matches): weak_other 346/257, other 252/174, hog 216/147, hyperbait 86/61, royal_giant
  36/18, golem 30/26, lava_hound 21/5, pekka_bridge 19/17, royal_giant_monk 17/3.
- Coverage: train 1,678 logs -> 1,039 with an opponent deck (seen8 941, hf 98), 16 dropped (minion-giant / spirit-empress not in
  vocab_hf); left out: 7 seen no library match 400, < 7 seen 194, mirror 15, other 30. Calibration 868 -> 734 (seen8 501,
  battlelog 224, hf 9), 17 vocab drops. Logs: all 868 calibration logs sha-identical laptop vs pod (logs_cal).
- (a) self-check, train / calibration (74,276 / 56,826 our-seat rows at live decision ticks): hand 99.90 / 99.92%, own elixir
  100 / 100%, opponent counter (<= 0.5) 99.22 / 99.91%, units 99.89 / 99.89%, towers 100 / 99.99%.
- (a) label quality on our seat: taps publicly sighted 99.93 / 99.93%; cycle-rule hand determined 89.4 / 90.5%, exact 99.66 /
  99.67%; (sighting - 20) - decision tick p50 troop 5 / 4, building 5 / 4, spell 6 / 5 ticks (p90 troop 22 / 20, spell 24 / 24;
  within +-2 of p50: troop 78 / 81%, building 86 / 88%, spell 71 / 70%); public counter vs true elixir within 0.5: 81.9 / 81.3%
  (mean |d| 0.36 / 0.37). Decks: planted completion answered 27.7%, right 89.1%; battle log (563 calibration matches): seen-8 ==
  battle deck 98.8% (n 332); real 7-seen completions answered 15.5%, right 81.5% (n 27 answered of 174).
- NOT DONE: re-drive validity in crforge (b): needs live -> HF replay conversion + opponent card levels; proposed as the next step.
- Codex: V1LIVEROWS_1 (low): log copy + sha256 of all 2,546 -> still running at 23:15 UTC (its train-log sha is the pending
  integrity proof for logs/; the 868 calibration logs are already proven by my own sha diff). V1LIVEROWS_2 (low): verify the
  final dirs -> DONE, every check passes (N 445,031 / 323,649, memory coverage 100%, no sealed tag, split order OK);
  numbers match live_npz's own counts; script + results .foreman/scratch/a2/codex/v1lr_verify_*.
