
## L61b (2026-09-05 15:2x-15:5x UTC) -- owner rulings applied: bias map in model.py; bcA (PPO from the BC init, control) LAUNCHED; crawl wins-first
- Q1 yes -> `PolicyNet.cell_bias_map` (78e14aa): old checkpoints bit-identical, native BC heads reproduce v1/v2 numbers exactly,
  suite 1,336/1,337 (1 pre-existing). Rail guard cell criterion max -> p99 (would have shrunk the BC init's convs x0.2).
- bcA launched 15:5x UTC: init bc_bias_native_s0 (15.44/46.61 sim, 15.00/43.51 engine), c2r config, one change = the init.
  Guard: "raw p99 9.5 within 2x cap -- left as loaded". Reads at m2k/m5k: does PPO keep or erode the pro agreement?
- Q2 (owner): mine ~10k icebow replays 10k trophies -> top, wins first; IL + 10k-deck pool + trophy-range ghosts + self-play
  opponent. Pushbacks: pro-weighted IL teachers; general-deck opponent needs a card-identity head; league not pure
  alternation; losses are the opponent-side signal; supply/rate unmeasured (~2 replays/min this wave).
- Wave 4: roster 50 -> 150, 1,445 battles, 834 replays queued, relaunched wins-first.
