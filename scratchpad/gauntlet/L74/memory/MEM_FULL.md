# MEM-FULL: full-match memory + a board snapshot per play (owner priority item 2, 10-30)

Owner: "who placed what card, where, when, and on what board state" -- not the newest 128 events; encoder not frozen.
Grades: (a) measured (number + source), (b) plausible, untested (with the test), (c) contradicted.

## STATUS + RESTART POINT (keep current)

- MEMFULL-LOOP (10-30, closed out at usage 97%): the fast-loop wiring is COMMITTED BUT NOT VERIFIED: do not train on it yet.
  Code: CfTrain enableMemory(t, stride) / 7-arg setMem (per-seat eMax / snap, rows at memStride), producer mem_opts + per-layout
  Rows.memory views (the learner's 256 / snap beside a 128 opponent: the pilot's `init` opponent B0 stays 128 / off, so the
  checklist's "all memory policies share opts" rule would have blocked the pilot), serve.py --mem-full + spec_for per model
  (needed: pilot_arm.sh runs --server eager and policy_server's load is strict), bench / fastloop pass it, compare.py e_max,
  msg_memfull.py (widens a message's sd; handles a plain GenModel learner only, NOT an `opp_init` learner message).
  Measured: (c) the only compare run FAILED before any row check: `AssertionError: (16, 15)` at compare.py's
  len(prod) == len(fast) on /workspace/fliv/out/cmp_live_b8.json.msg.pkl --device cpu (keys absent; 33903 /workspace/mfl/out/abs_b8.log).
  Cause NOT diagnosed; (b) candidates: HEAD's FAST-LIVEOPP follow_ups guard / a skipped job (this message = live partner
  + opp_init learner, the reference ran another code base) -- or my change. Keys-on exactness and the fastloop smoke: NOT run.
  Restart: 33903 /workspace/mfl: tree `cb` (mfl_tree.sh from mfl.tar, rebuild the tar from HEAD), `cmp_mfl.sh MSG OUT [args]`
  (CPUs 162-169, FASTLOOP_MEMHASH=1), `smoke_mfl.sh RUN` + `mfl.yaml` (keys on, CPU serve + learner, critic_warmup_updates=0,
  FASTLOOP_DUMP=1 = a real keys-on message whose `init` opponent exercises mixed layouts). Next: (1) find why 16 vs 15
  (print `skipped` from P.run; try a raw non-live B0 message: ref_mem lives on 33308, dump one on 33903 with smoke_mfl.sh
  without the keys); first set cb/icebow/data -> /workspace/icebow_data (cb2's icebow has no b0); (2) keys-absent identity,
  (3) keys-on compare (16 matches, memory tables + mem_h rows + traj keys), (4) smoke. Nothing of mine runs on 33903.
- Step 1 (measure): DONE (section 1). Step 2: Python builder DONE; model / rl_royale / e1_eval / eval_gen / train_memory /
  dataset_gen / live_gen plumbing DONE; Java CfMem + identity harness DONE and identical on 33903; real rl_royale --smoke
  with the keys on: SMOKE PASS on 33903 (pilot.yaml minus fastloop, B0 init, memory_e_max 256, memory_board_snap, encoder
  unfrozen, CPU learner, stored_values off: u0 round trip identical, 2 updates, resume check all True; both updates were
  the critic-only GAE warm-up, so no PPO policy step ran through the widened encoder: (b) untested). Step 3: encoder change DONE (mem_full, zero-init widen, measured on B0); retraining =
  recipe (section 4), NOT run (needs a pod with the pro replay corpora for the snapshot tables).
- Restart: read this file. Laptop tests (53 pass, 4 skip = royalegym-only SIM tests):
  `icebow/.venv/Scripts/python.exe -m pytest pipeline/tests/test_memory_full.py pipeline/tests/test_match_memory.py
  pipeline/tests/test_memory_s1b.py pipeline/tests/test_memory_aux.py pipeline/tests/test_memory_zero_empty.py
  pipeline/tests/test_train_memory.py pipeline/tests/test_learner_fast_cache.py -q -p no:warnings`
- Shared-tree hunks: `memory/full/mem_full_patch.py` holds every plumbing hunk with exact anchors (`apply` = working tree,
  `commit OUTDIR` = origin/main's file + only these hunks; other workers had uncommitted edits in the same files).
- Pod 33903 (CPUs 194-201 only): tree `/workspace/memfull/rl`, scripts `/workspace/memfull/run_id.sh NAME CPUS N [--mem-full 256,1]`
  (identity harness) and `/workspace/memfull/smoke_rl.sh RUN [overrides]` (rl_royale --smoke, CPU learner; the GPU is
  full); results `/workspace/memfull/out/`; smoke run dirs `/workspace/icebow_data/bench/rl_royale/memfull_smoke_on*`
  (mine, deletable). `/workspace/cfspeed/decks.tsv` = mine (top-16 live decks, the census file lived on the dead 32657).
- Checklist:
  - [x] measurement scripts + results (`memory/full/`)  -- commit 76d762e
  - [x] `pipeline/match_memory.py` opt-in e_max / snap + golden pin + tests -- commit 76d762e
  - [x] model_gen `GenModel.mem_full(e_max, snap)` (zero-column widen, `mem.full` buffer only when opt-in, load by content) -- commit after 3ddaa08
  - [x] rl_royale `memory_e_max` / `memory_board_snap` (validated; absent / null / false = historical hash: tested),
        e1_eval `_memory` + `gen_batch`, rl_royale mem row cache key, eval_gen (pro rows: e_max + zero snapshot columns on
        tables without one), train_memory `--e-max` / `--snap`, dataset_gen `memory --snap`, live_gen memory_rows
  - [x] Java CfMem per-instance eMax / snap + obs_id `--mem-full`; identity on 33903 (section 3)
  - [ ] pilot fast loop: WIRED, NOT VERIFIED (top of this section; the spec below is superseded on one point: per-seat layouts).
  - [ ] pilot fast loop (CfTrain / producer.py): memB stride and the MEM views are fixed at CfMem.BYTES / E_MAX / F.
        Spec: `CfTrain.enableMemory(t, eMax, snap)` overload storing memBytes = CfMem.bytes(eMax, snap); every
        `new CfMem(c, u.memT, u.mlog[i], s)` -> the 6-arg form; `features(deck, memB, r * memBytes)`; producer
        `Views.memory` reads eMax / nf / bytes from L (offsets = obs_id JavaMem's formula); producer.loop_mem: all memory
        policies of one JVM must share MM.opts (else NotImplementedError, one memB layout). Then LOOP-INT's identity
        (rec_identity / mem rows) with the keys on. NOT done: untested loop code is not shipped.
  - [x] live_replay.py identity with the options: 1,787 / 1,787 (section 3)
  - [ ] retraining (section 4) + gates: IN PROGRESS, section 5

## 5. MEM-RETRAIN (10-30): tables + warm-start training (restart point)

- Facts that changed the recipe: the replay corpora are ONLY on the laptop (`scratchpad/gauntlet/ext/corpus_*`, ~14 GB; 33903
  has 17 GB free, so they were not copied); `memory_tables` keeps every event (E_MAX only applies at read time), so a snap
  table is not tied to 256. Build on the laptop, ship the npz (25 MB for 3,000 replays). (a)
- Build cost (a): 0.30 s / replay single worker (20 replays, 6.1 s); 3,000 replays with 3 workers 390 s, 25.0 MB, 6,000
  tables, 639,172 events (sha256 b5b3cb99, `.foreman/scratch/memretrain/snap3k.npz`, on the pod `/workspace/memretrain/snap3k.npz`).
  `--limit` = the first N sorted files, so this subset is corpus s0 + part of s1 (a deck-mix bias, same for both encoders);
  the val split comes from the dataset, so its val rows are held out for the old encoder too.
- Code: train_memory `--mem-warm CKPT` (copy mem.* minus mem.out + mem_aux.*, 46-wide ev_in into the first columns),
  `--table-rows-only` (train / val only rows with a table), `--val-bs` (default 512 = as before); test
  `test_warm_start_copies_encoder_and_keeps_snap_columns_zero`. train_memory otherwise refuses an init with mem.* weights, so
  --init stays the RAW net the S3-aux encoder was trained on (u0075, sha 3eda9d23), --mem-warm = B0.
- Pod 33903 (CPUs 146-153 only): tree `/workspace/memretrain/rl` (= memfull tree + HEAD's *.py), runner
  `/workspace/memretrain/run.sh NAME TABLES [train_memory flags]`, outputs `/workspace/memretrain/out/NAME/`.
  Keep `--val-bs 128`: at val bs 512 the process peaked at 5.7 GB (over the 4 GB budget; that run was stopped by PID).

- Result of the short run (s3k_warm, a): warm from B0, 3,000 replays, 638,662 train rows, 2 epochs (4,988 steps), lr 3e-4, val
  bs 128, GPU peak 3,466 MiB, 588 s. Coupling zero, policy identical to base within GPU noise. Same 62,436 held-out rows
  (`memory/full/retrain/cmp_s3k.json`), summed aux loss, old (128) / old256 (B0 weights untrained, full history) / new:
  all 3.8340 / 3.8333 / 3.8306; <= 128 (60,114 rows) 3.8197 / 3.8197 / 3.8190; > 128 (2,322 rows) 4.4031 / 4.3617 / 4.4192.
  > 128 per head old -> new: swing r2 .194 -> .200, commit .478 -> .460, cyc queue_acc .632 -> .636, opp_next .385 -> .379;
  no CI computed, and rk_dmg (22) / xb_lock (2) are too few rows to read. So gate 4 is NOT met on this subset: no measured gain
  on the > 128 rows, and the untrained old256 beats the trained new there. A subset run, not a verdict on the full retrain.
- (a) Feeding B0 the full history did not hurt the aux heads: the 17.6% representation shift cost no aux loss (4.4031 -> 4.3617).
- (b) untested: these aux labels are short-horizon (hand, cycle, next card, next 10 s), so they may not reward 1x-phase events.
  Test: the full-table run below; if > 128 stays flat, add a long-horizon aux target (owner decision, not done here).
- RESULT of the FULL warm run (10-30, MEM-RETRAIN-2, a): tables `snap_full.npz` (sha d6222564, 126,786,699 B; failed [], 29,322 tables,
  rows_with_table 3,517,863) copied to 33903 (sha verified both sides). Run `full_warm` = run.sh full_warm snap_full.npz --epochs 2
  --lr 3e-4 --warmup 500 --val-bs 128: 3,168,599 train rows, 24,754 steps, 2,361 s, GPU 3.46 GB, coupling zero, policy identity
  1.5e-5 (base noise 1.1e-5). Checkpoint 33903 `/workspace/memretrain/out/full_warm/mem_best.pt` (= step 24754, sha 4ea21f0c), laptop
  copy `C:/Users/benpe/pod_backup_weekend/memretrain/full_warm_mem_best.pt`.
  Compare, ALL 349,264 held-out rows with a table (1,459 matches; 337,337 <= 128 events, 11,927 > 128), paired bootstrap over
  matches (1,000 draws; AUC 300), `aux_compare_ci.py` -> `memory/full/retrain/cmpci_full.json`, read with `show_cmp_ci.py`
  (metrics are POOLED per head, not aux_eval's batch mean; point estimates cross-checked against aux_eval: 58 / 58 within 5e-4).
  sum_main = the 10 heads except the sparse rk_dmg / xb_lock (chosen before the run); sum_all = all 12. Loss, old -> new [CI of new-old]:
    overall:  sum_main 3.7052 -> 3.6250 [-0.0839, -0.0767]; sum_all 5.2307 -> 5.1731 [-0.0880, -0.0287]; every one of the other 11 heads
              better with CI excluding 0 (cyc queue_acc .6483 -> .6749, opp_hand auc .9847 -> .9871, opp_next acc .3386 -> .3517, swing r2
              .4721 -> .4815, rk_dmg r2 .168 -> .210); EXCEPTION xb_lock BCE 1.0225 -> 1.0711 [+0.0315, +0.0672] (n = 1,104 elements,
              333 matches; its AUC .6619 -> .6698 [+0.0017, +0.0140] and acc .600 -> .611 [-0.005, +0.027] did not get worse).
    > 128 events (11,927 rows): sum_main 4.3588 -> 4.2950 [-0.0879, -0.0386]; sum_all 5.7125 -> 5.7119 [-0.0972, +0.1024] (flat: the
              two sparse heads, rk_dmg n=145 / xb_lock n=33, carry ~1.35 of it); CI-significant better: swing, vpe, cyc_el, opp_el10,
              opp_el_now, opp_hand, cyc, opp_next; threat/rk_dmg better, CI spans 0; commit worse +0.009 [-0.013, +0.032] (ns); xb_lock
              worse +0.070 [-0.016, +0.170] (ns, 33 elements).
    attribution on > 128 (sum_main): old256 (B0 weights fed the full history) -0.005 [-0.019, +0.008] (= nothing); new128 (the
              retrained encoder fed only 128 events) vs old -0.028; new vs new128 -0.036 [-0.055, -0.017] = the extra history pays, but
              only AFTER retraining; more than half the new-vs-old gain on > 128 is plain retraining / the snapshot.
  Aux gate 4 (as written: every aux metric not worse overall AND better on > 128 OT rows): NOT met literally, because of ONE metric
  (xb_lock BCE overall, +0.049, CI excludes 0; 11 of 12 head-losses improve); the > 128 part is met on sum_main with a CI and
  NOT on sum_all (CI spans 0). Earlier batch-mean number on a 60,000-row sample (cmp_full.json, aux_eval definition, summed): all
  4.0171 / old256 4.0172 / new 3.9433; <= 128 3.9864 / 3.9864 / 3.9119; > 128 (2,100 rows) 5.2453 / 5.2572 / 5.2562 (flat).
  (b) untested: why xb_lock BCE worsens (mem_best is picked by summed val loss on 30k rows; 8,874 train labels, 171 val labels in that
  sample): overconfident calibration with a better ranking; a per-head checkpoint choice or an xb_lock loss weight would be the test.
  Step 3 done anyway (a file only, nothing registered): B0-full = `/workspace/memretrain/out/b0_full/b0_full_clxiii_mem256snap.pt`
  (sha 8ad4cbfa74fb696541e87a59ae57d136c8e4a472f4258c7ae74714c3638ec837; 141 CLXIII tensors unchanged + 51 memory tensors incl.
  mem.full = [256, 1]; builder `memory/full/build_b0_full.py`), laptop copy `C:/Users/benpe/pod_backup_weekend/memretrain/`.
  G-mem-0 (a): vs CLXIII NOLEAK on 10,000 val rows (351 with > 128 events), CPU: max |diff| gate / card / cell / value and the card /
  cell log-probs = 0.0 exactly (< 1e-6). Recipe step 5 (RL) NOT started: needs the lead's pod decision.
  Scripts: `.foreman/scratch/memretrain/cmpci.sh NAME CKPT TABLES [flags]` (CI compare, ~10 min for all val rows, GPU ~3 GB);
  build: `python scratchpad/gauntlet/L74/memory/full/build_b0_full.py --b0 B0 --enc mem_best.pt --clxiii CLXIII.pt --tables TABLES --out OUT`.
- (old) NEXT, now DONE: full tables `.foreman/scratch/memretrain/snap_full.npz` (laptop PID 29472,
  was at 14,600 / 14,661; its meta line lands in `snap_full.json`; check `failed` is empty and rows_with_table = 3,517,863).
  `scp` it to `/workspace/memretrain/snap_full.npz`, then on 33903 (~50 min, b: scaled from 0.1 s / step):
  `cd /workspace/memretrain; nohup bash run.sh full_warm /workspace/memretrain/snap_full.npz --epochs 2 --lr 3e-4 --warmup 500 --val-bs 128 > out/full_warm.log 2>&1 &`
  then `bash cmp.sh full /workspace/memretrain/out/full_warm/mem_best.pt /workspace/memretrain/snap_full.npz --bs 128 --val-sample 60000`
  (read with `.foreman/scratch/memretrain/show_cmp.py`), then recipe steps 3-5 of section 4.
  Copies of run.sh / cmp.sh: `.foreman/scratch/memretrain/`. Checkpoint: `/workspace/memretrain/out/s3k_warm/mem_best.pt`.
- Codex dispatches: none.

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

- CfMem.java: per-instance `eMax` / `snap` (new constructor `CfMem(core, T, log, seat, eMax, snap)`; the 4-arg one = 128 /
  off), instance row layout `offMask .. bytes` (= the static OFF_* / BYTES at the defaults), `CfMem.bytes(eMax, snap)`,
  `snapshot(i)` = MatchMemory._snap (same sample, same body order, same value rule `value()`), F_SNAP-wide `table()`.
- obs_id.py (the LOOP-MEM identity harness): `--mem-full E,SNAP` widens the memory model (`mem_full`), JavaMem builds its
  CfMem with the model's `MM.opts`, views at the instance layout, the learner-rebuild check passes the rollout's e_max.
- Identity on pod 33903 (CPUs 194-201, tree `/workspace/memfull/rl` = 76d762e pipeline + these hunks, B0 =
  `/workspace/icebow_data/bench/rl_royale/b0/b0_clxiii_s3aux_grafted.pt`, crforge 5e8089a4, 2 census matches, decks =
  the top-16 live decks, `/workspace/cfspeed/decks.tsv` made from memory/decks_live_train_beat3_cx3.json):
  - absent (defaults, modified Java + Python): all 29 row keys IDENTICAL on 1,674 seat-rows, 4 / 4 tables identical in
    all 12 TABLE_KEYS, learner rebuild 1,674 / 1,674 (a) (`out/smoke_default.json`).
  - `--mem-full 256,1`: the 6 MEM keys IDENTICAL Java vs Python on 1,674 seat-rows (mem_ev 256 x 70), 4 / 4 tables
    identical (vals 70 wide), snapshot columns nonzero on 5.9k-51.8k rows each (a) (`out/smoke_full.json`); learner
    rebuild 1,674 / 1,674 (a; the first run showed 0 / 1,674 because the HARNESS rebuilt at e_max 128 -- fixed in obs_id; production gen_batch / the row cache pass the model e_max).
- Live path: `live_gen.GenPilot.memory_rows` builds `MatchMemory(side, **MM.opts(model.mem))`: a checkpoint without
  `mem.full` (CLXIII, every current model) = the defaults = unchanged (a: code; the opts of a model without the buffer are
  128 / off, test_empty_rows_and_opts). Live play itself is not touched (no live_play / LIVE_OPTIONS change).
- Live-path identity with the options (a): `MEMFULL=256,1 research/ext/Royale/.venv/Scripts/python.exe -B -X utf8
  scratchpad/gauntlet/L74/memory/live_replay.py LOGS` (live_replay.py: env MEMFULL gives its GenPilot a model whose mem
  carries e_max / snap; the reference = MM.build with the same options) on 4 live logs of 10-30 (3 with 151-170 events,
  1 with 51): **1,787 / 1,787 decisions identical** (live GenPilot.memory_rows vs the offline build), features_at(table)
  1,787 / 1,787 (`.foreman/scratch/memfull_live_replay.out`). Defaults on the same logs: 1,787 / 1,787 too.
- Live cost (a, laptop CPU, same 4 logs): memory_rows median 1.93-2.23 ms with 256 + snap vs 1.37-1.50 ms at the
  defaults on the 150+-event matches (p90 4.3-4.7 vs 3.4-3.6 ms); the 51-event match 1.10 vs 0.97 ms. Small next to the
  ~100 ms live decision.

## 4. Encoder: what the S3-aux encoder needs, and the retraining recipe

**What it needs to accept the longer history and the snapshot (a, code + measurement):**
- No new parameter for the length: MemoryEncoder has no positional embedding (time enters as the `ago_60` / `t_300`
  fields), padding is masked in attention, mean and pool. `model_gen.GenModel.mem_full(e_max, snap)` = the whole change:
  `snap` widens `mem.ev_in` 46 -> 70 inputs with the new 24 columns at ZERO (old columns copied), `mem.cfg[0]` = 70, buffer
  `mem.full` = [e_max, snap] (absent = the state dict unchanged); load builds it by content (test_mem_full_widen_is_identity_at_init).
- B0 measured (memory/full/widen_b0.py, laptop CPU): histories <= 128 events: max |mem.rep diff| 3.6e-7 (float noise of
  the longer padded tensor, not bit-identical); policy outputs bit-identical at u0 because B0's coupling mem.out is 0.
  Histories > 128 events (129 rows): mem.rep moves by 17.6% (L2, mean; max 23.3%) -- the frozen encoder now pools over
  events it never saw at training (masked mean over up to 256 events, a longer-than-trained input). (a)
- Consequence: with `memory_encoder_frozen: true` the long-history OT rows get an OUT-OF-DISTRIBUTION representation (b:
  harm untested; the coupling would have to learn on it). The pilot now runs `memory_encoder_frozen: false` (owner 10-30),
  so RL can adapt the encoder, but the aux heads (memory_aux v1) were fit on <= 128 events and on no snapshot. Hence:

**Retraining recipe (S3-aux v1 recipe, ONE change: full memory; train_memory flags `--e-max` / `--snap` added):**
1. Pro tables with the snapshot: `python -m pipeline.dataset_gen memory --dataset icebow/data/pipeline/gen_dataset_v32_fv5.npz
   --out icebow/data/pipeline/gen_dataset_v32_fv5_memory_v1_snap.npz --workers N --snap` (the 10-25 build: 14,661 replays;
   a pod with the replay corpora; laptop test first with `--limit 20`).
2. Encoder from scratch with the S3-aux targets unchanged (AUX_OWN swing / vpe / cycle classes / cycle elixir per own deck
   card, opponent in-hand, opponent next card, AUX_GLOB opp_el10 / opp_el_now / threat / commit / xb_lock / rk_dmg; the
   labels are built from the same tables, causal): `python -m pipeline.train_memory --init <CLXIII NOLEAK> --memory v2
   --memory-tables <snap tables> --trainable memory_encoder --aux v1 --zero-empty --e-max 256 --snap --out-dir ...`
   (other flags as the 10-25 S3-aux run: lr 1e-3, bs 256, 2 epochs; check the S3-aux run's args in its checkpoint meta).
3. Graft into B0 the way build_b0.py did (CLXIII tensors unchanged + the new mem.* / mem_aux.* tensors, coupling 0) ->
   B0-full. Gate G-mem-0: B0-full vs CLXIII log-probs on 10k recorded rows (< 1e-6; coupling 0 makes it exact).
4. Aux gates vs the 128 encoder on the SAME val rows: every aux metric not worse overall, and better on OT rows with >
   128 events (the rows the old window truncated: 17.2% of pro OT decisions) -- that is where the full history must pay.
5. RL: pilot recipe + `memory: v2, memory_aux: v1, memory_encoder_frozen: false, memory_zero_empty: true,
   memory_e_max: 256, memory_board_snap: true`, init B0-full; then the memory ablation gate (real vs shuffled memory,
   paired, CI low > 0) and the usual SIM gate vs CLXIII.
- Cheaper alternative if the pro rebuild is blocked: start RL from B0 widened (`memory_e_max: 256, memory_board_snap:
  true` on the B0 init) -- identical policy at u0, snapshot weights at zero, the unfrozen encoder learns both from RL only
  (b: slower credit than aux pretraining; the aux heads still train beside it with memory_aux v1).

## Ledger of Codex dispatches

None. The measurement scripts, hunks and identity runs were short and decided semantics (layouts, causality, identity); no menial bulk task came up that Codex would have saved usage on.
