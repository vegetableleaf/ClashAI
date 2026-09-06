# L64j notes (in progress, 10:1x UTC)
- hogeq re-fetch DONE 275/299 in 76 min, all i=1 (24,867 rows), 24 tags skipped on RateLimited (resumable: rerun --deck hogeq after icebow). i1_tags: 274 usable, 1 rejected (00YYPYY9JRVP).
- icebow re-fetch RUNNING (refetch_icebow2.out; 63/615 at 09:59 UTC, ~3.7/min -> ~12:30 UTC).
- Full i=1 hogeq drive (corpus_v3_i1/hogeq, aggregate.json): 274 tags, 222 ok, 52 failed ALL "card has no native evolution form: 26000043" (v3: 52/296 same reason + 3 deal). fidelity_hogeq_full.txt: winner match 145/222 = 65.3% vs v3 162/241 = 67.2%; acc 98.0 vs 98.7; exact crowns 54.5 vs 56.4 (the n=64 2-sd deficit was noise); terminal_vs_last_play negative 116/222 = 52% vs 88/241 = 36.5% (z 3.4, (b)); engine 3-crown 12.6 vs real 6.8 (v3: 18.3 vs 14.9).
- y_offset_hogeq.txt: per-card mean y, rotated i=1 vs i=0, weighted mean dy 0.008 tiles; blue cards within 0.32 -> frame correct (a). handedness full set: 97 cards, 6 |z|>3; sum|dLeft| rotation 8.74 vs mirror 9.99; blue tesla left 0.279 vs 0.237.
- crowns_vs_i.txt (battles.csv): hogeq i0 any-3-crown 17.3% (n300) vs i1 8.1% (n295), z~3.4; icebow 8.8% (625) vs 8.5% (612). Win rate equal both decks. (b) hogeq halves differ in outcome mix; not a frame effect.
- TRAP: the chained i=1 drive was launched WITHOUT --record-every 20 -> replay files have play_frames but no `frames` -> dataset would get 0 wait rows from the new half (v4-flawed: wait 23,421 == v3's 23,421, play 18,743 vs 9,797). Deleted that build. Re-drive with v3 flags (--record-every 20 --record-plays --determinism-every 10) chained after smp_ck0 on 37032 -> corpus_v3_i1r/hogeq (task b3kdzbeg5, drive_hogeq_rec.out).
- train_s1.py gained --tag (checkpoint s1_<deck>_<tag>_s<seed>.pt; default unchanged) so v4 runs cannot overwrite the v3 checkpoints. Plan: dataset --corpus corpus_v4/hogeq --out hogeq/data/pipeline/s1_dataset_v4.npz; train --data ... --tag v4 --out-dir scratchpad/gauntlet/L64/s1_v4; evaluate v4 ckpts on the v3 val rows (same instrument) -- needs an eval script.
- smp_ck1 (37031) finishing ~10:08; smp_ck0 RUNNING 37032 (started 10:00); smp_ck2 chained on 37031 (task bjqqt353p). Sample-gate band compared only within itself.
- smp_ck1 DONE (score_smp_ck1.txt, ckpt_diff_smp1.txt): s1 under --gate sample 79-21 (threshold: 19-1-80), seconds 145.9 (shorter: it wins faster, d_crowns_for +2.4), crowns against 0.97 (thr 2.06, none 2.87), survived longer 75/25, offered 20.7 plays/min, 54.5% accepted, accepted per match 27.4 (thr 17.4), mean elixir at decision 3.37 (thr 8.73), p_gate p50 0.154 (state-dependent: low elixir -> low gate), hog 435 vs 174, first play 6.5 s vs 23.5 s. DIFFERENT INSTRUMENT: compare only with smp_ck0/smp_ck2 and a rate-matched random (p ~0.2, to launch after smp_ck2).
- Crawler source fix APPLIED in the scraper repo (crawl_deck.py + crawl_icebow.py, both untracked there; diffs in refetch/crawl_*_fix.diff): markers joined on (tick, card, side) with in-order pop, attr_i kept. verify_crawler_fix.py: identical to parse_replay_i1 on 4 i=1 payloads + the i=0 probe payload (109/109 xy each) -> verify_crawler_fix.txt. Not yet exercised on a live crawl.
- pipeline/eval_s1.py: evaluates checkpoints on one npz's val rows; reproduces s1_hogeq_s0's val tile 0.2130 exactly.
- smp_ck0 DONE: 85-15, seconds 164.3, +57.0 +/- 7.7, survived longer 79, crowns against 0.82, offered 20.6/min, 58.4% accepted, accepted per match 32.9, p_gate p50 0.139, mean elixir at decision 3.41, first play 7.0 s. Sample band so far 85 / 79 / (s2 pending). rnd18_s0 (random p 0.18, rate-matched to the sample rule) chained on 37031 after smp_ck2 (task b7swhomeh).
- corpus_v3_i1r/hogeq re-drive RUNNING on 37032 (started 10:3x UTC).
- smp_ck2 DONE: 84-16, seconds 158.4, +51.0 +/- 6.9, survived longer 79, crowns against 0.95, offered 20.1/min, 57.4% accepted, 30.5 accepted per match, p_gate p50 0.137. SAMPLE BAND 85 / 79 / 84 (mean 82.7, sd 3.2) vs THRESHOLD 53 / 19 / 44 (sd 17.6). Accepted per match 32.9 / 27.4 / 30.5 vs 26.8 / 17.4 / 24.9. rnd18 (rate-matched random) running on 37031 from 10:4x.
- Chained (task byhty82qz): when corpus_v3_i1r/hogeq/aggregate.json appears -> s1_v4/run_hogeq_v4.sh (corpus_v4/hogeq = v3 + i1r; dataset s1_dataset_v4.npz; train_s1 x3 --tag v4; eval_s1 of v4+v3 ckpts on v3 val AND v4 val -> s1_v4/eval_v3val_hogeq.out, eval_v4val_hogeq.out). Reference band (v3 val): hogeq 21.30 / 20.58 / 21.08 = 20.99 +/- 0.36.

## L64k notes (11:18 UTC)
- i1r re-drive done 11:1x: 222 ok / 52 failed (same as first pass), rotated 274 tags / 25,859 rows, determinism 25/25, winner agreement 145/222 (unchanged), terminal_vs_last_play median -32 neg 116, first replay has frames (361) + play_frames (97).
- corpus_v4/hogeq = 241 + 222 = 463 replays; s1_dataset_v4.npz rows 63,769 (play 18,743 wait 45,026 val 9,907) vs v3 33,218 (9,797/23,421) -> play share 29.4% vs 29.5%: mix preserved (a).
- S1 v4 x3 training started ~11:17 UTC.

## L64l notes (12:2x UTC)
- Naive v4 (floor) band on v3 val (eval_summary_naive.txt): tile 23.28/22.73/23.28 = 23.10 +/- 0.32 vs v3 20.99 +/- 0.36; half 13.65/13.54/12.88 vs 20.03/18.71/19.04; nll 4.18-4.24 vs 3.90-3.93; card 58.0-58.3 vs 54.4-55.6; gate_bal 0.652-0.688 vs 0.588-0.627; wait 0.448-0.456 vs 0.417-0.439; value 0.572-0.587 vs 0.501-0.560. Best epochs 16/13/13 (v3: 20/11/18).
- v3 checkpoints on v4 val: nll 5.48-5.62 (label split they never saw), tile 21.14/19.95/21.21.
- lattice chain started 12:19 (v3-lat x3 then v4-lat x3).
- 12:5x: v3-lattice band on v3 val (eval_summary_v3lat.txt): lattice-point top-1 20.91/21.02/21.08 (21.00 sd 0.09) vs floor tile 21.30/20.58/21.08; nll 3.624/3.611/3.599 vs 3.899/3.933/3.897; card 55.5/53.7/55.9 vs 54.6/54.4/55.6; gate_bal 0.624/0.591/0.617 vs 0.627/0.588/0.621; value 0.567/0.525/0.560. Best epochs 12/12/17.
- Under lattice "tile" == half (pairs collapse onto tile-centre cells): lattice tile is NOT floor tile.
- Shared convention-free instrument added to evaluate(): place_hit (<=0.3 tile), place_1t (<=1 tile), place_dist (tiles) between the ckpt's own inverse of its argmax cell and the pro point (eval_summary_floor_place.txt):
  v3 floor 1t 27.19/26.64/27.13 dist 4.593/4.760/4.587; v3 lattice 1t 28.34/27.90/28.67 dist 4.580/4.669/4.515; v4 floor 1t 29.99/28.62/29.39 dist 4.414/4.380/4.425. floor hit = 0 by construction (centre 0.354 tile off the lattice).
- hogeq refetch resume: +22 (297/299 done, 2 RateLimited left). icebow drive 114/560 at 12:49.

## L64m notes (14:0x UTC)
- icebow i=1 chain DONE 14:02: drive 460/560 ok; fidelity i1r vs v3: winner match 343/460 = 74.6% vs 387/493 = 78.5%; acc 0.9897 vs 0.9922; exact crowns 0.722 vs 0.769; terminal_vs_last_play neg 123/460 = 26.7% vs 113/493 = 22.9%; expected s1 wins 314 vs engine 267 (v3: 338 vs 283). Second witness for 5cs.69 D (hogeq i1 65.3 vs 67.2): the i=1 half is 2-4 pp less faithful on both decks.
- handedness icebow: 113 cards compared, 5 with |z|>3 on left-fraction; sum |dLeft| rotation 7.038 vs mirror 8.118 (rotation is the better hypothesis, as on hogeq).
- corpus_v4/icebow = 493 + 460 = 953 replays, 0 collisions, frames present; dataset v4 147,842 rows (v3 78,277), play share 0.274 vs 0.277, val_rows 23,527.
- launched run_icebow_lat.sh (task bhyxgmby1) 14:04: v3 lattice x3 -> eval -> v4 lattice x3 -> eval -> floor place eval; ETA several hours.
- engine read smp_v4lat0 at 80/100 at 14:07.
