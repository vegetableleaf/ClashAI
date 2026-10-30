# MEM-FULL: full-match memory + a board snapshot per play (owner priority item 2, 10-30)

Owner: "who placed what card, where, when, and on what board state" -- not the newest 128 events; encoder not frozen.
Grades: (a) measured (number + source), (b) plausible, untested (with the test), (c) contradicted.

## STATUS + RESTART POINT (keep current)

- Step 1 (measure): DONE. Step 2 Python builder: DONE (opt-in, tests green). Step 2 model / rl_royale / e1_eval / live
  plumbing: see the checklist below. Step 2 Java CfMem: see below. Step 3 encoder: recipe in section 4.
- Restart: read this file top to bottom; the checklist says what is committed. Tests:
  `icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_full.py pipeline/tests/test_match_memory.py -q`
- Checklist (commit after each):
  - [x] measurement scripts + results (`memory/full/`)
  - [x] `pipeline/match_memory.py`: `MatchMemory(side, e_max=128, snap=False)`, `build(.., e_max, snap)`,
        `features_at / rows_features(.., e_max=128)`, `empty_rows(n, version, e_max, n_f)`, `opts(mem)`, SNAP_FIELDS,
        mirror; golden pin `pipeline/tests/mem_full_golden.json` + `test_memory_full.py` (8 tests)
  - [ ] model_gen: `MemoryEncoder` e_max / snap (buffer `mem.full` only when opt-in), `widen` of an existing encoder
        (new ev_in columns zero = identical outputs), load by content
  - [ ] rl_royale keys `memory_e_max` / `memory_board_snap` (absent = historical hash), e1_eval `_memory` / `gen_batch`,
        rl_royale mem row cache, train_memory, eval_gen, dataset_gen tables, live_gen memory_rows: all read `MM.opts(model.mem)`
  - [ ] Java CfMem: per-instance eMax / snap + identity on pod 33903 (CPUs 194-201)
  - [ ] pilot loop (CfTrain stride / producer views) for a non-default layout
  - [ ] real `rl_royale --smoke` on a pod with the keys on

## 1. How often does E_MAX = 128 truncate? (a)

Event = every play / ability press of both sides + debounced tower damage + tower falls (match_memory.MatchMemory.table).

| source | matches (tables) | mean | p50 | p90 | p99 | max | share > 128 | > 192 | > 256 | decisions truncated |
|---|---|---|---|---|---|---|---|---|---|---|
| pro (gen_v32 fv5 memory tables) | 29,322 sides / 14,661 replays | 109.1 | 100 | 169 | 201 | 229 | 28.5% | 2.5% | 0 | 3.46% of 3.52 M rows (OT 17.2%, 1x / 2x 0%) |
| live, ours (newest 400 complete logs, 10-29 01:51 .. 10-30 09:33) | 400 | 105.8 | 101 | 151 | 177 | 203 | 28.0% | 0.25% | 0 | 2.51% of 150,004 decisions |
| SIM (crforge fast loop, LOOP-MEM identity run `speed/crforge/obsid/results/mem_live.json`) | 112 sides / 56 matches | 110.2 | -- | -- | -- | -- | -- | -- | -- | 2.6% of 51,396 rows had all 128 slots full |

- When it truncates (a, pro): the 129th event comes at 260 s median (p90 292 s): only in OVERTIME (8,337 of 8,362 matches
  over 128 pass it in OT, 25 in 2x, 0 in 1x). Live the same: 129th event at 271 s median.
- What it drops (a): the OLDEST events. Pro, at the match end: 277,970 events dropped (8.7% of all events), of them
  1x-phase 224,070 (81%), 2x 53,641, OT 259; plays 214,690, tower damage 59,728; own / opp ~even (141k / 137k). Live: 2,344
  dropped, 1x 2,241 (96%), 2x 103, OT 0. A truncated decision loses 17.9 events on average (pro).
- So in OT -- where the owner's Rocket-cycle / tower-margin decisions live -- 17% of pro decisions do not see the opening
  (the first X-Bow outcomes, the opponent's first reveals, which plays worked in 1x). That is the "information limited on
  purpose" the owner named. (a)
- Type mix per match (pro): plays 68.5, presses 1.4, tower damage 37.7, falls 1.5; by phase 1x 40.9 / 2x 34.9 / OT 33.3.
- SIM distribution per table is (b) not measured beyond the mean: the identity harness only sums rows. It is measured for
  free by the Java identity run of step 2 (table rows per table). SIM mean 110 vs pro 109 vs live 106: same scale (a).
- Choice: **`memory_e_max: 256`** = every measured match whole (max 229 pro / 203 live; 0 of 29,722 over 256) with ~12% margin
  over the pro max. It stays a safety cap (a 256 + match would keep its newest 256); share at the cap is a monitor to add.

Scripts: `memory/full/count_events.py` (tables / counts), `memory/full/live_counts.py` (live logs via live_dump.read, the S1a
build proved = the live path 2013/2013); outputs `memory/full/pro_counts.json`, `live_counts.json`, `live_summary.json`.

## 2. The opt-in keys (design)

- `memory_e_max` (int, absent = 128): events kept, newest first. The encoder has NO positional embedding (model_gen
  MemoryEncoder: per-event Linear + card embedding, 2 pre-norm layers, masked mean + attention pool), so it accepts any
  length with no new parameter; padding is masked, so a match with <= 128 events gives the same encoder output
  mathematically (float noise from a longer padded tensor: (b), measured in section 4).
- `memory_board_snap` (bool, absent = off): SNAP_FIELDS (24 floats) appended to every play / ability event row
  (F 46 -> F_SNAP 70), from the last sample BEFORE the play -- the sample crowns / margin already read: causal and public
  (the board the decision rows see; no hidden info). Per side (me / opp) x 4 zones in my frame (back / front half x left /
  right lane): bodies with a known value (match_memory._value, the play-outcome value rule) / 10 and their elixir value / 10;
  the 6 tower HP fractions; known flags (tower reads, bodies). Tower events: zeros. Static group (visible with the event).
- Absent = byte-identical (a): golden sha256s of tables, features v1 / v2, features_at, rows_features, empty rows written from
  the unmodified code (c51efd9) and re-checked after the change: `test_absent_is_byte_identical_to_golden` passes.
- Tests (a, `pipeline/tests/test_memory_full.py`, 8 pass): e_max keeps older events only (first 128 rows, summary, answer
  identical); snap appends only (first 46 columns and every other key identical; tower events zero); incremental ==
  offline == features_at == rows_features with both on (e_max 384, > 128 events really used); randomised causality with both
  on; crafted snapshot values; mirror (l <-> r zones, princess HP L <-> R; twice = identity); empty rows / opts.
  Existing suites: test_match_memory 28 pass; test_memory_v2 1 failure PRE-EXISTING and unrelated (its lock-head meta sha
  vs the committed counter_priors.json sha: two artifact files, no code path of this change).

## 3. Java CfMem + live (identity)

(pending; see the checklist)

## 4. Encoder: what the S3-aux encoder needs, and the retraining recipe

(pending)

## Ledger of Codex dispatches

(none yet)
