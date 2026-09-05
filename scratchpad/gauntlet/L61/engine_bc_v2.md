# L61 -- BC dataset v2: pro placements with boards from the REAL CR engine (cr-native-sandbox)
Started 2026-09-05 10:24. Every number MEASURED on this box unless marked otherwise.

## Setup
- RAM before boot: 10191 MB free / 32164 total; qemu not running; crosvm procs (not ours, ~1.4 GB WS) present.
- Boot: scratchpad/gauntlet/ext/svc_start4.ps1 (6-attempt retry) started 10:24:54 -> log scratchpad/gauntlet/L61/service_start.log
- Boot result: attempt 1 (10:24:55) failed the flaky DataTables step, attempt 2 (10:30:53) ready 10:31:09, `"ready": true` port 37031, exit=0.
  qemu-system-x86_64-headless PID 66092, working set 3.6 GB during boot.

## A. Engine recording at pro-deploy ticks
- Code: `scratchpad/gauntlet/L61/replay_drive_rec.py` (copy of research/sandbox_tools/replay_drive.py + `record_plays`: a FULL
  `env.observe()` immediately BEFORE every driven play of both sides -- same tick, before the `act` -- stored in
  `play_frames` with play_index/side/card/x/y + both players' elixir/hand/hand_pos/cycle_pos/next; plus the existing
  `record_every=20` compact drift frames) and `replay_batch_rec.py` (211 §5ay-converted tags, resumable, writes
  `scratchpad/gauntlet/ext/batch_v2/replay_<tag>.json`, `summary.jsonl`, `aggregate.json`; each tag's final `state_hash`
  compared with the §5ay batch hash for that tag).
- The original driver already did an `observe_compact()` before each play (hand/elixir check), so the recording is a
  read-only change: full observe instead of compact.
- Smoke, 5 tags: hash_same_as_v1 5/5, accepted_same_as_v1 5/5, 1.28-2.7 s/match (median 1.75; v1 median for the same
  5: 2.1 s -- warm service, no measurable recording cost at this granularity).
- FULL BATCH (10:36:50-10:44:23): 211/211 ok, **hash_same_as_v1 211/211**, accepted_same_as_v1 211/211 (17757/17901
  accepted), crowns_match 164/211 (identical to §5ay), 17901 play frames + 62767 drift frames, 74 MB json.
  Wall time WITH recording: median 2.34 s/match (min 0.6, max 3.2, mean 2.19; total 462 s for 211 = 2.19 s/match
  = 1640 matches/h on one slot). §5ay without per-play recording: median 3.54 s -- the v1 batch included cold-service
  time; recording cost is below the noise. Full observe = ~20 ms x ~85 plays = ~1.7 s/match upper bound, i.e. most of a
  match's wall time IS the observes (see D).

## D. Throughput (one replay 000YLY0JCPGL, 123 plays, 6085 ticks = 304 s of match; batch params slack 40 / tail 7200)
Code `scratchpad/gauntlet/L61/throughput.py`; every run's final hash = the batch hash d0874ff2026fa69e (recording
granularity and concurrency do not perturb the engine). Per-match wall (s), 3 reps each, one process on port 37031:
| observe cadence | wall s (min..max) | frames | matches/h |
| plays only (full observe before each of 123 plays) | 1.22..1.58 (med 1.27) | 0 | ~2800 |
| every 10 ticks (compact) + plays | 3.67..3.97 (med 3.92) | 661 | ~920 |
| every 2 ticks (compact) + plays | 13.79..14.04 (med 13.83) | 3067 | ~260 |
- Marginal cost per drift frame (step chunk + observe_compact + python snapshot): (3.92-1.27)/661 = 4.0 ms; every-2:
  (13.83-1.27)/3067 = 4.1 ms. So one extra observe+step costs ~4 ms wall regardless of cadence.
- Raw RPC latency (100 calls, live match after 600 ticks, nearly empty board, direct transport): observe_compact
  median 1.6 ms (p90 2.6), observe_full 2.0 ms (p90 3.4), step(1) 1.7 ms, step(10) 2.0 ms, step(20) 2.0 ms.
  (Earlier "~20 ms per observe" in §5ay/HANDOFF was the adb transport / cold numbers; direct is ~2 ms.)
- VM RAM: qemu-system-x86_64-headless working set 3.6 GB at boot, 3.8 GB with one service, 4.26 GB with two
  services (-memory 4096 AVD).
- Second worker on the same VM: `worker start --workers 2 --base-port 37031` reused the VM and slot 0, started slot 1
  (port 37032, host 38032) first try (10:47, 25 s). Two drives concurrently (one per slot), 3 reps each:
  plays-only 1.44..1.73 s (vs 1.27 alone: +15..20%), every-10 4.65..4.85 s (vs 3.92: +20%). Both hashes = batch hash.
  Aggregate: 2 matches / 4.75 s = 1516 matches/h at every-10 vs 920/h for one slot (1.65x), 4650/h vs 2800/h for
  plays-only. Contention is mild (the AVD has 4 cores; each service is single-threaded in the engine).
- Stopped 10:51: `worker stop --workers 2 --stop-vm` -> services stopped, vm_stopped true; qemu process gone, `adb
  devices` empty.

## B. Engine frame -> policy obs adapter, dataset v2
Code `scratchpad/gauntlet/L61/build_bc_v2.py` (stages assemble / baseline / pack / report; reuses L60's
`stage_baseline`, `_write_npz_streamed`, `engine_queue`, `key_base`). Output `icebow/data/bc_pro_v2/` (dataset.npz
3.8 MB compressed, meta.csv, split.json, name_stats.json, report.txt, drive_summary.jsonl, shards/, models/).
- Adapter: each play frame (full observe BEFORE the pro's deploy at the play's tick) -> `FakeEngine` {t = tick*0.05,
  units = FakeUnit(sim CardSpec via `build_spec(db, key, 11)`, team, x, y, hp, deploy_left>0 iff engine kind 12/14),
  towers[team] = [L, R, king] real sim `Tower` objects at the engine's positions/hp (a tower missing from the engine
  list = destroyed: hp 0, alive False, at the sim anchor), elixir[me, them]}; it is swapped into a real `SimMatchEnv`
  (`env.eng = fake`) and `env._update_vectors()` runs the unchanged pipeline (hand/next/elixir/threat vectors, canvas
  stack, semantic + predictive channels). Geometry verified: transformed engine towers land exactly on the sim's
  (0.194,0.797)/(0.806,0.797)/(0.5,0.906) for me and the mirror for them. Mirror = L51 (engine side 1 = blue = icebow
  -> sim team 0 = bottom: x->18000-x, y->32000-y, sides swapped; sim x=X/18000, y=1-Y/32000).
- Temporal state (canvas stack decay, threat memory) is driven by the every-20-tick drift frames (agent_dt = 1.0 s)
  plus an update right before each focus play (agent_dt = time since the previous update) -- same cadence idea as v1's
  0.6 s ticks, coarser. Hand/cycle: v1 rule (engine deal queue -> `env.cycle`, `_play_slot` after each focus play, evo
  charge rule) and cross-checked against the engine's own hand in every play frame: hand_checked 9521, mismatch 81
  (0.85%; v1 had 48 mismatched rows of 6922). hand_source engine for 213/213 drives.
- Sample = engine-ACCEPTED focus play (17757/17901 accepted overall; icebow-side plays 9521 frames -> 9444 samples;
  77 icebow plays the engine rejected are dropped, they still advance the cycle). Cell label = nearest
  `actions.cell_center` (snap mean 0.383 tiles, max 0.833), acts = (card_id, gx, gy) as v1.
- Name mapping (engine display name = catalog internal name -> sim cards.yaml key): inverse of replay_drive
  SLUG_ALIASES + CamelCase->snake. 101 distinct entity names seen, **101/101 mapped, 0 unmapped, 0 samples dropped
  for mapping**; a generic knight spec fallback exists but was never used. Non-trivial pairs (count of appearances):
  MiniSparkys->zappies, SkeletonBalloon->skeleton_barrel, DarkWitch->night_witch, Archer->archers,
  BarbLog->barbarian_barrel, Ghost->royal_ghost, WitchMother->mother_witch, IceGolemite->ice_golem,
  FirespiritHut->furnace, MovingCannon->cannon_cart, SkeletonWarriors->guards, AxeMan->executioner,
  BlowdartGoblin->dart_goblin, IceSpirits->ice_spirit, RageBarbarian->lumberjack, ZapMachine->sparky,
  "Elixir Collector"->elixir_collector, Assassin->bandit, FireSpirits->fire_spirit, Heal->heal_spirit,
  DartBarrell->flying_machine, EliteArcher->magic_archer, MergeMaiden_Mounted->spirit_empress_air. Full table in
  `icebow/data/bc_pro_v2/name_stats.json`. Not represented at all: spells in flight (engine has them only as
  projectiles/effects, 5626/9444 frames have >=1 effect; the sim's obs has no spell channel either).
- Counts: **9444 samples** (v1: 6922) from 211 replays / 213 drives (2 replays are icebow-vs-icebow -> both sides,
  86 side-0 rows). Cards: skeletons 1543, ice_wizard 1481, the_log 1387, knight 1106, tesla 933, x_bow 827, tornado
  770, rocket 571, knight_evo 446, tesla_evo 380. Time: median 162 s, buckets 0-60 1406 / 60-120 1447 / 120-180 2661 /
  180+ 3930 (v1 was front-loaded because the sim ended matches early; 3726 v2 rows have no v1 partner).
- Split: v1 split.json restricted to converted tags: 178 train tags / 8111 rows, 33 val tags / 1333 rows (v1: 228/5918,
  40/1004). v1 val tags NOT converted (7): 000YLP22V2QU 000YLY2V9Q0V 020YPYL90Q82 020YPYYQJ888 022YYQ20UGU0
  02JY9G088VPU 02JY9GYGR9GG. No tag outside v1's split.
- Per-sample extras in meta.csv: engine tower HPs (tw_me_L/R/K, tw_them_L/R/K), eng_elixir_me/them, tick, n_units_me/
  them, n_deploying, n_projectiles, n_effects, and the v1 pairing (v1_row, d_units_me/them, towers_agree, d_elixir).
- v1-vs-v2 board difference at the SAME play (5718 paired of 9444; v1 counted units after its deploy, so the played
  card's body count is added to v2's before-count): d_units_me mean -0.14 (|d| 0.52; equal 3504, v2 fewer 1376, v2
  more 838); **d_units_them mean -0.74 (|d| 1.09; equal 3027, v2 fewer 2110, v2 more 581)** -- the sim keeps ~0.7
  more enemy bodies alive than the real engine at the moment of the pro's play; towers-alive agreement 70.7%;
  elixir v2-v1 mean +0.16, |d| 0.27, p90 0.86, >2 in 0.9%.

## C. Scoring on v2 (val = 1333 rows / 33 tags; `scratchpad/gauntlet/L61/knn_vs_bc_v2.py`, models in bc_pro_v2/models/)
| method | v2 val top1 / top5 | v1 val (1004 rows) |
| c2r_best_36k_backup (masked cell map) | **2.78 / 11.10** (per-card: log 10.8/41.8, skel 2.7/7.6, iwiz 2.4/6.7, knight 1.9/4.4, tesla 1.6/3.9, xbow 0.0/0.0, nado 0.0/5.2, rocket 0.0/13.5; time 0-60 4.4/10.7, 60-120 3.5/11.0, 120-180 1.9/9.4, 180+ 2.5/12.5) | 3.49 / 11.75 |
| per-card cell histogram prior (train) | **12.08 / 37.66** | 13.65 / 40.04 |
| kNN raw-PCA-256 k=15 gauss | **14.03 / 37.28** (k15 hard 14.25/40.21; k50 hard 15.38/44.49; k150 hard 14.70/45.46) | 16.24 / 36.16 |
| kNN fmap k=15 gauss | 15.60 / 36.61 | 15.94 / 33.76 |
| global cell histogram | 4.05 / 17.48 | -- |
- Paired apples-to-apples (865 v2 val rows that have a v1 partner): c2r_best top1/top5 3.12/10.75 on the engine
  board vs 3.35/11.33 on the sim board for the SAME plays; the checkpoint picks the same top-1 cell on both boards in
  58.6% of them. Over all 5718 paired rows: 3.53 (v2) vs 3.32 (v1). => the checkpoint's near-prior performance is not
  an artefact of the sim board; it is equally bad on the real engine's board.
- kNN/prior on v2 are 1-2 points below v1 on top-1, but the val sets differ (v2 val has 468 rows past 180 s with no
  v1 partner, where the checkpoint gets 2.35 top-1) -- do not read the gap as "engine boards are harder".
- ck_top1 histogram: cell 235 predicted 2422/9444 times, 423 1445, 374 1214 (same collapse as v1).
- rawcos (full-Gram eigh) skipped at n=9444 (>9000 guard); baseline `agree` with meta ck_hit1: 1332/1333.

## Not done / caveats
- kNN and prior were not re-scored on the paired subset (only the checkpoint was); v1-vs-v2 kNN numbers are on
  different val row sets.
- The adapter's temporal channels are fed at 1.0 s cadence (every-20-tick drift frames), v1 used 0.6 s; canvas decay
  differs slightly. A denser recording (every 10 ticks costs +2.6 s/match, see D) would close that.
- Spells in flight / projectiles are not rendered (neither dataset has a channel for them); n_effects/n_projectiles
  are in meta.csv for a later channel.
- rawcos kNN variant skipped (n=9444 full Gram eigh guard).
- Nothing committed; `scratchpad/gauntlet/ext/batch_v2/` (74 MB) is outside git as instructed.

## Files
- scratchpad/gauntlet/L61/: engine_bc_v2.md, replay_drive_rec.py, replay_batch_rec.py, run_batch.ps1, batch_rec.log,
  build_bc_v2.py, knn_vs_bc_v2.py, throughput.py, run_tp.ps1, tp_single.log, tp_seq.log, tp_conc_a.log, tp_conc_b.log,
  throughput_*.json, svc_slot2.ps1/log, service_start.log
- scratchpad/gauntlet/ext/batch_v2/: replay_<tag>.json x211, summary.jsonl, aggregate.json
- icebow/data/bc_pro_v2/: dataset.npz, meta.csv, split.json, name_stats.json, report.txt, drive_summary.jsonl, shards/, models/

STATUS: complete
