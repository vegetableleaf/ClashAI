
### §5cs.38 -- L61b (2026-09-05 15:2x-15:5x UTC): OWNER RULINGS (Q1 yes: bias map in model.py; Q2: mine ~10k icebow replays 10k-trophies->top, wins first, IL + 10k-deck pool + trophy-range ghosts + self-play opponent) -- model.py `cell_bias_map` landed bit-identical for old checkpoints (78e14aa); rail guard cell criterion -> p99; **bcA LAUNCHED 15:5x UTC** = PPO from the BC-initialised head (15.44/46.61 sim, 15.00/43.51 engine) with the c2r config -- the CONTROL of the IL-init pair; wave-4 crawl relaunched wins-first (150-player roster, 1,445 battles kept, 834 replays queued)

**Owner (15:2x UTC).** Q1: "Yes". Q2, a different proposal: mine random icebow replays from 10,000 trophies (the
bot's current range) to top ladder, concentrated around the bot's range, ~10,000 matches; use them for IL, to grow
the opponent deck pool 1,000 -> ~10,000 distinct decks, and as trophy-range "ghost" opponents; PLUS self-play: the
model pilots the opponent side, learns to counter icebow, icebow learns to answer, alternating. "Scripted adaptation
is bad because opponent responses vary across and within matches." Then (15:4x): "prioritize matches where the icebow
deck actually wins." Pushbacks given in the reply (all (b) unless marked): (1) IL teachers should stay pro-weighted --
10k-trophy placements teach 10k-trophy play; range-matched data belongs on the OPPONENT side; (2) a general-deck
opponent policy needs a card-identity action head (the current card head is the 10-slot icebow deck) -- a larger
architecture change than the bias map; (3) alternating self-play is the textbook cycling setting; keep past opponent
checkpoints in the pool (league); (4) wins-first is right for IL but the LOSSES are the informative half for the
opponent model -- fetch both, tag them; (5) supply is unmeasured: RoyaleAPI exposes ~198 rated icebow players on the
deck boards; 10,000 replays needs either ~1,000 players or deeper histories, under a rate limit measured at ~2
replays/min this wave (a). (6) (a) engine throughput 920-1,516 matches/h/VM -> a self-play phase of 30k matches is
~1 day per VM.

**Model change (78e14aa).** `PolicyNet.cell_bias_map` [n_cards, n_cells] zeros, added in `_cell_logits` before the
tanh cap; `load_state_dict`/`load_compat` fill a missing key with zeros. (a) Old checkpoint (armE snapshot) through
old vs new code: z, cards, cells bit-identical (max |d| 0.0); `load_compat` drops nothing. (a) The three L60
wrapper heads converted to native checkpoints (`bc_pro/models/bc_bias_native_s{0,1,2}.pt`) reproduce exactly: v1
15.44 / 16.24 / 15.14, v2 15.00 / 14.63 / 14.93. Unit suite 1,336/1,337; the 1 failure (`test_xbow_into_push`
clamped-row) fails on HEAD too. Live-play path untouched (env.py); live inference of any existing checkpoint is
unchanged by construction (zero map).

**Rail guard change (this loop, `train_sim_ppo.py`).** The cell criterion was `absmax > 2 x cap` and rescaled
`cell_conv[-1]` only. (a) The native BC heads reach absmax 20-28 on v1 val boards with p99 ~6 by construction, so
the max rule would have shrunk the conv residual x0.2 on load and left the bias map alone -- silently changing the
init under test. Now: p99 of |raw| over the 8 probe states > 2 x cap fires (c2r_best-class heads, p99 62, still
trip); otherwise it prints the p99/absmax and leaves the head. bcA's launch line: "raw p99 9.5 (absmax 19) within 2x
cap -- left as loaded". Consequence for any future resume of a SATURATED head: the factor is 4.5/p99 not 4.5/absmax
(E's would have been x0.073 instead of x0.043) -- no such resume is planned.

**bcA launched 15:5x UTC** (`data/bench/bcA_run_launch.sh`, `bcA_run.yaml`, log `bcA_run_20260905.log`, init
`policy_bcA_20260905.pt` = `bc_bias_native_s0.pt` sha a1273d5d..., source kept). Config = `armE_run.yaml` with
`sim.ppo_cell_entropy_floor` back to c2r's 0.008 and the bcA paths -> key-level diff vs `c2r_run.yaml` is the
checkpoint/continuation paths plus the absent-vs-default / live-only keys already audited in §5cs.3x (G). ONE
change vs c2r: the init. `--resume --matches 40000 --envs 96 --workers 12 --size 432 --seed 41 --search-interval 4`.
Box before launch: 9.96 GB free, 40% CPU (crawler + Nucleo), python 3. First line: 25 episodes, 0.4 ep/s. Reads
planned at m2k / m5k with `L60/rails_read.py` + `L60/knn_vs_bc.py baseline` (pro agreement on v1 val) +
`L61/knn_vs_bc_v2.py baseline` (engine val) + place_probe: the question is whether PPO KEEPS the 15/46 pro agreement
or erodes it (c2r_best is at 3.5/11.8). The arm half (same init + per-board KL-to-pro-prior on the cell head) needs
trainer code; it launches after bcA's m2k read so the pair shares the box fairly.

**Crawl wave 4.** `crawl_icebow.py expand 150` (new mode, re-ranks the boards, grows the roster): 50 -> 150 players
(198 on the boards), histories walked 124/150 (RateLimited retries pending), 1,445 battles kept, 834 replays queued;
relaunched 15:4x with the owner's wins-first order (`todo.sort` by result == win, then rating). Measured pace this
wave: 80 replays in 42 min (~2/min, RateLimited errors are retried next run). Log `L61/crawl_icebow_wave4.log`.
