
## L60b (2026-09-05 14:5x-15:3x UTC) -- kNN vs BC vs baseline on 1,004 held-out pro placements: board-blind card prior 13.65/40.04 is the bar; c2r_best 3.49/11.75; trunk embedding near-constant; cell head at the tanh rails
- Same val rows, pro card's masked map. Card prior (no board) 13.65 / 40.04. kNN raw-PCA-256 k=15 gauss
  16.24 / 36.16 (+2.6 pt top-1 ~2 SE, marginal; never beats the prior on top-5 below k=150). Trunk
  embedding z is the WORST key (12.15) and near-constant: pro-to-pro NN cosine median 0.991 vs raw 0.562.
  BC head-only 8.27/8.27/8.37 (3 seeds), trunk ft 8.47 -- below the static prior; x_bow 0/91. (a)
- MECHANISM: c2r_best cell head at the tanh rails, 92.4% of masked raw logits |raw| > 8 (mean -23.6),
  gradient 1e-2..1e-6 -> PPO cannot move it; head-only BC without repair returned the untouched checkpoint.
  Shipped BC ckpts rescale cell_conv.4 /10.36. (a) Prior nulls §5ae/5am/5ao may be dead-gradient artefacts (b).
- Unresolved: uninformative boards (26% sim) vs stereotyped deck -- separators: real-record-feature
  conditioning (cheap), engine dataset v2. Also untested: coordinate channels / prior-initialised bias.
- Owner: stop E after m5k (E at ~2.6k eps, m5k ~15:5x UTC); then engine work.
