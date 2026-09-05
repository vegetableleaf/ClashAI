# IL / BC AUDIT -- ClashBot (icebow), 2026-09-05 13:4x UTC (Explore agent, read-only; transcribed by the loop)

## 1. Imitation / behaviour-cloning history
- BC machinery EXISTS and HAS BEEN RUN on YouTube footage, not on the crawl:
  - `icebow/src/clashrl/train_bc.py` (321 L): predicts (card, cell) from obs+hand; `_demonstrated_cell_logits` L52; group-wise val split by session, early stopping.
  - `icebow/src/clashrl/replay_bc.py` (538 L): pro footage -> BC dataset; ch 0-2 canonical synthetic re-render matching `sim/view.render_obs`, ch 3-8 `detect_obs.detection_channels`; team from arena half first seen + tracker.
  - Output `icebow/data/replay_bc/HunterCR_{1..4}_trimmed/dataset.npz`: obs (N,96,64,12), N = 95 + 481 + 189 + 388 = 1,153 samples, 4 videos, 1 player. Own-play sessions 30+16+150 = 196 samples (3-ch, stale).
  - HANDOFF.md:2746-2751: pipeline `label --all --size 432` -> `replay-bc --jobs 4` -> `train-bc`; "Current BC set is small: 1,142 replay samples + 39 session samples". No BC winrate recorded; superseded by sim PPO.
- BC on the RoyaleAPI placement crawl was PROPOSED and REFUSED by the owner: HANDOFF.md:5202-5207 "Owner ruling on replay-data use: NOT BC pretraining" -- grounds: three distillation nulls + no reconstructable states (sim-parity drift) + 50-75k plays too thin. Approved: board-blind placement priors, continuation stats, eval anchors.
- The three nulls (HANDOFF.md:10368-10375, `research/sim_parity/ledger/distillation.md`): (1) CARD choice distils (agreement 0.4955 -> 0.8754) but moves winrate +3.0pp / +0.63 sigma over 3 seeds; (2) the GATE does not distil from one frame (0.5892 -> 0.6012, below the always-WAIT floor 0.7756); (3) DAgger interval 4 co-existed with a banking collapse (>=6 share 35.4% -> 1.0%). All three were SIM search-teacher distillation, card/gate heads -- the CELL head was never distilled from anything.
- Placement-prior nulls (board-blind priors): §5ae (HANDOFF:5127), §5am (:5365, 1/3), §5ao (:5422, CLEAN FAIL 0/3); :5437 "placement priors alone don't move behaviour".
- In the trainer today (`train_sim_ppo.py`): distillation term L137-138/274-303/1637-1662 (CARD head only, sim search teacher); gate prior KL L345-381/1745-1754; DAgger L1883+.
- Gate priors are BOARD-BLIND: `config/gate_prior.json` / `gate_prior_p6.json` from `data/royaleapi/crawl2/plays_ext.csv` (519 replays, 23,620 blue plays); condition on elixir bucket x phase (+ one "enemy play in last 6 s" bit). HANDOFF:8171 "the prior is board-blind". `tools/replay_priors.py` fits P(tile | card, phase) on an 18x32 tile frame (policy grid is 18x24).

## 2. Pro placement corpus
- `icebow/data/royaleapi/crawl2/`: battles.csv 520 battles (29 cols), plays_ext.csv 45,335 rows / 519 replays / 122 cards; rows with tile coords 22,927 (50.6%); blue 23,620 / red 21,715 (BOTH sides). Join is bimodal: 268 replays join >80%, 251 <20% (HANDOFF:5213, §5ag) -> 12,220 blue plays with tile coords. Per-card blue: x-bow 1,038 / tesla 1,705 / the-log 1,802 (HANDOFF:2565).
- players_done.json 35 tags (24 with icebow battles), replays_done.json 520, roster.json top-50 icebow roster (ratings 3429 down). Source: RoyaleAPI top-50 rated icebow players, pathOfLegend.
- Fields per play: replay_tag, play_index, tick (20 Hz), seconds, x_units, y_units (1000/tile), tile_x, tile_y, attr_ability, attr_card, attr_s (side), attr_t. NO HP / unit list / board snapshot -- but the board is RECONSTRUCTABLE by replaying both sides' commands: real engine `research/sandbox_tools/replay_drive.py` 211/268 converted, 99.2% plays accepted, crowns match 77.7% (§5ay); our sim `scratchpad/gauntlet/L51/sim_replay_drive.py` reproduces the same 211 at 26.1% crowns-match (§5cs.21), 26.5% after three mechanic fixes (§5cs.22) -- the X-Bow side loses 188 of the 211 it really won 129 of.
- The n=807 pro Tesla plays (L58/L59 gate) = the subset inside the 211 converted replays; `scratchpad/gauntlet/L58/gate_plays.csv` 6,639 rows (per pro placement: reconstructed sim board scored, pro tile, 26 candidate tiles).
- Frame: blue own half = high y; tesla median tile_y 20.0; same orientation as the engine (§5ag).

## 3. Crawler
- OUTSIDE the repo: `C:\Users\benpe\clash-replay-scraper\crawl_icebow.py` (280 L) + `crawl_deck.py`, `scrape.py`, `royale/` package. Source: RoyaleAPI web, login-gated `/data/replay`. Needs a RoyaleAPI session cookie from a browser or interactive login; Cloudflare `cf_clearance` rotates/expires (`ClearanceExpired`). Token in `crawl2/.session_token` (32 B, 2026-09-04 22:30). No emulator/ADB/Supercell token. PLAYERS_CAP 50, PAGES_PER_PLAYER 5 (10 battles/page). Output hard-coded to `icebow/data/royaleapi/crawl2`; resume-safe via players_done/replays_done. Yields PLACEMENTS (every data-* attribute kept). Second run for hogeq: `scratchpad/gauntlet/L4/crawl_hogeq*.log`, output `hogeq/data/royaleapi/crawl2/`.
- In-repo fetchers mine no placements: `cr_web.py` (wiki/meta), `deck_import.py` (official API decks), `roboflow_fetch.py`, `record.py`/`label.py` (own-play recorder). No YouTube/statsroyale/in-game-replay recorder.

## 4. Observation / action interface
- Obs (96, 64, 12): 3 image + 6 detection canvases (enemy_ground/air/building, my_ground/building, spell) + 3 predictive; `detect_obs.obs_in_channels` L102-110; `sim/env.py:128,149`. Side vectors: hand (8), nexts, elixir, threats 34 live (`config.yaml:194`; train-bc caps at 16).
- Action: `actions.py:156-198`, grid [18, 24] = 432 cells (`config.yaml:499`), cell head (B, n_cards, n_cells) row-major; live masking removes 12 cells; `model.py:57` default n_cells 576 (sized from config at construction).
- Frame mismatch for BC: corpus/`replay_priors.py` are 18x32 engine tiles; policy grid 18x24. `L58/gate_replay.py:26-27` records a mis-conversion retraction; true centres via `env.actions.cell_center` (235 -> (1.5,18.0), 423 -> (9.5,31.33), 426 -> (12.5,31.33)).
- Converters: `replay_bc.py` (video -> obs), `L51/sim_replay_drive.py` (timeline -> sim state), `L58|L59/gate_replay.py` (hook before each accepted pro deploy -> `gate_plays.csv`). Adding a `render_obs` call at that hook yields BC pairs directly. No `from_replay`/`replay_to_obs` exists.

## 5. Winrate history (as recorded)
- HANDOFF_ARCHIVE.md:372 early live play: 0.87% over 805 matches.
- 2026-08-26 §4t 40k run: @16000 ladder 43% (avg-5 33%), @18000 PEAK 34% (avg-5 33%), fair 26%.
- HANDOFF:4048 policy_BEST_m18000 11.3% +-5.1 (n=150); :4374 §5r same run 18.8% and 6.2% 800 matches apart.
- 2026-09-01..02: 11%, 6%, 2%, 12%/8% (various arms).
- 2026-09-03 gatec2 m2/4/6/8/10k: 2/12/23/27/25%; gate05 5/13/17/8/10%.
- 2026-09-04 c2r: @2k..@18k 19 31 29 30 29 30 19 30 33%; @24-30k 31/27/23/31; c2r_best @36000 avg-5 31% (fair 21%); 8k->36k ladder avg-5 28-31 FLAT, fair 19-21 FLAT.
- 2026-09-05 armG: 37/39/27/23/36/27/35% m2k-m14k.
- Standing caveat: winrate is not a discriminator at n=16-150 (+-8pp).

STATUS: complete
