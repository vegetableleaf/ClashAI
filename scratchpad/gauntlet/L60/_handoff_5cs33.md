
### §5cs.33 -- L60 (2026-09-05 13:4x-14:4x UTC): OWNER PIVOT TO IMITATION LEARNING -- IL audit written, crawl wave 3 (+88 replays, 520 -> 608), first PRO-PLACEMENT BC DATASET built (6,922 samples / 268 replays, policy-format obs from sim-reconstructed boards), c2r_best agrees with the pro cell 3.3% top-1 / 10.9% top-5 (chance 0.6 / 3.1); owner's kNN-over-board-embeddings idea and "rebuild the sim on the sandbox engine" answered; question open: stop arm E after its m5k read?

**Owner (13:3x UTC):** "Every day the model strays further ... from sensible play ... going in circles ... give
imitation learning a chance (train the model directly on pro placements first before sim) ... make sure the
sim gradient points towards how pros actually play given certain board states (case by case, not
generalized) ... do another crawl in the background for players you haven't mined yet." Follow-up (14:1x):
similarity via a RAG-style board-embedding vector space (normalised dot product, every tick of every
replay); and "if parity really is this low ... use the sandbox engine to rebuild the sim".

**Assessment given (labels as stated to the owner).** (a) 10-day flatness is measured: c2r ladder avg-5
28-31% from 8k to 36k, every arm since 25-39% (inside +-8pp); every arm resuming from c2r_best re-collapses
the cell head within ~10k matches (G: knight 41/41 by m10k; c2r itself late). "Since day 1" is NOT one
number (live 0.87%/805 vs sim eval = two instruments). (b) Circle diagnosis: (1) every arm starts from the
same saturated head (raw absmax 105, guard x0.043, re-saturates) and is compared to a checkpoint, not a
control run; (2) in our sim pro play LOSES (211 real timelines: 26.1% crowns-match vs 77.7% in libg,
§5cs.21) so PPO is pushed away from sensible play; reward shaping cannot fix that. IL: agreed, with the
earlier refusal (HANDOFF:5202) re-examined -- two of its three grounds changed (states reconstructable via
the gate_replay hook; the distillation nulls were card-head / in-sim-teacher, the cell head was never
trained on anything), the third (thin corpus) stands and is why the crawl matters. Pushback on "case by
case": no two boards repeat, so any lookup needs a similarity rule and that rule is a model; the honest
version is per-card/per-situation held-out agreement scoring. The "sim gradient toward pros" request maps
to the parked cell-head KL-to-prior arm (gate prior KL plumbing at train_sim_ppo.py:345-381).
On the kNN idea: raw-vector cosine is blind to the one unit that matters (hog at tile 15 vs 17 barely
moves the cosine), so the embedding must be learned = the trunk; kNN over a learned embedding is a
legitimate non-parametric policy with real advantages here (cannot collapse to one tile, interpretable,
updates without retraining). Every tick = ~1.1M near-duplicate states; only deploy ticks carry a placement
label (6.9k now), the rest label "pro waited" (gate). Coverage (519 games, ~40 opponent archetypes, ~10
games each) and the bot's off-distribution boards are the limits -- both measurable (leave-one-replay-out
agreement; bot-state-to-nearest-pro distance vs pro-to-pro). Decision: build BOTH kNN and BC net on the
same dataset, score on the same held-out replays, the winner becomes the KL prior.
On the sandbox: corrected the premise -- the engine already RUNS here (§5ax: tick stall solved, 211/268
replays convert at 77.7%, 1.7 s/match, ~2000 matches/h one worker, deterministic). Three uses ranked:
(1) engine per-tick state as the BC state source (77.7% vs 26% fidelity; needs an engine-state -> obs
renderer, untested), (2) engine as the RL environment -- one throughput experiment decides (observe cost
per decision tick, RAM/VM, workers/VM; no built-in opponent, levels forced to 11, 22% still diverge),
(3) engine as a per-mechanic oracle (slowest; 3 fixes gave 26.1 -> 26.5%). RAM conflict with arm E (7.4 GB).

**Done this loop.**
- IL audit written to `scratchpad/gauntlet/L59/il_audit.md` (from an Explore agent's read-only report;
  corrects one item: `.session_token` is dated 2026-08-30, not 09-04).
- Killed the hung `scratchpad/bb/stt.ps1` (PID 22200, 2.37 GB): available RAM 1.31 -> 3.40 GB. (a)
- **Crawl wave 3** (`C:\Users\benpe\clash-replay-scraper\crawl_icebow.py crawl`, saved token accepted, no
  login needed; log `L60/crawl_icebow_wave3.log`): 15 unmined roster players walked, 11 completed, 4
  RateLimited (retry next run: L8GVPJ900, 2PLQLRGQR, GRUGJPJGV, 2PY2228U9); **+88 replays in 17 min**
  (replays_done 520 -> 608, players_done 35 -> 46, plays_ext.csv 45,335 -> 52,587 rows). (a) The roster
  is the top-50 icebow players; a wave 4 beyond it needs a re-ranked roster (delete/rename roster.json).
- **BC dataset v1** (`L60/build_bc_dataset.py`, notes `L60/bc_dataset.md`; outputs `icebow/data/bc_pro/`
  dataset.npz in train-bc format, obs [6922,96,64,12] uint8, meta.csv, meta_oov.csv, split.json,
  drive_summary.jsonl, report.txt): drives each of the 268 usable replays through OUR sim (L51 driver,
  blue-focus mirror as `--mirror`, real `SimMatchEnv` obs pipeline with `env.eng` swapped, domain_rand
  off) and records the policy's own obs + side vectors immediately before each accepted pro deploy.
  6,922 samples (blue 6,836, red 86 -- the icebow deck is the BLUE deck in 268/268 usable replays, so red
  plays are out of vocabulary and go to meta_oov.csv, 6,069 rows), median 26/replay; cards: skeletons
  1170, ice_wizard 1099, the_log 1027, knight 881, tesla 726, x_bow 637, tornado 508, rocket 356,
  knight_evo 289, tesla_evo 229; top cells 422:294, 423:269, 237:265, 248:259, 296:246; time buckets
  0-60 s 1790 / 60-120 1694 / 120-180 2709 / 180+ 729 (median 119 s). Hands from the engine records
  (213/270 drives) agree with `hand_before` at 5,705/5,753 plays (0.8% flagged); 57 drives use a
  heuristic queue (`hand_certain` 6,694/6,922). Cells via `env.actions.cell_center` nearest (snap mean
  0.379 tiles, max 0.833). Split by replay 228/40 tags = 5,918/1,004 rows, seed 0. 4 workers, ~1 min,
  ~80 MB/process. (a)
- **Baseline agreement of c2r_best_36k_backup.pt with the pro cell** (pro card's cell map, policy mask):
  **top-1 3.26%, top-5 10.92%** (chance for a troop over 160 deployable cells 0.63 / 3.1). Per card
  top-1/top-5: the_log 11.39/37.59, skeletons 4.19/10.85, knight 2.27/7.26, tornado 1.77/5.31, rocket
  1.69/10.67, ice_wizard 1.36/4.82, tesla 0.69/2.75, x_bow 0.00/0.31. By time 0-60 s 4.64/14.08, 60-120
  3.19/10.51, 120-180 2.58/9.63, 180+ 2.61/8.92. The checkpoint's top-1 sits on cell 235 for 27% of
  samples. Card head (in-hand + affordable mask) picks the pro's card 43.35%. (a) These are the numbers
  every IL arm is measured against.
- Arm E kept running: 2,200 episodes, 4%, avg_rew -20.9, 0.7 ep/s at 14:3x UTC; m5k read ~15:1x UTC.

**What the dataset does NOT establish / caveats (measured where numbered).** The boards are OUR sim's
reconstruction (26% crowns-match): 43.5% of pro plays (5,348/12,306) fall AFTER the sim's own end (sim
ended before the last play in 219/270 drives; median sim end 180 s vs last play 281 s; crowns match
73/270) -- late-game coverage is thin and biased toward early divergence. No per-tick tower HP in the
engine records, so state-match is proxied by elixir (sim vs engine `elixir_before` |diff| median 0.07,
mean 0.27, >2 in 0.9%) and towers-alive (all six alive at 68.5% of samples). One driver nondeterminism:
020YPYQ22GY2 differs between runs (sim end 268.9 vs 271.0 s, labels identical); 269/270 bit-exact. The
"v2" of this dataset should come from the sandbox engine's per-tick state (route 1 above).

**Traps.** (1) `train_bc`'s loader globs `root/*/dataset.npz` and splits val by FILE order -- to honour
`split.json`, subset rows by its indices (see bc_dataset.md). (2) The crawler's `Pages()` is a headful
Playwright Chrome; with a valid saved token no window opens. (3) The corpus is one-sided for BC: red-side
plays are almost never the icebow deck. (4) `PLAYERS_CAP 50` roster = "players you haven't mined" is
exhausted after the 4 rate-limited retries; more data means a new roster.

**Open question to the owner (asked 14:2x UTC, unanswered):** stop arm E after its m5k read and give the
box (RAM) to the sandbox-engine work (state dump -> obs renderer -> BC v2; throughput experiment)? Until
answered: kNN-vs-BC comparison on dataset v1 proceeds beside E.
