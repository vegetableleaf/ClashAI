# L64 rescore_old -- the OLD imitation init on the NEW S1 corpus (one instrument)

Old model: icebow/data/bc_pro/models/bc_bias_native_s0.pt (clashrl PolicyNet, 432-cell head).
New data: scratchpad/gauntlet/ext/corpus_v3/icebow/replay_*.json val replays (crc32(tag)%100 < 15), play_frames.
Driver: scratchpad/gauntlet/L64/rescore_old.py (reuses build_bc_v2.assemble_tag + knn_vs_bc_v2.forward_all/score unchanged).

## 1. What the old model consumes (read from build_bc_v2.py / knn_vs_bc_v2.py)

- Input = 5 tensors rendered by the SIM env's own observation pipeline (clashrl SimMatchEnv with its engine swapped for a
  FakeEngine built from the engine frame): obs uint8 [96,64,12] (12-channel canvas, /255 at forward), hand_vec, next_vec,
  elixir_vec, threat_vec (from env._update_vectors, agent_dt = tick gap since the previous frame/play).
- FakeEngine from each play frame (the FULL obs before the play): entities [side,x,y,name,hp,max_hp,kind] -> FakeUnit with a
  sim CardSpec (engine display name -> cards.yaml key via _ALIAS_INV / CamelCase->snake; unknown names get a generic knight
  spec; hp<=0 and name "-1" dropped; kind 12/14 = deploying); towers list -> sim Tower objects (missing tower = destroyed
  anchor); elixir[focus], elixir[other]. Drift frames (every 20 ticks) are ALSO fed so the threat/canvas state evolves.
- Side convention: focus side = sim team 0 = "me" = BOTTOM. Engine side 1 is mirrored (x->18000-x, y->32000-y);
  sim x = X/18000, sim y = 1 - Y/32000 (identical to pipeline/obs_contract._engine_xy).
- Hand/next: the sim's cycle model seeded from deal_probe.canonical (hand_pos+cycle_pos) and advanced by env._play_slot on
  every driven play; if the played card is not in the modelled hand it is forced to the front (hand_mismatch counter).
- Pro cell label: the play's (x,y) in the same frame -> NEAREST of the 432 ActionSpace cell centres (18 wide x 24 tall,
  distance in tiles); cell = gy*18 + gx.
- score(): cell logits for the PRO's card only (net._cell_logits(...)[card]), tanh-capped 8*tanh(l/8), masked to
  ActionSpace.deployable_mask(anywhere_card, pocket_state) with -inf; top-1 = argmax == pro cell, top-5 = pro cell in top 5.
  Conditional on the play (no gate), card given.

## 2. Old init scored on the S1 val plays (a) measured -- summary lines in scratchpad/gauntlet/L64/rescore_old_summary.txt

Rows: 3,796 play rows from 85 val replays / 86 (tag,side) drives (one mirror match: both sides icebow). This is EXACTLY the
S1 dataset's val play-row count, and every (tag, side, tick) key matches 1:1 (only-new 0, only-old 0); the pro xy label agrees
between the two builders to max |d| 0.00005 (both use x/18000, 1-y/32000 with the side-1 mirror). Nothing dropped by me:
23 focus-side play frames were not `accepted` by the engine and are excluded by BOTH builders (3,819 -> 3,796). Hand model:
all 86 drives seeded from deal_probe (hand_source engine); hand_match_engine=1 on 3,790/3,796 rows (6 forced).

- (a) old init on S1 val, 432 grid, pro card given, deployable-masked, no gate:
  **top-1 13.70% / top-5 41.73%** (n 3,796). Side 0 (n 60) 26.67/51.67, side 1 (n 3,736) 13.49/41.57.
  Per card: skeletons 9.1/29.3 (624) ice_wizard 10.9/35.9 (607) the_log 21.1/52.2 (536) knight 10.7/39.1 (450)
  tesla 16.7/56.3 (389) x_bow 30.5/75.4 (325) tornado 6.4/20.8 (312) rocket 10.5/40.2 (219).
  Per time: 0-60 s 19.6/54.7 (591) 60-120 15.4/48.2 (570) 120-180 13.9/39.6 (1,088) 180+ 10.7/35.9 (1,547).
- (a) sanity, same code path on the old model's OWN v2 val (1,333 rows): **15.00 / 43.51** -- reproduces read_ckpt exactly.
- (a) LEAKAGE: 37 of the 85 S1-val replays (1,724 of 3,796 rows) were in the OLD model's TRAIN split
  (bc_pro/split.json train_tags; S1 uses a different split rule). On those rows the old init scores 14.39/42.00; on the
  **2,072 CLEAN rows (never seen by the old model): 13.13 / 41.51** at the 432 grid. Use the clean subset (preds
  `in_old_train == 0`) for any comparison that must be fair to the new model.
- (a) 175/3,796 pro cells (4.6%) lie OUTSIDE the deployable mask the old instrument scores under (the plain live-screen
  ActionSpace(cfg) mask, as in knn_vs_bc_v2.load_all) -- guaranteed misses; same handicap as in the 15.00/43.51 number.

## 3. Per-play file: scratchpad/gauntlet/L64/rescore_old_preds.npz (n = 3,796, row order = sorted shard files, i.e. by tag then side)

| key | shape / dtype | meaning |
| --- | --- | --- |
| tag, play_index, side, tick | [n] str / int | replay tag, engine play_index, engine side of the pro (0/1), engine tick of the play frame |
| card_id, card_key | [n] | old policy's card id (0..7 + evo ids) and key (knight_evo / tesla_evo appear as separate keys) |
| seconds, hand_match_engine, in_old_train | [n] | tick*0.05; 1 = modelled hand == engine hand; 1 = replay was in the old model's TRAIN split |
| pro_engine_xy | [n,2] int32 | the pro's RAW engine (x, y), unmirrored, 1000/tile |
| pro_frame_xy | [n,2] f32 | the same in the NEW convention: [0,1], me at bottom (== s1_dataset y_xy to 5e-5) |
| pro_cell432 | [n] | pro's label on the old 432 grid (nearest cell centre in board space) |
| argmax_cell432, argmax_frame_xy | [n], [n,2] | old model's masked argmax cell and its centre in the NEW convention |
| probs432 | [n,432] f32 | old model's full masked softmax over the 432 cells (0 outside the mask) |
| mask432 | [n,432] bool | the deployable mask used (anywhere card x pocket state) |
| cell432_centers | [432,2] f32 | cell -> board-frame centre, cell = gy*18+gx; x pitch 1.000 tile, y pitch 1.333 tiles |
| hit1, hit5 | [n] int8 | 432-grid top-1 / top-5 hits (the numbers in section 2) |
| tile18x32_pred, tile18x32_pro | [n] | 1-tile bins floor(x*18) + 18*floor(y*32) of argmax_frame_xy / pro_frame_xy |

Join key to s1_dataset.npz play rows: (tags[rep], side, tick) -- verified 3,796/3,796 unique and matched.

## 4. Old init at the 1-tile 18x32 grid (a) measured

- **top-1 6.69%** (argmax cell centre binned to a tile == pro tile; identical when binning the summed tile prob mass);
  top-5 by summed tile mass 21.13%. Clean subset (n 2,072): **6.37 / 20.95**.
- |argmax - pro| in tiles: mean 5.28, median 4.03, p90 12.30; within 1 tile 14.8%, within 2 tiles 31.3%.
- CAVEAT for the matched comparison: this grid penalises the old model for its own cell shape. Of its 520 432-cell hits only
  250 survive 1-tile binning (a 1.333-tile-tall cell straddles two tile rows; tesla drops 16.7 -> 1.0, the_log 21.1 -> 1.7,
  x_bow unchanged 30.5). The fair matched read is EITHER (i) 1-tile bins for both (what cell_tile_top1 gives the new model,
  a real 2x-finer-y instrument the old model cannot match), OR (ii) bin the NEW model's predicted xy to the nearest
  `cell432_centers` entry and compare with `pro_cell432` -- the old model's home grid, both models equally coarse. Report both.

## Findings the lead should know
- (a) HANDOFF §5cs.48 says the 432 grid's row pitch is 0.499 tiles and "the 1.333-tiles/row figure does not exist at any grid
  size". On the grid the BC datasets (v1, v2, this rescore) AND SimMatchEnv use -- `sim/env.py::_board_action_space`,
  arena_box [0,0,1,1] -- the 432 cell centres span y 0.0208..0.9792 = **row pitch 1.333 tiles, col pitch 1.000 tile**
  (snap_dist max 0.833 = half-diagonal of a 1.0 x 1.333 cell). §5cs.48's probe used the plain live-screen ActionSpace(cfg)
  (arena_box 0.03..0.97 x 0.10..0.86 FRAME coords, then read as tiles): that is the live tap space, not the trainer's grid.
  Worth a re-read of §5cs.48's conclusion; not changed here.
- (a) The old model's 432 argmax rarely lands in the pro's tile (6.7%) even when it is in the pro's cell; at the half-tile
  resolution the new head predicts, the old init is structurally unable to compete on tile-exact metrics.
- Untested (b): whether the 1.3-point gap between old-train-tag rows (14.39) and clean rows (13.13) is memorisation or
  replay-quality noise; n is small (37 vs 48 replays).

Files: rescore_old.py (driver), rescore_old_run.log, rescore_old_summary.txt, rescore_old_score.json (per card / time),
rescore_old_assemble.json (per-drive summaries), rescore_old_shards/ (obs shards, reusable), rescore_old_preds.npz.
Nothing staged into git.

STATUS: complete
