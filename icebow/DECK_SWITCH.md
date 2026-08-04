# Deck switch runbook — Rocket Cycle → Miner X-Bow Control

**Status:** Phase 1 code is DONE and on `main`. Waiting on the user to RE-RECORD with the new
deck before Phase 2. This file is the single ordered source of truth for the switch — read it
first (human steps in §1, AI/code steps in §2, reward audit in §3, roadmap in §4).

**Deck (Classic 1v1, real account levels):** Evo Tesla, Miner, X-Bow, Ice Wizard, Skeletons,
The Log, Rocket, Tornado. (2026-08-04: Tornado swapped back in for Royal Delivery. Earlier icebow
swap: Electro Spirit → The Log. Gone vs the pre-icebow deck: Ronin, Ice Spirit.)

**Doctrine:** X-Bow = win condition, placed FORWARD on your side just behind the bridge, within
its ~11.5-tile range so it locks the enemy princess tower (back-centre = a defensive sniper
fallback). Miner = chip the tower / tank / snipe support, deploys ANYWHERE. Rocket = clear big
pushes, or cycle-chip the tower in 2×/3× elixir. Cheap cards (The Log / Skeletons) cycle
and stall; defenders (Tesla / Ice Wizard) clean up.

---

## 1. What the USER must do, in order (training device)

1. `git pull origin main` (get Phase 1).
2. **Re-record from scratch with the new deck.** The BC dataset is deck-specific — old recordings
   teach dead cards (Tornado/Ronin/Ice-Spirit) and none show Miner/X-Bow play, so they are useless
   for this deck. Play many matches: `python run.py record` → Ctrl+C after the results screen.
3. **Rebuild card templates** (needed before labeling — hand recognition is template matching):
   `python run.py hand-templates` → rename each `_cand_*.png` crop to its deck key:
   `tornado.png`, `tesla_evo.png`, `ice_wizard.png`, `x_bow.png`, `rocket.png`,
   `miner.png`, `the_log.png`, `skeletons.png` (extra crops of one card: `<key>_2.png`).
   Then the next-card previews under `templates/next/`. Verify: `python run.py verify --hand`.
4. **Re-verify tower calibration:** `python run.py verify --towers` (should be unchanged; recalibrate
   only if the window moved).
5. Build data: `python run.py label --all` then `python run.py outcomes --all`.
6. `python run.py train-bc` (imitation baseline).
7. `python run.py train-rl` (live RL fine-tune; Discord monitor optional). Tip: consider deleting
   `data/policy_rl.pt` first so the gate re-learns from the new BC start.

## 2. What the AI does AFTER footage exists (needs real frames to calibrate)

1. **Calibrate `env.xbow_range`** (currently 0.36 ≈ 11.5 tiles) against `verify --towers` frames so
   the X-Bow win-condition reward fires exactly when it can reach the enemy princess. Also sanity-
   check `env.xbow_defense_front` / `env.xbow_defense_back` (the defensive centre band).
2. **Phase 2 gameplay mechanics:**
   - Time-based **2×/3× elixir reader** (read the match CLOCK, reuse the tower-HP digit OCR) → gate
     rocket-cycle-on-tower behaviour.
   - **Miner** tank-for-X-Bow (drop at the bridge to pull troops off a fresh X-Bow) + snipe a support
     card behind an enemy tank.
   - **X-Bow-protect** micro (defend it while it chips).
   - **The Log** knockback/reset + conditional cycle-chip shaping (only chip-cycle when Skeletons is unavailable, there are no enemy targets to Log, AND you're at full elixir). **[DONE (reward-shaping): `env._log_reward` + `log_cycle_ok` in `step()` — The Log now has its own path (was mis-scored as a Tornado). Coarse point-at-cast pixel proxy for now; a true roll-path read waits on the detector.]**
3. Continue **Stage 2/3** (object detector → semantic obs) and **Stage 4** (replay strategy mining)
   on their own tracks — deck-agnostic, unaffected by this switch.

## 3. Reward-parameter audit (Miner X-Bow deck) — decisions

DONE in Phase 1 / this change:
- ADDED: `xbow_wc_reward` (X-Bow in tower range = win condition), `xbow_defense_reward` (back-centre),
  `xbow_misplace_penalty` (forward but out of range), `miner_chip_reward` (Miner on enemy princess),
  `xbow_wrong_lane_frac` (see below), and geometry `env.xbow_range` / `env.xbow_defense_front`+`_back`.
- CHANGED doctrine: Miner + X-Bow are EXEMPT from the enemy-half `offensive_penalty`. Miner is fully
  exempt from the wrong-lane penalty (it deploys anywhere). X-Bow opposite-lane is now nuanced —
  exempt when punishing a SPENT push, but pays `wrong_lane_penalty × xbow_wrong_lane_frac` (0.6) if a
  REAL push is still LIVE (`enemy_mass ≥ env.threat_mass`), because leaving it undefendable is bad.
- STALE (2026-08-04: these Tornado/Ronin knobs were removed in the later reward rebuild; Tornado is
  back in the deck but is now handled by the generic spell + reactive-spell paths, so do NOT tune these):
  `king_tank_reward`, `threat_tornado_pull`, `rocket_tornado_combo`, `tornado_chip_penalty`,
  `env.combo_window_steps` / `combo_radius` / `combo_kill_min`.
- KEPT (still valid): tower/win/loss terminals, `hp_scale`, spell rewards (Rocket/RD are spells),
  `tesla_kill`/`defense_kill`(+cap), `blocker_protect` (now Skeletons/Electro-Spirit/Miner shield Ice
  Wizard), `royal_delivery_hit/kill`, `threat_counter_delivery`, `siege_counter` (counter the ENEMY's
  siege), `offensive_penalty`, `defense_center_bonus`, `building_center_reward`/`misplace` (Tesla),
  `wrong_lane_penalty`, `ranged_ontop_penalty`, `rd_enemy_half_penalty`, `back_corner_penalty`,
  `premature_defense_penalty`, `cycle_reward`, `shaping_match_cap` (the anti-farm ceiling).
- TO RE-TUNE WITH DATA (do not guess now): relative weights of `xbow_wc_reward` vs `rocket_tower_reward`
  vs `miner_chip_reward` once train-rl shows which offense the policy over/under-uses.

## 4. Roadmap / stages

- **Simulator / self-play gym (BUILT — usable now): `run.py train-sim`.** A headless, medium-fidelity,
  stat-driven match engine (`clashrl/sim/`) driven by the card KB — elixir economy, lane movement with
  bridge crossing, nearest-target combat with splash, princess/king towers, area spells, and scripted
  opponent archetypes (hog-cycle / beatdown / control / siege). It trains the SAME `PolicyNet`/DQN with
  NO vision and FROM SCRATCH, thousands of matches fast, writing `data/policy_sim.pt` — a PRIOR to
  warm-start live RL. See §5.
- **Stage 3:** object detector (YOLO11) → per-unit semantic obs into PolicyNet. Prereq for 4 & the world model.
- **Stage 4:** external-replay strategy mining (`replay_mine.py`, gated by `rewards.strategy_prior_scale`).
  - **Sub-task — BC refinement from pro icebow replays (YouTube / public media).** Goal: clone strong
    icebow play so BC starts from a PRO-level policy (you're not a pro / don't know one). Now viable *in
    principle* because the deck matches your action space — BUT **gated on the detector (Stage 3)**: a
    video has no mouse log, so each play must be RECOVERED by the detector (spot a friendly unit spawn →
    its card + cell + the board state). **YouTube-specific caveat (the crux):** public footage is a
    DIFFERENT RENDERING than your Google Play window (resolution / skin / overlays / facecam), so (a) the
    hand/elixir/tower readers misread it and (b) BC clones *pixels*→action, so **raw-pixel BC from YouTube
    transfers poorly** — do NOT feed YouTube pixels straight into the image policy. Instead, once the
    detector is up: detector → STRUCTURED play (card, cell, entity board) → then ONE of:
    (i) **canonical re-render** the recovered play into your OWN synthetic top-down (like the sim's render)
    and BC on that — normalizes the visual, bridges the domain gap; (ii) train on the detector's
    **semantic obs** (the Stage-3 shared representation), rendering-independent by construction; or
    (iii) use the recovered plays as **reward priors** (robust to domain shift) rather than raw BC.
    Pipeline: `yt-dlp` the clips (personal research use; respect copyright/ToS) → per-frame detector read →
    recover `(obs*, card, cell)` plays filtered to icebow cards → EXTEND `replay_mine.py` to emit a
    `train-bc`-loadable `dataset.npz` (and/or priors). START only after the detector is trained + wired.
- **Self-play (sim) — BUILT (2026-07-30).** The opponent (team 1) can be driven by a FROZEN past copy of
  the agent's own policy on a MIRRORED board (`sim/view.py` 180° rotation), mixed with the scripted meta
  bots. `train_sim` snapshots the policy into a small league every `sim.selfplay_snapshot_every` matches;
  each reset picks a league snapshot with prob `sim.selfplay_prob` (ramped in over `sim.selfplay_ramp_matches`),
  else a scripted bot. See `sim/opponents.SelfPlayOpponent`. Defaults: prob 0.5, ramp 5000, snapshot 1000,
  league 5 (set `selfplay_prob: 0` to disable). This is ALSO the point where PPO starts to beat DDQN (see the
  PPO note) — consider trying PPO here later.
- **Stage 5 (post-Stage-3): learned dynamics / world model.** A model that predicts the NEXT board
  state from the current state + action (e.g. a placed troop advances toward its nearest target). Trained
  first (supervised on recorded transitions), then used to help RL — this is model-based RL (Dreamer /
  MuZero family). It operates on the DETECTOR's structured entity state (units = {type, x, y, hp, team}),
  NOT raw pixels, which is why it is firmly POST-Stage-3. NOTE: the `train-sim` engine is a HAND-CODED
  world model — the twin of this LEARNED one; they can converge later. See log.txt for the full note.

## 5. Simulator training (`train-sim`) — READY NOW, runs in parallel with recording

**Readiness decision: YES — start it.** The policy is ready to train in the engine from scratch: the sim
emits the exact observation the CNN expects (validated end-to-end — obs `(96,64,3)`, hand/next/elixir/threat
vectors, the same 9 card identities incl. Tesla's evo/normal split), matches terminate correctly, and the
reward gives a clean gradient (losses land clearly negative, wins ~+10). Unlike live RL — which needs a BC
warm-start because live matches are too scarce to learn from scratch — the sim provides effectively
unlimited volume, so from-scratch is the whole point, and **no recordings are needed to start**. It needs
PyTorch + a GPU (same as `train-bc`/`train-rl`).

PowerShell (training device, from `icebow/`):
```powershell
git pull origin main
# (optional) refresh opponents to the CURRENT top-100 meta decks — needs a free CR API token:
#   set the token in env CLASHRL_CR_API_TOKEN (from developer.clashroyale.com, IP-locked), then:
.\.venv\Scripts\python.exe run.py decks-import --limit 100      # else the curated 100-deck pool is used
.\.venv\Scripts\python.exe run.py train-sim --matches 20000 --envs 16   # START (from scratch); K vectorized envs
# monitor: watch the [train-sim] summary lines (winrate / avg_rew / m/s); policy_sim.pt updates every 50 matches
# END: press Ctrl+C any time — it saves data/policy_sim.pt on exit
.\.venv\Scripts\python.exe run.py train-sim --resume           # continue a previous run
```
Opponents are sampled from a pool of real meta decks (`config/meta_decks.yaml`) and piloted by their
inferred style (cycle / control / beatdown / siege). `--envs K` runs K matches in a vectorized learner
(batched inference + shared replay; single-process, so it's GPU-amortisation not multi-core — the engine
is cheap). Tune `sim.envs` and the pool/fidelity under the `sim:` config.

To then **warm-start live RL from the sim prior:** `copy data\policy_sim.pt data\policy.pt` (dims match the
deck/config), then `run.py train-rl` — it fine-tunes the sim policy on real matches to close the sim-to-real
gap. (Or keep BC and sim as two separate warm-starts and compare.)

**Honest limits:** medium fidelity — aggro/target-commitment, ~1s deploy, hit-speed combat,
slow/stun/freeze, soft-collision body-blocking, and king-on-chip ARE now modelled; still unmodelled:
exact CR pathfinding, champions, evolutions (Evo Tesla uses base stats), and per-card quirks
(charge / ramp-up). The observation is a crude synthetic top-down, so a sim-trained policy transfers as a
strategic/elixir/timing PRIOR, not a finished real-game bot. Tune fidelity/opponents under the `sim:` config
section; add self-play + more archetypes later. The engine is DECK-DRIVEN (reads `cards.yaml`), so deck
changes auto-apply on `git pull` — e.g. the Electro-Spirit→The-Log swap needs no engine change. (The Log is
modelled as a rolling ground-only knockback corridor.)

## Conventions
- Reward-shaping changes only take effect on the next `train-rl`.
- Every change is committed AND pushed to `origin/main` (autopush).
- `data/` (recordings, weights, templates output, mined priors) is git-ignored → per-device; only code
  and config sync via git.
