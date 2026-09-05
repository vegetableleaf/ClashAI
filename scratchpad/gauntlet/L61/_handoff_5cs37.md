
### §5cs.37 -- L61 (2026-09-05 14:2x-15:0x UTC): BC DATASET v2 FROM THE REAL ENGINE (9,444 pro plays, boards observed by cr-native-sandbox at the deploy tick, 211/211 hash-identical drives) -- the checkpoint is equally bad on real boards (paired 3.12/10.75 engine vs 3.35/11.33 sim: NOT a sim-board artefact); the sim-trained prior-bias-map heads TRANSFER to engine boards (15.00/43.51, 14.63/44.11, 14.93/43.44 vs the v2 prior 12.08/37.66, +2.6-2.9 top-1 ~3 SE, +5.8-6.5 top-5 ~4.5 SE); engine throughput: 2,800 matches/h/slot plays-only, 920/h at a 0.5 s observe cadence, 1,516/h with 2 slots on one 4.3 GB VM (vs the sim's ~2,880/h on 16 cores, §5cs.35's 0.8 ep/s)

Source: `scratchpad/gauntlet/L61/engine_bc_v2.md` (agent, STATUS complete) + `rescore_bias_v2.py/.json` (this
loop). Code: `L61/replay_drive_rec.py`, `replay_batch_rec.py`, `build_bc_v2.py`, `knn_vs_bc_v2.py`, `throughput.py`.
Recordings `scratchpad/gauntlet/ext/batch_v2/` (74 MB, outside git); dataset `icebow/data/bc_pro_v2/` (outside git).
(a) throughout unless marked.

**A. Recording.** Full `observe()` immediately before every driven play of both sides (same tick, before the act)
+ a compact frame every 20 ticks, on the 211 §5ay-convertible replays. **211/211 final state hashes identical to
§5ay**, accepted 17,757/17,901 (same), crowns-match 164/211 (same) -- recording does not perturb the engine. 17,901
play frames + 62,767 drift frames. Wall WITH recording median 2.34 s/match (mean 2.19; 462 s for 211) -- §5ay's
3.54 s included cold-service time; recording cost is below noise. Boot: attempt 1 died in the DataTables step,
attempt 2 ready at 10:31 local (the ~1-in-3 flake, §5ay).

**B. Adapter -> obs.** Engine frame -> duck-typed `FakeEngine` (sim `CardSpec` units via `build_spec`, REAL sim `Tower`
objects at the engine's positions/hp, elixir, t) swapped into a real `SimMatchEnv`; the unchanged `_update_vectors()`
renders the policy obs. Tower geometry exact; mirror = L51 convention. Temporal channels fed by the 1.0 s drift frames
(v1: 0.6 s sim ticks). Name mapping 101/101 engine entity names -> cards.yaml keys, 0 samples dropped (table in
`bc_pro_v2/name_stats.json`); hand cross-check vs the engine's own hand 81/9,521 mismatches (0.85%). **9,444 samples**
(v1 6,922) from 211 replays; 3,726 rows have no v1 partner (past the sim's early end); time buckets 0-60 1,406 /
60-120 1,447 / 120-180 2,661 / 180+ 3,930. Split = v1's split.json restricted: 178 train tags / 8,111 rows, 33 val
tags / 1,333 rows (7 v1 val tags not convertible). Spells in flight are not rendered (no channel in either dataset;
`n_effects`/`n_projectiles` kept in meta.csv).
- **Sim vs engine board at the SAME play (5,718 paired):** enemy units v2-v1 mean **-0.74** (v2 fewer in 2,110, more
  in 581, equal 3,027) -- the sim keeps ~0.7 more enemy bodies alive at the pro's deploy moment; own units -0.14;
  towers-alive agreement 70.7%; elixir v2-v1 +0.16 mean, >2 in 0.9%. This is the first per-play board-level parity
  number (§5ay's 26% was crowns/state-hash level).

**C. Scores on v2 val (1,333 rows / 33 replays; masked cell map, same convention as §5cs.34):**
| method | v2 (engine) top-1 / top-5 | v1 (sim, 1,004 rows) |
|---|---|---|
| c2r_best | **2.78 / 11.10** (x_bow 0.0/0.0, tornado 0.0/5.2) | 3.49 / 11.75 |
| per-card prior (v2 train) | **12.08 / 37.66** | 13.65 / 40.04 |
| kNN raw-PCA-256 k=15 gauss | 14.03 / 37.28 (k=50 hard 15.38 / 44.49) | 16.24 / 36.16 |
| kNN fmap k=15 gauss | 15.60 / 36.61 | 15.94 / 33.76 |
| global cell histogram | 4.05 / 17.48 | -- |
| **bias-map heads trained on v1 (sim boards), scored on v2 (engine boards), s0/s1/s2** | **15.00 / 43.51, 14.63 / 44.11, 14.93 / 43.44** | 15.44 / 46.61, 16.24 / 46.41, 15.14 / 46.51 |
| coord+bias s0 / bias-only (convs frozen) s0 | 14.63 / 43.74 / 12.15 / 37.81 | 15.54 / 46.91 / 12.75 / 40.94 |
| the trained bias map ALONE (no convs) on v2 | 10.58 / 37.21 | -- |
- **Paired apples-to-apples (865 v2 val rows with a v1 partner): c2r_best 3.12 / 10.75 on the engine board vs
  3.35 / 11.33 on the sim board for the same plays**, same top-1 cell on 58.6%. (a) The checkpoint's near-nothing pro
  agreement is not an artefact of the sim boards -- it is board-blind on the real game too. Top-1 histogram: cell 235
  x2,422 of 9,444, 423 x1,445, 374 x1,214 (same collapse).
- v1-vs-v2 gaps for prior/kNN (-1.5 / -2.2 top-1) are on DIFFERENT val row sets (v2 has 468 rows past 180 s where the
  checkpoint gets 2.35); do not read them as "engine boards are harder".
- **Transfer (this loop, `rescore_bias_v2.py`):** the three §5cs.36 bias-map heads, trained only on sim boards, beat
  the engine-board prior by +2.6..+2.9 top-1 (SE ~0.9 at n=1,333 -> ~3 SE) and +5.8..+6.5 top-5 (~4.5 SE), with no
  retraining; x_bow 31-34% top-1 / 70-72% top-5 (c2r_best 0/0). The trained map alone scores 10.58 -- BELOW the v2
  prior -- so the convs contribute +4.4 top-1 on real boards; the head is not just carrying the prior. Reading: the
  cell head trained on our sim's boards generalises to the real engine's boards for this deck; the -0.74 enemy-body
  gap did not break it. (b) Whether training on v2 itself is better is untested (one `bc_coord.py` run on
  `bc_pro_v2`, ~5 min).

**D. Throughput (one 6,085-tick replay = 304 s of match, 123 plays, 3 reps each; every run's hash = the batch hash):**
| cadence | s/match (median) | matches/h/slot |
|---|---|---|
| plays only (123 full observes) | 1.27 | ~2,800 |
| compact observe every 10 ticks (0.5 s) + plays | 3.92 | ~920 |
| every 2 ticks (0.1 s) | 13.83 | ~260 |
Marginal cost ~4.0 ms per step-chunk+observe at any cadence. Raw direct-transport RPC: observe_compact 1.6 ms,
observe_full 2.0 ms, step(1..20) 1.7-2.0 ms median (the "~20 ms/observe" in §5ay was adb/cold -- **retracted**, direct
is ~2 ms). VM: qemu working set 3.6 GB boot, 3.8 GB one service, 4.26 GB two. Second slot on the same VM started
first try; two concurrent drives +15-20% per match, both hashes correct: **1,516 matches/h at every-10 (1.65x one
slot)**, 4,650/h plays-only. Comparison instrument-aware: the sim trainer ran 0.8 ep/s = ~2,880 matches/h on 16 cores
(§5cs.35, incl. policy inference + PPO); the engine number excludes policy inference and the opponent. So the real
engine at a 0.5 s decision cadence is ~1/2 of the sim's match rate per VM, at 100% parity instead of 26%; a second VM
(RAM 4.3 GB each, 7-10 GB free) is (b) untested. VM stopped 10:51 local (`worker stop --workers 2 --stop-vm`; no
qemu, `adb devices` empty).

**What this settles / does not.**
- (a) The IL bar on real boards is 12.08 / 37.66; the prior-bias-map head clears it without retraining. The model
  change (`cells + cell_bias_map[None]` before the tanh cap, 4,320 floats) is now supported on both datasets.
- (a) Engine-as-environment is throughput-feasible (~920-1,516 matches/h). NOT solved: the OPPONENT. The sandbox
  drives both sides from replay commands; a training environment needs something on the other side -- (i) replay
  "ghost" opponents (268 pro timelines, non-reactive: once the policy deviates, the ghost's later plays no longer
  fit the state), (ii) self-play (2x inference, from a head that is currently collapsed), (iii) a scripted bot.
  That is a design decision that changes what the experiment means -> owner question (L61 report).
- (b) Training the bias-map head on v2 instead of v1; two VMs; every-10 vs plays-only cadence for the temporal
  channels (1.0 s drift frames vs v1's 0.6 s -- canvas decay differs slightly).
- Trap: `observe()` cost depends on transport -- adb ~20 ms, direct ~2 ms; never quote the adb number for a
  training-throughput estimate.
