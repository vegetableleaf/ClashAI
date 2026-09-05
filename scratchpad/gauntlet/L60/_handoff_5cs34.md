
### §5cs.34 -- L60b (2026-09-05 14:5x-15:3x UTC): kNN vs BC net vs baseline on the SAME 1,004 held-out pro placements -- a BOARD-BLIND per-card cell histogram scores 13.65% top-1 / 40.04% top-5 and beats every learned method except kNN-on-raw-pixels by a marginal +2.6 pt; the c2r_best TRUNK EMBEDDING IS NEAR-CONSTANT (pro-to-pro nearest-neighbour cosine median 0.991) and its CELL HEAD SITS AT THE TANH RAILS (92.4% of masked raw logits |raw| > 8, gradient 1e-2..1e-6) -- the mechanism behind "every arm re-collapses"; BC on this architecture cannot even learn the static map (8.3%); owner ruled: stop arm E after m5k (pending), engine work next

Source: `scratchpad/gauntlet/L60/knn_vs_bc.md` (+ `knn_vs_bc.py`; artefacts `icebow/data/bc_pro/models/`,
untracked). All numbers on the same 1,004 val rows (40 replays, split.json seed 0), pro card's masked cell
map, top-1 / top-5 %. Binomial SE ~1.1 pt at p 0.14. 30 val rows (3%) have the pro cell inside an excluded
own-tower footprint and are unreachable for every masked method. (a) throughout unless marked.

| method | top-1 | top-5 |
|---|---|---|
| A. baseline c2r_best_36k_backup (val) | 3.49 | 11.75 |
| **CONTROL: per-card cell histogram from TRAIN, no board** | **13.65** | **40.04** |
| B. kNN raw-obs PCA-256, k=15, Gaussian vote | 16.24 | 36.16 |
| B. kNN feature map 6144-d, k=15 gauss | 15.94 | 33.76 |
| B. kNN trunk embedding z 328-d, k=15 | 12.15 | 34.96 |
| C. BC head-only s0 / s1 / s2 (rail-repaired) | 8.27 / 8.27 / 8.37 | 22.61 / 21.22 / 24.90 |
| C. BC trunk fine-tune 1e-4 s0 | 8.47 | 21.31 |

**What it establishes.**
1. **The card prior is the bar.** "Which card -> where that card usually goes" gets 13.65 / 40.04; per card
   tesla 22.9 / 64.8, x_bow 29.7 / 80.2, the_log 15.4 / 48.3, knight 7.9 / 35.7. The checkpoint is 4x below
   it (cell 235 x267, 423 x173, 374 x100 of 1,004 top-1 picks; masked entropy 0.950 nats of 5.08). Any
   method has to beat 13.65 / 40.04 to be using the board at all.
2. **kNN = the prior plus a little.** Best margin +2.6 pt top-1 (~2 SE, marginal); no kNN beats the prior on
   top-5 below k=150 (k=150 rawpca 43.82, converging to the prior). Per card (rawpca k=15 gauss): tesla
   29.5 / 51.4, x_bow 27.5 / 50.5, the_log 20.3 / 44.8, knight 17.5 / 40.5.
3. **Owner's raw-vector-vs-learned-embedding question, measured:** raw pixels (PCA-256, 62.2% of variance)
   >= feature map > trunk embedding at every k. The trunk's 328-d embedding is nearly constant across pro
   boards: nearest-neighbour cosine median 0.991 (p10 0.981, p90 0.996; any-card 0.994) vs raw PCA 0.562
   (0.410 / 0.821). The current policy's representation carries almost no board information -- a learned
   embedding for the owner's vector space has to come from somewhere else (a BC-trained trunk, or an
   encoder trained on the engine states). Train leave-one-out coverage matches val (val is not under-covered).
4. **TRAP / MECHANISM: the c2r_best cell head is stuck at the tanh rails.** 92.4% of raw pre-tanh masked
   cell logits have |raw| > 8 (mean -23.6, min -112); the cap's gradient there is 1e-2..1e-6. Head-only BC
   without repair returned the UNTOUCHED checkpoint (val top-1 2.8-3.3 for 8 epochs; epoch-1 entropy jumps
   0.95 -> 5.07 nats = uniform); trunk fine-tune without repair needed 17 epochs to leave the rails. The
   shipped BC checkpoints (`models/bc_head_s{0,1,2}.pt`, `bc_ft_s0.pt`, full source dict layout + `bc_pro`
   record, strict reload verified) use a ranking-preserving linear rescale of `cell_conv.4` (/10.36,
   `--rescale_p99 6`; epoch-0 numbers identical to the baseline). (a) **This is the mechanism for the
   10-day circle:** any PPO gradient on that head is nearly dead at the rails; the resume guard (x0.043)
   revives it and it re-saturates within ~10k matches; every reward-side arm was pushing on a head that
   cannot move. (b, consistent with §5cs.32 / §5cs.28): the board-blind placement-prior nulls (§5ae/5am/5ao)
   may have been dead-gradient artefacts, not evidence that priors don't move behaviour -- untested;
   `tools/repair_card_head.py` deliberately skips the cell head.
5. **BC on this architecture cannot learn even the static map** with 5.9k samples: val CE 4.3-4.5 vs the
   prior's 3.88; tesla 1-4 and x_bow 0-1 vs 22.9 / 29.7 (BC still puts x_bow at 0/91 like the baseline),
   while knight 15.9-19.0 beats the prior's 7.9. The cell head has no coordinate input: a per-card static
   map ("x_bow at the river") must be read off the fixed background through 3 convs + a 12x8 bilinear
   map. Trunk fine-tune at 1e-4 or 1e-3 does not fix it in 60 epochs (1e-3 overfits from ep 18). Seed noise
   on head-only val top-1 is 0.1 pt; epoch-to-epoch wobble ~1.5 pt, so top-1 with patience 8 is a noisy
   stopping rule (val-CE-stopped and 60-epoch diagnostics reach 9.2-9.3 -- still below the prior).

**What it does NOT establish.** Whether the small board-conditioning gain is because the boards are
uninformative (26%-parity sim reconstruction, 43.5% of pro plays after the sim's end) or because this
deck's pro placements really are mostly stereotyped per card. Two cheap separators, both untested:
(i) condition the kNN/prior on REAL-record features only (elixir, time, opponent's last card + tile from
the engine records -- none of them from the sim): a gain over 13.65 says boards matter and the sim's
boards are the problem; (ii) dataset v2 from the sandbox engine. Also untested: a 2-channel coordinate
input to `cell_conv` (model-internal, no obs change) or initialising the per-card bias map from the prior
should lift BC to >= 13.65 immediately -- one head-only run each.

**Plan consequences.** (1) The IL init is NOT "c2r_best + BC head": the head has to be rescaled or
re-initialised and the architecture needs a coordinate input before BC can carry a doctrine. (2) The
per-card prior (13.65 / 40.04, `models/control_prior.json`) is a free, strong prior for the PPO KL term --
already 4x more pro-like than the checkpoint. (3) The owner's vector-space idea needs a non-collapsed
embedding; raw-pixel PCA is the placeholder key until a BC-trained trunk exists. (4) Engine dataset v2 is
the fidelity separator and stays next.

**Not done:** `train-sim-ppo --resume` from the BC checkpoints not launched (run contention); loader calls
reproduced instead. `best_wr`/`matches` inherited from the source checkpoint.
