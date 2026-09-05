# L60 -- PRO behaviour-cloning dataset from the RoyaleAPI replay corpus through the sim
Every number is MEASURED on this box (2026-09-05) unless marked otherwise.

## Output (icebow/data/bc_pro/)
- `dataset.npz` -- train-bc format: obs [6922,96,64,12] uint8, acts [6922,3] int64 = (card_idx, gx, gy), hands/nexts [6922,10] f32,
  elixirs [6922,1] f32, threats [6922,52] f32, grid [18,24] int64, deck (10 policy identities, same order as the checkpoint). 2.8 MB.
- `meta.csv` -- one row per sample (row index = dataset row): tag, side, play_index, tick, seconds, sim_t, delay_ticks, card_slug/key/id,
  gx, gy, cell, snap_dist_tiles, x_units, y_units, own_nx/ny, hand_source, hand_certain, hand_match_engine, sim_elixir,
  eng_elixir_before, elixir_diff, anywhere, pocket_code, sim crowns / towers alive / unit counts per side, hand_ids, and the
  checkpoint's ck_top1, ck_top5, ck_hit1, ck_hit5, ck_card_top1, ck_card_hit1.
- `meta_oov.csv` -- 6069 accepted plays of the NON-focus side (cell in its own frame, no obs, no card label: out of the policy's vocabulary).
- `split.json` -- by-replay 85/15, seed 0: 228 train tags / 40 val tags = 5918 / 1004 rows (train_rows, val_rows are dataset row indices; no tag in both).
- `drive_summary.jsonl` (one line per drive), `report.txt`, `shards/` (per-drive npz + json + baseline json; the assemble stage reads these).

## How it is built (scratchpad/gauntlet/L60/build_bc_dataset.py)
- Drive = the L51 parity driver, re-implemented with a hook (L51 itself unchanged): both sides L11, princess towers, 40-tick elixir slack,
  tail cap 360 s, sub_dt 0.1, engine seed 424242. Corpus tick*0.05 = release time; x/18000, 1-y/32000 = sim coords.
- Frame: "me" is sim team 0 (bottom, hard-coded in SimMatchEnv). The icebow deck is the BLUE deck in 268/268 usable replays (RED too in 2), so
  every blue-focus drive is MIRRORED exactly like L51 --mirror (sides swapped, x->18000-x, y->32000-y); the 2 red-icebow replays get a second,
  un-mirrored drive (86 samples, side 0). Verified: the mirrored drive of 000YLY0JCPGL reproduces L51 simbatch_mirror (crowns [0,1], 118 accepted, t 295.0).
- Obs: a real SimMatchEnv whose `env.eng` is swapped for the driven engine per replay (vectors, canvas stack, evo charge, threat credits reset);
  `_update_vectors()` runs every agent_dt (0.6 s) for opp-memory upkeep and once more IMMEDIATELY BEFORE each focus deploy with
  agent_dt = time since the last update. domain_rand disabled (eval convention), detector noise at env defaults, deterministic per drive
  (rng seeded by crc32(tag:side)). obs/hand/next/elixir/threat are copied from the env at that moment = exactly what the policy would see.
- Card label: the sim's own evo rule (`_slot_card_id`; tesla/knight evolve after 2 base plays) applied to the reconstructed cycle.
- Cell label: nearest of the 432 `env.actions.cell_center` points to the pro's own-frame point, distance in tiles (18x32). Never a hand scale.
  meta.cell == acts gy*18+gx checked for all rows. snap distance mean 0.379 tiles, max 0.833 (the 24-row policy grid is coarser than the 32 engine rows,
  so a cell centre lands up to 0.67 tiles from the pro's tile in y).
- Hand: engine record queue (deal_probe hand_pos+cycle_pos over final_decks) for 213/270 drives, played-card-to-back; checked against the
  record's `hand_before` at 5753 plays: 48 samples disagree (0.8%), all flagged hand_match_engine=0. 57 drives (no record) use the heuristic
  first-play-order queue; hand_certain=1 for 6694/6922 rows.
- The cycle advances on every real non-ability focus play (accepted or not); samples only for ACCEPTED sim deploys (50 rejected in total, all sides).

## Numbers
- samples 6922; per side blue(1) 6836 / red(0) 86; replays with samples 268/268 (270 drives); samples per replay median 26 (p10 10, p90 38, min 1, max 90).
- per card: skeletons 1170, ice_wizard 1099, the_log 1027, knight 881, tesla 726, x_bow 637, tornado 508, rocket 356, knight_evo 289, tesla_evo 229.
- per cell top 10: 422:294, 423:269, 237:265, 248:259, 296:246, 278:204, 267:192, 238:188, 254:176, 242:175
  (422/423 = behind the king tower; 237/238/248 = the lane tiles just below the river).
- time coverage (corpus seconds): min 5.7, p10 27.6, median 119.0, p90 182.7, max 298.1; buckets 0-60: 1790, 60-120: 1694, 120-180: 2709, 180+: 729.
- COVERAGE LOSS: 12306 focus plays in the corpus, 6922 sampled. 5348 (43.5%) come AFTER the sim's own end: the sim finished before the
  replay's last play in 219/270 drives (median sim end 180.1 s vs median last play 281.2 s; 90 drives end < 180 s, 114 at 180 s, 66 later;
  209 replays have plays after 180 s). Sim crowns match RoyaleAPI in 73/270 drives. This is the L51 parity gap, not something this script can fix
  without driving a dead engine.
- Drift proxies per sample: sim elixir vs the real engine's `elixir_before` (5753 rows): |diff| mean 0.27, median 0.07, p90 0.87, >2 in 0.9%;
  signed (sim-engine) mean -0.17. All 6 towers alive in the sim at 4739/6922 samples (68.5%). delay_ticks>0 in 118 samples.
- Determinism: 1 vs 4 workers identical on 40 drives; a full 1-worker re-drive matched the stored 4-worker run on 269/270 drives; drive
  020YPYQ22GY2 differed (sim end 268.9 vs 271.0 s, 81 vs 82 accepted, obs pixels differ, meta identical) -> the engine has a small
  process-dependent nondeterminism (not investigated here).

## Baseline: icebow/data/bench/c2r_best_36k_backup.pt (read-only; PolicyNet 12ch/10 cards/432 cells/52 threat, ck["model"])
Cell logits of the PRO's card, masked with the same deployable mask the policy gets (card kind + pocket code), top-1 / top-5 vs the pro cell.
Chance for a troop card = uniform over its 160 deployable cells: top-1 0.63%, top-5 3.1% (anywhere cards: 416 cells, 0.24% / 1.2%).
- overall n 6922: top-1 3.26%, top-5 10.92%. Card head (in-hand + affordable mask) picks the pro's card 43.35% of the time.
- per card: skeletons 4.19/10.85, ice_wizard 1.36/4.82, the_log 11.39/37.59, knight 2.27/7.26, tesla 0.69/2.75, x_bow 0.00/0.31,
  tornado 1.77/5.31, rocket 1.69/10.67 (top-1 % / top-5 %).
- by time: 0-60 s 4.64/14.08 (n 1790), 60-120 3.19/10.51 (1694), 120-180 2.58/9.63 (2709), 180+ 2.61/8.92 (729).
- 6 towers alive vs not: top-1 3.52% vs 2.70%.
- The checkpoint's own top-1 cell histogram is collapsed: 235 x1883 (27%), 423 x1100, 374 x642, 341 x362 ... (cell 235 = far-left river edge, the L58 collapse cell).
  x_bow agreement is 0/637 -- the pro's x-bow cells (237/238/248, at the river) and the checkpoint's are disjoint.

## Reproduce (cwd icebow; ~1 min total, 4 procs, <0.2 GB per worker: peak_wset 80 MB measured single-process)
    PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L60/build_bc_dataset.py --workers 4          # all stages
    ... --stage drive|baseline|assemble|report   (--force re-does existing shards; --limit N for a smoke run; --out for another dir)
train_bc note: `_load_datasets(root)` globs `root/*/dataset.npz` and splits val by FILE order, so to use split.json subset the rows yourself
(np.load(...); idx = json.load(open("split.json"))["train_rows"]) or copy dataset.npz under a subdirectory (e.g. bc_pro/all/dataset.npz).

## Could not be done / caveats
- Red-side (opponent) plays carry no card label: their decks are outside the 10-identity policy vocabulary in 266/268 replays (meta_oov.csv keeps their cells).
- 43.5% of pro plays are after the sim's own end (above); late-game coverage is thin (180+ s: 729 samples) and biased to replays the sim keeps alive.
- Per-tick tower HP of the real engine is not in the records (only final), so "does the sim state still match" is proxied by elixir agreement
  and sim towers-alive, not by tower HP.
- Sample obs after a sim-only tower loss (31.5%) show a board the real match did not have; filter with my_towers_alive/their_towers_alive if needed.
STATUS: complete
