
### §5cs.36 -- L60d (2026-09-05 14:3x-14:5x UTC): TWO SEPARATORS MEASURED -- (1) real-record context (time, engine elixir, opponent's last card/tile) adds at most +1.9 top-1 / +4.7 top-5 over the board-blind card prior, the same size as the sim-board kNN gain, so the small board gain is NOT explained by wrong boards: on this deck's placements the per-card prior is nearly all of it, and the one informative feature is WHERE the opponent just played; (2) a per-card cell BIAS MAP initialised from the prior is the first BC result above the prior (15.44 / 46.61 vs 13.65 / 40.04; 3 seeds 15.1-16.2 / 46.4-46.6), coordinate channels alone do not help (9.76 / 28.29, x_bow still 0/91)

Source: `scratchpad/gauntlet/L60/board_value.md` (+ `real_context.py`, `bc_coord.py`; artefacts
`icebow/data/bc_pro/models/M1_real_context.json`, `M2_*.json`, `bc_head_{coord,bias,both,biasonly}_s0.pt`,
`bc_head_bias_s{1,2}.pt`). Same 1,004 val rows and masked-map convention as §5cs.34. (a) throughout.

**M1 -- real (non-sim) context vs the card prior (13.65 / 40.04):**
| conditioning | top-1 / top-5 |
|---|---|
| card x time bucket | 12.95 / 38.94 (below the prior: dilution) |
| card x engine `elixir_before` (present for 87% of val) | 14.54 / 41.93 |
| card x opponent's last card (<= 6 s; 300/1004 backed off) | 13.45 / 37.85 |
| **card x opponent's last tile (4 rows x 3 lanes, own frame)** | **15.54 / 44.72** |
| CV-selected NB combo (time + elixir + opp tile) | 15.44 / 42.13 |
| kNN over the real-record vector k=15 (hard / gauss) | 13.75 / 37.35, 14.54 / 34.96 (k=50 15.84 / 43.53) |
Best real-context gain +1.9 top-1 (~1.7 SE), +4.7 top-5 (~3 SE); nothing reaches the +3 pt top-1 bar set
in §5cs.34. The sim-board kNN's +2.6 (§5cs.34) is the same size, so "the boards were wrong" does not
explain the smallness of the board gain. Reading: for THIS deck's placements (where to put the card,
given the card), the per-card static doctrine is nearly all of the predictable signal; what remains
predictable is the lane/row of the opponent's last play. Caveats: the opponent tile is the exact record
tile (live play only has the detector's estimate); 12.9% of val rows lack the engine elixir record.
NOT measured: whether card CHOICE and TIMING (what / when) are board-driven -- this section is about
placement only; the owner's "case by case" claim is untested for those two heads.

**M2 -- coordinates / prior bias map on the cell head** (head-only, rail-repaired, Adam 1e-3, batch 128,
<= 60 epochs, early stop on val CE patience 8):
| run | top-1 / top-5 | best ep | val CE |
|---|---|---|---|
| prior (control) | 13.65 / 40.04 | - | 3.88 |
| plain head-only (§5cs.34) | 8.27 / 22.61 | 3 | 4.45 |
| (i) 2 coordinate channels (Conv2d 96 -> 98 in, new weights zero; epoch 0 == baseline asserted) | 9.76 / 28.29 | 58 (never stopped) | 4.115 |
| **(ii) per-card bias map [10, 432] init log(count+1)** | **15.44 / 46.61** (s1 16.24 / 46.41, s2 15.14 / 46.51) | 35 | **3.52** |
| (i)+(ii) | 15.54 / 46.91 | 35 | 3.519 |
| bias map only, convs frozen (control) | 12.75 / 40.94 | 60 | 3.889 |
Coordinates alone do not let the head learn the static map in this budget (x_bow top-1 0/91, CE still
falling at 60). The prior-initialised bias map beats the control from epoch 2 (13.25 at ep 1, 14.04 at
ep 2); the gain is mainly top-5 (+6.6, ~4 SE) and CE (-0.36 nats); top-1 +1.8 is ~1.7 SE. Epoch 0 of
(ii) = 9.16 / 32.47: the source head's logits DEGRADE the prior by 4.5 pt. The convs of the bias run
scored without the map: 6.77 / 20.12 -- the head learned a residual on the map, not the map itself.

**Checkpoint / code consequence.** Neither wrapper fits the source dict layout: a [10, 432] map cannot
fold into `cell_conv.4.bias` [10] (which sits BEFORE the 12x8 -> 24x18 bilinear upsample). Each saved .pt
keeps `model` = the strict-loadable part plus `bc_pro_extra` (`cell_bias_map` / `cell_conv.0.weight_coord`);
reload through the wrapper reproduces the val number. To use it, the policy needs ONE addition:
`cells = cells + cell_bias_map[None]` before the tanh cap -- 4,320 floats, loaded as zeros when a
checkpoint lacks the key. That is the only modification that paid, and it is where the live-vs-training
model change would have to go (model.py, not env.py). Not done here; owner's call on the model change.

**Not done / caveats.** No `train-sim-ppo --resume` from any BC checkpoint (E was running). M1 kNN k /
alpha not CV-selected. coord / both / biasonly single-seed. All on dataset v1 (sim boards); v2 (engine
boards) is being built (L61).
