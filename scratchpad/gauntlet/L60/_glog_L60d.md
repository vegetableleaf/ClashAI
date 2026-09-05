
## L60d (2026-09-05 14:3x-14:5x UTC) -- board-value separators: real context adds <= +1.9/+4.7 over the card prior; prior-initialised bias map is the first BC above the prior
- M1 real-record context vs prior 13.65/40.04: time 12.95/38.94, engine elixir 14.54/41.93, opp last card
  13.45/37.85, opp last tile 15.54/44.72 (best), NB combo 15.44/42.13, real-vector kNN k=50 15.84/43.53.
  (a) Same size as the sim-board kNN gain (+2.6) -> the small board gain is not "wrong boards"; for this
  deck's placements the per-card prior is nearly everything; opponent's last lane/row is the one live feature.
  Card choice / timing NOT measured -- the "case by case" claim is untested for those heads.
- M2 head-only BC: coord channels 9.76/28.29 (x_bow 0/91 still); per-card bias map [10,432] init from the
  prior 15.44/46.61 (s1 16.24/46.41, s2 15.14/46.51), val CE 3.52 vs prior 3.88; coord+bias 15.54/46.91;
  bias only (convs frozen) 12.75/40.94. Source head's logits at epoch 0 DEGRADE the prior (9.16/32.47).
- Consequence: the policy needs `cells + cell_bias_map[None]` (4,320 floats) before the tanh cap -- a
  model.py change (not env.py), owner's call. Checkpoints carry it as `bc_pro_extra`.
- Next: L61 engine dataset v2 (running) -> re-score on engine boards; then the model change + BC init.
