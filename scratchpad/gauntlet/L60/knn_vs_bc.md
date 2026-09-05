# L60 -- kNN retrieval vs BC cell head vs baseline, PRO placement cells (same 1,004 val rows)
All numbers MEASURED on this box 2026-09-05 unless marked. Code: scratchpad/gauntlet/L60/knn_vs_bc.py. Outputs: icebow/data/bc_pro/models/.
Val split = split.json val_rows (40 replays, 1,004 rows); train = train_rows (228 replays, 5,918). Every method scores the MASKED
(ActionSpace.deployable_mask(anywhere, pocket) from meta.csv) 432-cell map of the card the pro actually played; top-1 = argmax == pro cell,
top-5 = pro cell in the 5 highest. Per-card = top-8 cards by count (n in parentheses is the VAL count); time buckets from meta seconds.
Format below: top-1% / top-5%.

Reproduce (cwd icebow): `PYTHONPATH=src PYTHONHASHSEED=0 ./.venv/Scripts/python.exe ../scratchpad/gauntlet/L60/knn_vs_bc.py <cmd>` with cmd one of
`baseline`, `prior`, `knn`, `bc --mode head --seed {0,1,2} --rescale_p99 6 --skip_epoch0`, `bc --mode ft --seed 0 --rescale_p99 6 --skip_epoch0`
(cuda, 2 torch threads, obs kept uint8 on the GPU; baseline 3 s, prior 2 s, knn 44 s, bc 10-45 s; RAM <= 1.2 GB).

## A. Baseline c2r_best_36k_backup.pt on val (n 1004)
- overall 3.49 / 11.75 (all-rows number was 3.26 / 10.92; train-split rows 3.26 / 10.80). Agrees with meta.csv ck_hit1 on 1003/1004 rows, ck_hit5 on 1002/1004 (GPU tie order).
- per card: skeletons 3.9/10.0 (180), ice_wizard 3.1/5.7 (159), the_log 11.9/41.3 (143), knight 3.2/8.7 (126), tesla 1.0/2.9 (105), x_bow 0.0/0.0 (91), tornado 0.0/9.7 (72), rocket 0.0/9.4 (53)
- by time: 0-60 4.7/13.2 (257), 60-120 3.3/12.8 (242), 120-180 2.9/9.6 (376), 180+ 3.1/13.2 (129)
- masked cell-map entropy on val: 0.950 nats mean (max possible for a 160-cell troop mask = 5.08). Top-1 histogram collapsed: cell 235 x267, 423 x173, 374 x100.
- file: models/A_baseline.json

## CONTROL: per-card cell histogram from TRAIN (no board state; = kNN with k -> all same-card rows). models/control_prior.json
- overall 13.65 / 40.04 (hard counts; sigma-1 Gaussian-smoothed 13.45 / 33.86). Card-agnostic global histogram 3.88 / 20.72.
- per card: skeletons 10.0/25.6, ice_wizard 11.9/34.0, the_log 15.4/48.3, knight 7.9/35.7, tesla 22.9/64.8, x_bow 29.7/80.2, tornado 8.3/23.6, rocket 3.8/17.0
- by time: 0-60 15.6/48.2, 60-120 14.0/40.9, 120-180 13.8/37.2, 180+ 8.5/30.2
- => the baseline checkpoint (3.49 / 11.75) is 4x WORSE than the card prior; any method has to beat 13.65 / 40.04 to be using the state at all.

## B. kNN retrieval (train rows of the SAME card, cosine on L2-normalised vectors; ties in the hard vote broken by 1e-3 x the sigma-1 smoothed vote). models/B_knn.json
Embeddings: `z` = PolicyNet._embed output (328-d: trunk(pool(fmap)) ++ hand_fc ++ next_fc ++ elixir_fc ++ threat_fc -- the vector feeding card_head and cell_ctx);
`fmap` = flattened pre-pool conv map features(x) (64x12x8 = 6144-d, the map the spatial cell head reads); `rawpca256` = flattened obs/255 (73,728-d),
train-mean-centred, PCA-256 fitted on train rows via the Gram eigendecomposition (256 comps explain 62.2% of train variance); `rawcos` = cosine on the
flattened obs with no PCA (exact, via the normalised Gram).
Coverage (val row -> nearest same-card TRAIN row cosine; median / p10 / p90): z 0.991 / 0.981 / 0.996; fmap 0.928 / 0.838 / 0.982; rawpca256 0.562 / 0.410 / 0.821;
rawcos 0.940 / 0.888 / 0.982. Train leave-one-out same-card NN: z 0.991/0.980/0.996, fmap 0.926/0.834/0.982, rawpca256 0.552/0.400/0.851 (val is as covered as train).
Any-card NN is only slightly closer (z 0.994 median) -> the learned embedding barely separates by card, and cos 0.99 for everything means z is nearly a constant vector.

| embedding  | k=1 hard | k=5 hard | k=5 gauss | k=15 hard | k=15 gauss | k=50 hard | k=150 hard |
| z (328)    | 9.56/20.52 | 10.76/29.68 | 10.56/28.09 | 12.15/34.96 | 12.75/33.76 | 13.65/39.44 | 13.75/41.53 |
| fmap (6144)| 12.25/25.20 | 13.45/33.96 | 13.35/30.58 | 14.74/37.95 | 15.94/33.76 | 13.55/39.94 | 13.55/39.44 |
| rawpca256  | 11.06/22.11 | 13.65/32.67 | 13.84/31.57 | 15.84/39.34 | 16.24/36.16 | 14.34/41.93 | 13.84/43.82 |
| rawcos     | 9.46/19.62 | 11.35/29.18 | 11.75/24.70 | 11.55/34.76 | 11.35/31.08 | 12.05/35.46 | 12.65/38.15 |
(k=1 hard == k=1 gauss by construction.)
- Best kNN top-1: rawpca256 k=15 gauss 16.24 (hard 15.84); fmap k=15 gauss 15.94. Card prior is 13.65: the margin is ~2.5 points = ~2 binomial SE (SE ~1.1 at p 0.14, n 1004) -- marginal.
- Top-5: no kNN at k<=15 beats the card prior's 40.04; at k=150 rawpca256 43.82 (converging to the prior + a little).
- Raw vector vs learned embedding (the owner's question): raw PCA-256 >= fmap > z at every k. The trunk's 328-d embedding is the WORST retrieval key
  (k=15: 12.15 vs 15.84); it is nearly collapsed (median NN cosine 0.991, any-card 0.994). Raw pixels do not lose to it.
- per card, rawpca256 k=15 gauss: skeletons 6.7/26.7, ice_wizard 12.6/31.4, the_log 20.3/44.8, knight 17.5/40.5, tesla 29.5/51.4, x_bow 27.5/50.5, tornado 12.5/25.0, rocket 9.4/20.8
- by time, rawpca256 k=15 gauss: 0-60 23.3/43.6, 60-120 17.4/38.8, 120-180 12.5/33.0, 180+ 10.9/25.6 (early game is easiest for every method: opening placements are stereotyped).
- per card, fmap k=15 gauss: skeletons 7.8/21.7, ice_wizard 16.4/30.8, the_log 16.8/43.4, knight 15.9/35.7, tesla 23.8/47.6, x_bow 30.8/52.7, tornado 15.3/20.8, rocket 11.3/22.6;
  by time 0-60 21.4/44.4, 60-120 16.1/35.1, 120-180 14.6/29.0, 180+ 8.5/24.0.
- kNN runtime 44 s on cuda (both Gram matrices chunked, 512 rows at a time; peak RAM ~1.2 GB).

## C. BC on the cell head (cross-entropy on the pro cell, pro card's masked map; train rows 5,918; Adam, batch 128, <=60 epochs,
early stop on val top-1 patience 8, seed = torch/shuffle seed). Val CE below = mean over the 974 val rows whose pro cell is inside the mask.
UNREACHABLE ROWS: 330/6922 pro cells (300 train, 30 val = 3.0%) lie in cells the deploy mask EXCLUDES (own princess/king footprints: 234/251 for
ice_wizard/skeletons, 320 knight, 337/338 the_log). They are misses for every masked method (val ceiling 97.0%) and are skipped in the loss.

### Trap found: the source cell head is stuck at the tanh rails
Pre-tanh raw cell logits of c2r_best on val (pro card, masked cells): mean -23.6, sd 12.8, min -112.6, max 26.4; 92.4% have |raw| > 8 (= model._LOGIT_CAP).
d/dx[8 tanh(x/8)] at x=-24 is 0.01 and at -60 it is 1e-6, so a CE gradient through the cap barely moves the head. Measured effect (as-spec, no repair):
- head-only s0, as spec: epoch 1 entropy jumps 0.95 -> 5.07 nats (uniform), val top-1 2.8-3.3 for 8 epochs -> early stop returns the UNTOUCHED checkpoint
  (best epoch 0 = 3.49/11.75). Run to 60 epochs without stopping: 9.16/26.79 at ep 57, train CE still falling 4.04 (models/diag_head_full60.json, .pt).
- fine-tune s0 (trunk 1e-4), as spec but epoch 0 not eligible: 9.26/27.29 at ep 33 (stopped ep 41), 17 epochs to leave the rails (models/diag_ft_norescale.*).
Fix used for the shipped checkpoints (documented deviation): divide cell_conv.4 weight AND bias by a constant so the train p99 |raw masked logit| = 6
(p99 measured 62.19 -> factor 10.36; --rescale_p99 6). Linear -> every ranking preserved: epoch-0 val top-1/top-5 = 3.49/11.75 exactly as the baseline;
entropy at epoch 0 becomes 4.57 nats. Same idea as tools/repair_card_head.py, which deliberately left the cell head alone. Epoch 0 excluded from early stop (--skip_epoch0).

### Shipped runs (rail-repaired, spec early stopping). models/C_head_s{0,1,2}.json, C_ft_s0.json
curve = (epoch: val top-1 / top-5 / val CE):
- head s0: 1: 7.97/21.41/4.60  2: 7.77/22.31/4.52  3: 8.27/22.61/4.45  5: 6.87/23.31/4.39  7: 8.07/24.90/4.32  10: 7.47/25.30/4.30  11: 6.97/24.70/4.29 -> stop ep 11, best ep 3
- head s1: 1: 8.27/21.22/4.58  3: 7.67/22.31/4.45  5: 7.97/23.41/4.38  7: 7.87/24.10/4.34  9: 7.97/24.50/4.32 -> stop ep 9, best ep 1
- head s2: 1: 7.97/21.81/4.60  3: 7.67/23.31/4.43  5: 8.07/23.21/4.38  8: 8.37/24.90/4.33  12: 7.77/24.80/4.30  16: 7.37/24.60/4.26 -> stop ep 16, best ep 8
- ft   s0: 1: 8.47/21.31/4.55  3: 8.37/23.21/4.39  5: 7.07/24.30/4.31  7: 8.47/25.00/4.24  9: 7.97/24.90/4.23 -> stop ep 9, best ep 1
Val top-1 sits at 7-8.5 from epoch 1 on while val CE keeps falling (4.60 -> 4.26); top-1 (SE ~0.85 pt at n 1004) is too noisy a stopping criterion here.

| run | val top-1 / top-5 | best ep | val CE | entropy (nats) | file |
| baseline | 3.49 / 11.75 | - | 5.22 (rescaled) | 0.95 (rescaled: 4.57) | bench/c2r_best_36k_backup.pt |
| card prior (control) | 13.65 / 40.04 | - | 3.88 (Laplace-1) | 4.26 (Laplace-1) / 3.64 (raw hist) | control_prior.json |
| bc_head_s0 | 8.27 / 22.61 | 3 | 4.45 | 4.41 | models/bc_head_s0.pt |
| bc_head_s1 | 8.27 / 21.22 | 1 | 4.58 | 4.68 | models/bc_head_s1.pt |
| bc_head_s2 | 8.37 / 24.90 | 8 | 4.33 | 4.39 | models/bc_head_s2.pt |
| bc_ft_s0   | 8.47 / 21.31 | 1 | 4.55 | 4.56 | models/bc_ft_s0.pt |
| diag head 60 ep, no repair, no stop | 9.16 / 26.79 | 57 | 4.20 | 4.07 | models/diag_head_full60.pt |
| diag ft no repair, top-1 stop | 9.26 / 27.29 | 33 | 4.11 | 3.95 | models/diag_ft_norescale.pt |
| diag ft trunk lr 1e-3, repaired, stop on val CE | 8.37 / 28.19 | 18 | 4.06 | 3.81 | models/diag_ft_lr1e3_ce.pt (train CE 3.56 at ep 26 = overfitting, val CE rising) |
Seed noise, head-only val top-1: 8.27 / 8.27 / 8.37 (range 0.1 pt at the stop point; the epoch-to-epoch wobble is ~1.5 pt, larger than the seed spread).
(Re-running seed 0 gave 8.17 once and 8.27 once at ep 3: cuDNN nondeterminism of ~0.1 pt.)
- per card, bc_head_s0: skeletons 8.9/19.4, ice_wizard 11.9/27.7, the_log 16.8/44.8, knight 15.9/31.0, tesla 1.0/9.5, x_bow 0.0/8.8, tornado 1.4/5.6, rocket 0.0/11.3
- by time, bc_head_s0: 0-60 14.4/33.5, 60-120 7.4/21.9, 120-180 6.1/18.4, 180+ 3.9/14.7
- per card, bc_ft_s0: skeletons 8.9/18.3, ice_wizard 12.6/26.4, the_log 14.7/44.8, knight 16.7/25.4, tesla 2.9/11.4, x_bow 0.0/4.4, tornado 2.8/6.9, rocket 0.0/15.1
- by time, bc_ft_s0: 0-60 14.8/31.5, 60-120 8.3/20.2, 120-180 5.6/17.6, 180+ 4.7/14.0
- Where BC loses to the prior: tesla (1-4 vs 22.9) and x_bow (0-1 vs 29.7) -- the two cards whose pro cells are a fixed tile set (river / centre); BC still puts
  x_bow at 0/91 like the baseline. Where BC ties or beats the prior: knight (15.9-19.0 vs 7.9), ice_wizard (12-14 vs 11.9), the_log (14-17 vs 15.4).
- Checkpoint format: full source dict (model, gate, value, value_d, algo, grid, n_cards, n_cells, threat_dim, in_ch, deck, best_wr, matches, arena_size) with
  the model entry replaced and a bc_pro record added (mode, seed, best_epoch, val_top1, source, head_rescale_div, epoch0). Verified: PolicyNet(12,10,432,52).load_state_dict
  strict + nn.Linear(328,{2,1,1}).load_state_dict for gate/value/value_d + val top-1 identical after reload (the same calls train_sim_ppo --resume makes,
  train_sim_ppo.py L407-413). CAVEAT: best_wr 30.67 / matches 36000 are inherited from the source, so a --resume would print "best so far 31%", and the
  gate/value heads are the source's (the trunk moved in bc_ft_s0, so its critic is slightly stale). I did NOT launch train-sim-ppo --resume (run contention with arm E).
- Runtime: head-only ~1 s/epoch, ft ~1.2 s/epoch on cuda with the PPO run sharing the GPU; peak RAM ~1.0 GB (obs uint8 on GPU); GPU mem ~1.4 GB.

## Bottom line (all measured on the same 1,004 val rows; 30 of them unreachable under the mask)
| method | top-1 | top-5 |
| A baseline c2r_best | 3.49 | 11.75 |
| control: per-card cell histogram (no state) | 13.65 | 40.04 |
| B kNN best (raw-obs PCA-256, k=15, gauss) | 16.24 | 36.16 |
| B kNN, learned z embedding, k=15 | 12.15 | 34.96 |
| C bc_head_s0 / s1 / s2 | 8.27 / 8.27 / 8.37 | 22.61 / 21.22 / 24.90 |
| C bc_ft_s0 | 8.47 | 21.31 |
1. The checkpoint is 4x below the card prior: its cell head carries no usable placement doctrine for pro cells (collapsed histogram, rails).
2. kNN is essentially the card prior plus a little: best margin +2.6 pt top-1 (~2 SE), and it never beats the prior on top-5 below k=150. Raw pixels are a
   better key than the trunk's 328-d embedding (which has median NN cosine 0.991 -- near-constant); the fmap (6144-d) is in between.
3. BC on this architecture with 5.9k samples cannot even reach the card prior (val CE 4.3-4.5 vs 3.88; train CE >= 4.0 with the trunk frozen). The cell head
   has no coordinate input -- a per-card static map ("x_bow at the river") has to be read off the fixed background through 3 convs + a 12x8 bilinear map --
   and fine-tuning the trunk at 1e-4 or 1e-3 does not fix it in 60 epochs (1e-3 overfits from ep 18). Hypothesis (untested): adding a 2-channel coordinate
   input to cell_conv, or initialising the per-card bias map from the prior, would lift BC to >= 13.65 immediately; the measurement is one head-only run each.
4. Rail trap (measured, relevant beyond this study): c2r_best's cell logits are 92% past the +/-8 tanh cap; any gradient on that head (BC or PPO) is ~1e-2 to
   1e-6 of nominal. tools/repair_card_head.py skips the cell head on purpose (was healthy in round 5); it is not healthy in c2r_best.

## Not done / caveats
- train-sim-ppo --resume from the saved files was not launched (run contention); the loader path was reproduced call-for-call instead.
- Early stopping on val top-1 with patience 8 (as specified) stops at epoch 1-8 on a criterion whose noise (~0.85 pt) exceeds the epoch-to-epoch gains; the
  val-CE-stopped and 60-epoch diagnostics are reported alongside so the ceiling of this recipe is visible (9.3 top-1, still below the prior).
- kNN uses the pro card as a hard filter (same-card neighbours); no distance weighting was tried beyond the sigma-1 cell smoothing.
- No confidence intervals beyond the binomial SE quoted; the 40 val replays are one split (split.json seed 0).
- Commands: see the Reproduce line at the top; diag runs used --min_epochs 60 / --skip_epoch0 / --rescale_p99 6 / --stop_on ce / --trunk_lr 1e-3 / --out / --json.
STATUS: complete
