# Deck switch runbook — Rocket Cycle → Miner X-Bow Control

**Status:** Phase 1 code is DONE and on `main`. Waiting on the user to RE-RECORD with the new
deck before Phase 2. This file is the single ordered source of truth for the switch — read it
first (human steps in §1, AI/code steps in §2, reward audit in §3, roadmap in §4).

**Deck (Classic 1v1, ALL cards level 11):** Evo Tesla, Miner, X-Bow, Ice Wizard, Skeletons,
Electro Spirit, Rocket, Royal Delivery. (Gone vs the old deck: Tornado, Ronin, Ice Spirit.)

**Doctrine:** X-Bow = win condition, placed FORWARD on your side just behind the bridge, within
its ~11.5-tile range so it locks the enemy princess tower (back-centre = a defensive sniper
fallback). Miner = chip the tower / tank / snipe support, deploys ANYWHERE. Rocket = clear big
pushes, or cycle-chip the tower in 2×/3× elixir. Cheap cards (Electro Spirit / Skeletons) cycle
and stall; defenders (Tesla / Ice Wizard) clean up.

---

## 1. What the USER must do, in order (training device)

1. `git pull origin main` (get Phase 1).
2. **Re-record from scratch with the new deck.** The BC dataset is deck-specific — old recordings
   teach dead cards (Tornado/Ronin/Ice-Spirit) and none show Miner/X-Bow play, so they are useless
   for this deck. Play many matches: `python run.py record` → Ctrl+C after the results screen.
3. **Rebuild card templates** (needed before labeling — hand recognition is template matching):
   `python run.py hand-templates` → rename each `_cand_*.png` crop to its deck key:
   `royal_delivery.png`, `tesla_evo.png`, `ice_wizard.png`, `x_bow.png`, `rocket.png`,
   `miner.png`, `electro_spirit.png`, `skeletons.png` (extra crops of one card: `<key>_2.png`).
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
   check `env.xbow_defense_y`.
2. **Phase 2 gameplay mechanics:**
   - Time-based **2×/3× elixir reader** (read the match CLOCK, reuse the tower-HP digit OCR) → gate
     rocket-cycle-on-tower behaviour.
   - **Miner** tank-for-X-Bow (drop at the bridge to pull troops off a fresh X-Bow) + snipe a support
     card behind an enemy tank.
   - **X-Bow-protect** micro (defend it while it chips).
   - **Electro Spirit** stun/reset shaping.
3. Continue **Stage 2/3** (object detector → semantic obs) and **Stage 4** (replay strategy mining)
   on their own tracks — deck-agnostic, unaffected by this switch.

## 3. Reward-parameter audit (Miner X-Bow deck) — decisions

DONE in Phase 1 / this change:
- ADDED: `xbow_wc_reward` (X-Bow in tower range = win condition), `xbow_defense_reward` (back-centre),
  `xbow_misplace_penalty` (forward but out of range), `miner_chip_reward` (Miner on enemy princess),
  `xbow_wrong_lane_frac` (see below), and geometry `env.xbow_range` / `env.xbow_defense_y`.
- CHANGED doctrine: Miner + X-Bow are EXEMPT from the enemy-half `offensive_penalty`. Miner is fully
  exempt from the wrong-lane penalty (it deploys anywhere). X-Bow opposite-lane is now nuanced —
  exempt when punishing a SPENT push, but pays `wrong_lane_penalty × xbow_wrong_lane_frac` (0.6) if a
  REAL push is still LIVE (`enemy_mass ≥ env.threat_mass`), because leaving it undefendable is bad.
- INACTIVE (no Tornado/Ronin in the deck — code paths are inert, knobs marked in config, do NOT tune):
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

- **Stage 3:** object detector (YOLO11) → per-unit semantic obs into PolicyNet. Prereq for 4 & 5.
- **Stage 4:** external-replay strategy mining (`replay_mine.py`, gated by `rewards.strategy_prior_scale`).
- **Stage 5 (NEW, post-Stage-3): learned dynamics / world model.** A model that predicts the NEXT board
  state from the current state + action (e.g. a placed troop advances toward its nearest target). Trained
  first (supervised on recorded transitions), then used to help RL — this is model-based RL (Dreamer /
  MuZero family). It should operate on the DETECTOR's structured entity state (units = {type, x, y, hp,
  team}), NOT raw pixels, which is why it is firmly POST-Stage-3. See log.txt for the full design note.

## Conventions
- Reward-shaping changes only take effect on the next `train-rl`.
- Every change is committed AND pushed to `origin/main` (autopush).
- `data/` (recordings, weights, templates output, mined priors) is git-ignored → per-device; only code
  and config sync via git.
