# L60 -- board value: does REAL context beat the card prior, and can the head learn the static map with coordinates?
Every number MEASURED on this box 2026-09-05 unless marked. Same 1,004 val rows (split.json), same scoring convention as
knn_vs_bc.md (pro card's masked 432-cell map, top-1 / top-5; 30 val rows unreachable under the mask). Reference points:
card prior 13.65 / 40.04 (control_prior.json), plain head-only BC 8.27 / 22.61 (bc_head_s0), kNN best 16.24 / 36.16.
Code: scratchpad/gauntlet/L60/real_context.py (M1), bc_coord.py (M2). Outputs: icebow/data/bc_pro/models/.



## Measurement 1 -- REAL (non-sim) context vs the board-blind card prior. models/M1_real_context.json, real_context.py (704 s, cuda)
Features from the replay records ONLY (meta.csv seconds / eng_elixir_before / tag,side,tick + crawl2/plays_ext.csv); no sim state.
- time bucket (0-60/60-120/120-180/180+ s, corpus seconds); elixir bucket from the ENGINE record eng_elixir_before (<4 / 4-6 / 6-8 / 8+;
  present for 87.1% of val rows, 1039 train rows have no record -> their own "na" bucket, i.e. effectively the card prior over the record-less replays);
  opponent's last NON-ability play strictly before our tick and <= 6 s old: card slug (120 distinct in train; "none" for 23.7% of train / 21.5% of val rows)
  and its tile in OUR frame (mirrored like the drive: side 1 nx = 1-x/18000, ny = y/32000), 4 rows x 3 lanes (13 values incl. "none";
  top: r1l2 1118, r1l0 973, r1l1 794 = the opponent's front half, r0l1 694 = their back-centre).
- Conditional histogram score = n_bucket(cell) + alpha * p_card(cell) [Laplace-1 prior, alpha in {1,5,20}] + 1e-3 gauss tie-break;
  bucket with < 5 train rows of that card -> back off to the plain card prior (the control's "hard" map, reproduced here at 13.65/40.04 exactly).
- Per-card columns: skeletons(180) ice_wizard(159) the_log(143) knight(126) tesla(105) x_bow(91) tornado(72) rocket(53); format top-1/top-5 %.

| conditioning (alpha) | overall | skel | icewiz | log | knight | tesla | x_bow | tornado | rocket | backoff rows |
| card prior (control) | 13.65 / 40.04 | 10.0/25.6 | 11.9/34.0 | 15.4/48.3 | 7.9/35.7 | 22.9/64.8 | 29.7/80.2 | 8.3/23.6 | 3.8/17.0 | - |
| (a) card x time (1) | 12.95 / 38.94 | 9.4/28.3 | 9.4/31.4 | 16.1/48.3 | 8.7/34.1 | 23.8/60.0 | 25.3/76.9 | 6.9/23.6 | 3.8/11.3 | 0 |
| (b) card x elixir (20) | 14.54 / 41.93 | 6.1/31.1 | 15.1/36.5 | 16.8/49.7 | 12.7/34.1 | 22.9/64.8 | 29.7/76.9 | 8.3/20.8 | 3.8/18.9 | 0 |
| (c) card x opp last card (20) | 13.45 / 37.85 | 7.8/22.8 | 10.1/28.9 | 16.8/44.8 | 9.5/35.7 | 21.0/59.0 | 26.4/76.9 | 11.1/23.6 | 11.3/26.4 | 300/1004 |
| (d) card x opp last tile (1) | 15.54 / 44.72 | 9.4/35.6 | 15.1/40.9 | 18.9/50.3 | 14.3/41.3 | 17.1/64.8 | 34.1/75.8 | 12.5/27.8 | 11.3/32.1 | 7 |
| (e) CV-selected: NB time+elixir+opptile (20) | 15.44 / 42.13 | 9.4/29.4 | 14.5/41.5 | 17.5/46.9 | 11.1/38.1 | 21.0/61.0 | 36.3/76.9 | 8.3/20.8 | 9.4/28.3 | - |
| kNN real vector k=15 hard | 13.75 / 37.35 | 8.9/22.2 | 11.9/32.1 | 13.3/42.0 | 12.7/34.1 | 16.2/49.5 | 27.5/71.4 | 9.7/23.6 | 15.1/37.7 | - |
| kNN real vector k=15 gauss | 14.54 / 34.96 | 10.6/19.4 | 11.3/32.7 | 13.3/38.5 | 13.5/36.5 | 23.8/51.4 | 27.5/50.5 | 6.9/25.0 | 13.2/32.1 | - |
| kNN real vector k=50 hard | 15.84 / 43.53 | 8.3/30.6 | 18.2/44.0 | 16.1/46.2 | 11.9/42.9 | 22.9/67.6 | 31.9/70.3 | 11.1/22.2 | 7.5/24.5 | - |
(alpha barely matters: time 12.95 at all three, elixir 14.44/14.44/14.54, oppcard 13.35/13.35/13.45, opptile 15.54 x3.)
- (e) selection: every subset of {time, elixir, oppcard, opptile} x alpha x {joint bucket, naive-Bayes product of the single conditionals} was
  ranked by 5-fold BY-REPLAY CV on train (top-1): NB time+elixir+opptile a20 14.34/40.30, NB elixir+opptile a20 14.21/41.29, opptile alone 14.02/39.95,
  joint elixir+opptile 14.02/39.88 ... vs the prior's CV 12.32/37.04 (CV folds are harder than the val split: 12.32 vs 13.65). Anything with oppcard or
  the 3-4 way JOINT buckets ranks below opptile alone (the joint buckets back off too often). The CV winner scores 15.44/42.13 on val, i.e. no better
  than opptile alone (15.54/44.72) -- the selection is within noise.
- kNN over the real-record vector (dim 127: sec/180, elixir/10 + missing flag, opp nx, ny, age/6, opp-card one-hot 121; Euclidean, same-card
  neighbours): k=15 13.75/37.35 hard, 14.54/34.96 gauss; k=5 10.16/31.18; k=50 15.84/43.53 (k=50 hard is the best number of the whole measurement).
- by time, opptile (d): 0-60 19.5/52.1, 60-120 16.9/50.8, 120-180 13.8/39.9, 180+ 10.1/32.6 (prior 15.6/48.2, 14.0/40.9, 13.8/37.2, 8.5/30.2).

VERDICT M1 (measured): the best real-context gain over the prior is +1.9 top-1 (opptile, 15.54 vs 13.65; binomial SE ~1.1 pt at n 1004 -> ~1.7 SE)
and +4.7 top-5 (44.72 vs 40.04; SE ~1.5 -> ~3 SE); kNN k=50 +2.2 / +3.5. NOTHING reaches the +3 pt top-1 bar. Real context carries about the same
placement information the sim-board kNN did (+2.6 top-1, 16.24/36.16) -- and the two look complementary in kind (real context helps top-5 a lot,
the board kNN hurt top-5). Reading: pro placement of this deck is mostly stereotyped per card; the one real feature that moves it is WHERE the
opponent just played (lane/row: 4.7 pt of top-5 = "answer in the lane they attacked"), not what they played, not the clock. Time alone is
BELOW the prior (12.95: 38 buckets dilute the histogram without adding information). So the +2.6 kNN gain from the sim boards cannot be dismissed
as "wrong boards" -- real context does not do better either -- but neither says placement is board-driven; both say the prior is nearly all of it.
Caveats: features are the pro's OWN records, so opp last-tile uses the exact opponent tile, a luxury the live policy would have only through the
detector; the elixir feature is missing for 12.9% of val rows (their bucket = record-less replays' prior); k and alpha for the kNN were not CV-selected.

## Measurement 2 -- can the cell head learn the static map once it has coordinates? bc_coord.py, models/M2_*.json, bc_head_{coord,bias,both,biasonly}_s0.pt
Recipe = knn_vs_bc head-only (trunk frozen; cell_ctx + cell_conv trained; rail repair --rescale_p99 6 -> cell_conv.4 / 10.36; Adam 1e-3; batch 128;
<= 60 epochs; early stop on VAL CE, patience 8, epoch 0 eligible; seed 0; cuda, 19-30 s per run). Wrapper module HeadWrapper in bc_coord.py holds the
UNMODIFIED PolicyNet (icebow/src untouched) and re-implements _cell_logits:
 (i) coord: cell_conv[0] = Conv2d(96 -> 48, 1x1) (64 fmap + 32 ctx channels) is replaced by Conv2d(98 -> 48, 1x1); weight[:, :96] and bias copied
     from the source, weight[:, 96:98] = 0; the 2 new input channels are constant x, y in [-1, 1] at the fmap resolution 12 x 8 (obs 96 x 64 / 8).
     Asserted: epoch-0 val top-1/top-5 == rescaled baseline (3.49 / 11.75).
 (ii) bias: learnable per-card bias map [10, 432] added to the pre-tanh cell logits, init = log(train_count + 1) (Laplace-1, not centred). The log
     prior alone through the same tanh path scores 13.65 / 40.04 (= control); epoch 0 = rescaled baseline logits + log prior = 9.16 / 32.47, CE 4.24
     (the source head's logits DEGRADE the prior by 4.5 pt: they are anti-informative noise on top of it).
 extra: both = (i)+(ii); biasonly = (ii) with the convs frozen (only the map trains).
curve = (epoch: val top-1 / top-5 / val CE); val CE over the 974 reachable val rows.
- coord s0: 1: 8.47/21.02/4.60  3: 8.96/22.61/4.45  7: 8.76/24.10/4.33  12: 9.26/24.50/4.28  20: 8.67/24.10/4.22  30: 9.46/25.40/4.19  40: 9.36/26.69/4.16
  50: 9.56/26.29/4.14  58: 9.76/28.29/4.115  60: 9.56/27.29/4.12 -> NO early stop in 60 epochs (val CE still falling at 60; train CE 3.905), best ep 58.
- bias s0: 0: 9.16/32.47/4.24  1: 13.25/39.74/3.80  2: 14.04/41.83/3.74  4: 16.14/41.93/3.67  10: 15.04/44.32/3.59  20: 15.14/45.92/3.535
  26: 15.44/46.31/3.531  35: 15.44/46.61/3.521  41: 16.43/46.51/3.534 -> stop ep 43, best ep 35 (train CE 3.28 at ep 35: fits train much better, mild overfit).
- both s0: 1: 13.25/39.74/3.80  5: 14.94/42.13/3.64  20: 14.34/46.12/3.533  35: 15.54/46.91/3.519 -> stop ep 43, best ep 35.
- biasonly s0 (convs frozen): 1: 9.16/33.07/4.23  20: 10.76/36.25/4.03  40: 11.45/37.95/3.93  60: 12.75/40.94/3.889 -> 60 epochs, never stops: the map is
  slowly CANCELLING the frozen baseline logits (lr 1e-3 on a bias moves ~0.06/epoch); at 60 it is back at the prior's CE (3.89) and below its top-1.
- bias seeds 1, 2: 16.24/46.41 (best ep 38, CE 3.534), 15.14/46.51 (best ep 24, CE 3.531). Seed spread top-1 15.14-16.24, top-5 46.4-46.6.

| run | val top-1 / top-5 | best ep | val CE | entropy (nats) | file |
| card prior (control, Laplace-1) | 13.65 / 40.04 | - | 3.88 | 4.26 | control_prior.json |
| plain head-only bc_head_s0 (knn_vs_bc, top-1 stop) | 8.27 / 22.61 | 3 | 4.45 | 4.41 | bc_head_s0.pt |
| plain head-only 60 ep, no stop (knn_vs_bc diag, unrepaired) | 9.16 / 26.79 | 57 | 4.20 | 4.07 | diag_head_full60.pt |
| (i) coord s0 | 9.76 / 28.29 | 58 | 4.115 | 3.98 | bc_head_coord_s0.pt |
| (ii) bias s0 | 15.44 / 46.61 | 35 | 3.521 | 3.49 | bc_head_bias_s0.pt |
| (ii) bias s1 / s2 | 16.24 / 46.41, 15.14 / 46.51 | 38 / 24 | 3.534 / 3.531 | - | bc_head_bias_s{1,2}.pt, M2_bias_s{1,2}.json |
| both s0 | 15.54 / 46.91 | 35 | 3.519 | 3.48 | bc_head_both_s0.pt |
| biasonly s0 (convs frozen) | 12.75 / 40.94 | 60 | 3.889 | 3.60 | bc_head_biasonly_s0.pt |
- per card (top-1/top-5), bias s0 vs prior: skeletons 11.1/33.3 (10.0/25.6), ice_wizard 13.2/44.0 (11.9/34.0), the_log 23.1/55.9 (15.4/48.3),
  knight 10.3/43.7 (7.9/35.7), tesla 24.8/67.6 (22.9/64.8), x_bow 25.3/76.9 (29.7/80.2), tornado 5.6/23.6 (8.3/23.6), rocket 11.3/32.1 (3.8/17.0).
  by time: 0-60 18.3/55.3, 60-120 17.4/50.8, 120-180 14.6/41.5, 180+ 8.5/36.4 (prior 15.6/48.2, 14.0/40.9, 13.8/37.2, 8.5/30.2).
- per card, coord s0: skeletons 5.0/28.3, ice_wizard 18.2/36.5, the_log 18.2/44.8, knight 16.7/37.3, tesla 7.6/22.9, x_bow 0.0/12.1, tornado 1.4/8.3,
  rocket 0.0/9.4. Coordinates lift tesla 1.0 -> 7.6 and x_bow top-5 0 -> 12.1 but x_bow top-1 stays 0/91: 60 epochs at 1e-3 is not enough for three
  1x1 convs + a 12x8 -> 24x18 bilinear map to carve "the river tile" out of two linear ramps.
- The strict-loadable convs of bias s0 WITHOUT the map score 6.77 / 20.12 (both s0: 7.67 / 20.32): the head learned a residual on top of the map,
  not the map itself. What the head adds to the map: bias s0 15.44/46.61 CE 3.52 vs the prior 13.65/40.04 CE 3.88 (+1.8 top-1 ~1.7 SE,
  +6.6 top-5 ~4 SE, -0.36 nats).

VERDICT M2 (measured): (i) coordinates alone do NOT let the head learn the static map: 9.76 / 28.29 after 60 epochs (vs 8.27 / 22.61 plain, 9.16 / 26.79
plain-60-epoch), still 4 pt of top-1 and 12 pt of top-5 below the prior, val CE 4.12 vs 3.88. (ii) the per-card bias map initialised from the log prior
puts the head ABOVE the prior from epoch 2 and ends at 15.4 / 46.6 (3 seeds 15.1-16.2 / 46.4-46.6), val CE 3.52 -- the first BC result in L60 that
beats the control on every metric, and its top-5 46.6 beats every kNN and every real-context conditional (best 44.7). The gain over the prior is
in top-5 and CE (the head sharpens the map's neighbourhood per state); top-1 +1.8 is ~1.7 SE. The hypothesis in knn_vs_bc.md point 3 is therefore
half right: "initialising from the prior lifts BC to >= 13.65 immediately" -- measured yes (13.25 at epoch 1, 14.04 at 2); "adding a coordinate
input" -- measured no, not within this recipe's budget. Adding the coordinates on top of the map changes nothing (both 15.54/46.91 vs 15.44/46.61).
Checkpoints: NEITHER wrapper fits the source dict layout. cell_conv.0.weight would be [48,98,1,1] (PolicyNet expects [48,96,1,1]); the [10,432] map
cannot fold into cell_conv.4.bias [10] (per channel, before a bilinear 12x8 -> 24x18 upsample -- a per-cell map is not in that layer's span). Each .pt
keeps the full source layout with `model` = the strict-loadable part (verified: PolicyNet.load_state_dict strict OK; that part alone is NOT the
evaluated model -- see the 6.77/20.12 line) plus `bc_pro_extra` = {tensors: cell_bias_map [10,432] and/or cell_conv.0.weight_coord [48,2,1,1], note}
and `bc_pro` = {mode, seed, best_epoch, val_top1, val_top5, val_ce, head_rescale_div 10.36, stop_on val_ce}. Reload through HeadWrapper reproduces
the val top-1 exactly (asserted in the script). The policy code (PolicyNet._cell_logits) would need the extra parameter: cells + bias_map[None]
before the tanh cap (10 x 432 = 4,320 floats) -- the cheaper of the two, and the only one that pays.

## Could not be done / caveats
- The two wrappers cannot be saved in the strict source layout (above); no --resume of train-sim-ppo was attempted (run contention with arm E).
- M1 elixir buckets use the engine record where present (87.1% of val); the 12.9% record-less rows sit in their own "na" bucket (not a true back-off to
  the card prior over all train rows, but the prior over the record-less replays -- 1039 train rows).
- M1 opponent-play features use the exact tile from the replay record (the live policy would only have the detector's estimate); ability plays skipped.
- "Best combination" in M1 was chosen by 5-fold by-replay CV on train, not on val; the kNN's k and the histograms' alpha were not CV-selected
  (alpha changes nothing beyond 0.1 pt; k=50 > k=15 for the real-vector kNN, 15.84 vs 13.75).
- Seeds: M2 bias 3 seeds, coord/both/biasonly 1 seed each; M1 is deterministic. Binomial SE ~1.1 pt (top-1) / ~1.5 pt (top-5) at n 1004.
- Per-run wall time: M1 704 s (python-loop CV over 15 feature subsets x 3 alphas x 2 modes x 5 folds), M2 19-30 s each; RAM < 1.2 GB, GPU ~1.4 GB.
STATUS: complete
