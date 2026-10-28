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

## STATUS (2026-10-28 ~18:10 EDT)
- Logs: Codex V1LIVEROWS_1 (low) copying 2,546 logs laptop -> 33553 `/workspace/v1live/logs/*.jsonl.gz` (+ sha256 both sides).
- Test (14 calibration matches, pod): self-check (A) hand 100%, own elixir 100%, opp counter 99.91%, units 100%, towers 100%
  (after counting off-slot card_id -1 bodies as units: the live model's model_bodies include them).
- Wave 1 build running on 33553 (`/workspace/v1live/run_wave1.log`) on the logs copied so far.
