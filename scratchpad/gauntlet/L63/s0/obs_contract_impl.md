# S0 step 2 -- obs contract implementation record (2026-09-06)

Spec: `scratchpad/gauntlet/L63/s0/obs_contract_spec.md`. Audits read: `obs_audit_engine.md`, `obs_audit_live.md`.
Source ranges read: `icebow/src/clashrl/actions.py:55-155` (BoardWarp), `replay_mine.py:66-96` (Detection),
`native_core/env.py:187-265` (observe/_enrich_state), `build_bc_v2.py:44-69` + `:100-158` (alias rules, mirror,
normalisation, tower slots, kind->deploying), `clashrl/cards.py:133-215` + `card_threat.py:34-45` (CardDB.kind /
base_key, needed to derive the 46 spell classes), `clashrl/config.py:13-50` (Config.get signature BoardWarp expects).

## Facts measured during implementation

- Detector vocab: `icebow/config/detect_classes.yaml` key `classes`, 230 names, 128 base keys after suffix folding.
  KB kinds via `CardDB.kind(base_key)`: 165 troop / 19 building / 46 spell (26 card + 20 `_aoe`) -- matches the audit.
- Catalog (`live_card_catalog.json`, 152 cards, 122 in use) display_name -> `_ALIAS_INV` + CamelCase->snake:
  all 122 in-use names land on a detector class. Names with NO detector class: `MergeMaiden_Mounted`
  (-> spirit_empress_air; the only one seen in recordings, name_stats.json), `DarkElixir_Bottle` (not in use),
  `CHAR_DISABLED_1/3/4/5/6/7` (placeholders, not in use). Crown towers are name `'-1'`.
- Sub-spawn max_hp survey over ALL 211 batch_v2 recordings (level 11 only; frames + play_frames):
  Golem {5120: 1323, 1039: 528}; LavaHound {3581: 740, 215: 710}; ElixirGolem {1569: 741, 762: 525, 360: 659};
  RoyalRecruits {547: 4282} (every body is one recruit); WitchMother {529: 1937} (NO hog spawn ever seen);
  Goblinstein {2385, 721}; SkeletonArmy {81, 2}; Graveyard {81}; HogRider {1697, 1863}.
- Entity `kind` in play_frames: towers 12 (king) / 13 (princess); troops 14 at spawn then 15; buildings 12/13.
  Coordinate range seen: x 0..17999, y 0..31500.
- Engine `effects` entries mirror `projectiles` by name ('-1' tower shots 2275, 'Xbow' 801, 'Log' 474, 'IceWizard'
  278, ... 'Rocket' 123, 'Arrows' 120, 'Fireball' 26): most are UNIT ATTACK effects, not spells.
- Record top-level `final_decks[side]` = 8 engine names in deck order with an `@evolution` suffix; play_frame
  `players[i].next` is a DECK INDEX into that list (verified: frame 5 next=0 -> cycle_pos[0]=0).
- Detector label counts (15,167 label files): royal_recruits 330 AND royal_recruit 257 both exist as board boxes;
  mother_witch_hog 171; golemite 53; lava_pups 31; elixir_golemite 47; elixir_blob 32.
- Python: `icebow/.venv/Scripts/python.exe` (HANDOFF.md:85-90); pytest is NOT installed there -> unittest runner.
- hogeq deck: `hogeq/config/cards.yaml:36-47` -> hog_rider, firecracker (evo), mighty_miner, tesla (evo), the_log,
  earthquake, skeletons, ice_spirit. (`hogeq/DECK_SWITCH.md` is a stale copy of the icebow runbook -- it lists the
  icebow deck at line 7, so it was NOT used.) icebow deck: `icebow/config/cards.yaml:36-46` (tornado, tesla evo,
  ice_wizard, x_bow, rocket, knight evo, the_log, skeletons) = the 8 named in the task.

## Facts measured after the first draft (led to two rule changes)

- Entity `kind` vs damage, 40 recordings: buildings kind 12 = 271 full-hp rows + 75 DAMAGED rows (22%); kind 13
  = 2447 damaged + 14 full; troops kind 14 = 982 full + 109 damaged, kind 15 = 12,541. So for troops kind 14 is
  a spawn state (the damaged 10% are spawns hit by a spell); for buildings kind 12 is NOT only "deploying"
  (an X-Bow at 203/1600 hp read kind 12 at tick 2896, 190 ticks after placement) -- it looks like an idle /
  no-target state. 16 troop rows of kind 12 exist too (Bats, GoblinGang, MinionHorde ...).
- Spawn-spell bodies are named by the SPELL: `BarbLog` 716 (760 rows), `GoblinBarrel` 202 (308) and 81 (41),
  `Graveyard` 81 (471), `RoyalDelivery` 547 (13), `Clone` 1 (17). Without a rule these troop bodies landed on
  spell-class ids inside `units`.
- Effect coordinates leave the board: 4 spell effects of 80,668 frames (Arrows y=-141/-143, Log y=33420,
  BarbLog y=-1060; MegaKnight jump effects at y=-5500 are dropped as unit attacks anyway). Entities never do
  (x 0..17999, y 0..31500).

## Decisions (spec left a choice)

1. **y-convention.** `nx = x/18000`, `ny = 1 - y/32000`; side 1 mirrored `(18000-x, 32000-y)` first
   (= build_bc_v2.py:100-158). Me at the BOTTOM = ny near 1. **My king row is ny = 0.90625** (engine side-0
   king at (9000, 3000) -> (0.5, 0.90625)); my princess row 0.796875 at x 0.19444 (L) / 0.80556 (R); river 0.5;
   enemy princess 0.203125; enemy king 0.09375. Asserted in `TestGeometry` numerically, and the same tower
   is checked to land on the config's `env.my_towers` frame anchor through BoardWarp's forward map
   (king -> frame (0.4962, 0.72), bottom-centre; river -> `board_edges.river`).
2. **Token truncation rule (one rule for both sources).** Units and spells are ranked jointly by
   `|y - 0.5|` ascending (nearest the river / bridges first), ties by conf descending; the first `max_units`
   are kept, emitted in rank order. Reason: live conf is uninformative about importance (everything kept
   already passed the deploy gate) and the river-distance rule is deterministic across engine/live/degraded,
   so the three sources truncate the same board the same way. Asserted on a 70-unit board.
3. **Sub-spawn thresholds.** (a) measured, level 11, all 211 batch_v2 recordings: golem <2500 -> golemite
   (5120/1039); lava_hound <1000 -> lava_pups (3581/215); elixir_golem >=1100 parent / >=500 golemite / else
   blob (1569/762/360); royal_recruits -> royal_recruit for every body (all 547; the card is never one entity).
   (b) UNTESTED: mother_witch <400 -> mother_witch_hog -- no cursed-hog body exists in any recording (parent
   measured 529); the threshold is a guess, flagged TODO in vocab.py. Added beyond the spec's six, all
   measured: spawn-spell bodies barbarian_barrel->barbarians, graveyard->skeletons, goblin_barrel->goblins
   (the 81-hp GoblinBarrel body is (b) untested -- also mapped to goblins), royal_delivery->royal_recruit.
   `Clone` bodies (hp 1) keep the `clone` id: the engine does not say which troop was cloned (143 unit rows
   in 80,668 frames).
4. **royal_recruit vs royal_recruits.** The detector has both (330 / 257 label boxes). Every engine body is
   one recruit (547 hp), so bodies map to `royal_recruit`; the deck / hand card stays `royal_recruits`. Which
   of the two the detector fires on a live recruit line is (b) untested.
5. **Unmapped engine names.** After `_ALIAS_INV` (copied from build_bc_v2.py:44-69, plus
   `DarkElixir_Bottle -> dark_elixir_bottle`) and CamelCase->snake, every one of the 122 in-use catalog cards
   maps to a detector class. Engine-only names appended after id 229: `spirit_empress_air` (230,
   `MergeMaiden_Mounted`, the only one seen in recordings) and `dark_elixir_bottle` (231, not in use).
   `CHAR_DISABLED_1/3/4/5/6/7` and the crown-tower name `'-1'` return None on purpose (not vocab entries).
   Sweep: 211 recordings, 80,668 frames -> unmapped set empty, 0 coordinates outside [0, 1].
   `from_engine(..., unmapped=set)` collects instead of raising `UnmappedName`.
6. **hogeq deck** read from `hogeq/config/cards.yaml:36-47` (hog_rider, firecracker evo, mighty_miner, tesla
   evo, the_log, earthquake, skeletons, ice_spirit). `hogeq/DECK_SWITCH.md` is a stale icebow copy (line 7
   lists the icebow deck) and was NOT used; the yaml says so. Both deck yamls point `src_dir` at
   `icebow/src` (the BoardWarp import) and carry their own `config` / `crawl_dir` / `data_dir`.
7. **Deploying flag.** Kept the builder's rule `kind in (12, 14)` for parity with build_bc_v2.py:151 but it
   is (b) inferred, and for buildings it is wrong in part: 22% of building kind-12 rows are damaged
   (the 203-hp X-Bow above). Troop kind 14 does look like a spawn state. A model reading `deploying` on a
   building should treat it as "idle or deploying". Not changed: the spec names the rule and the fix is a
   builder-wide decision.
8. **Effects -> spells.** An engine `effects` entry becomes a spell token only when its name's class is a
   detector spell class; the `_aoe` class is preferred when one exists (rocket -> rocket_aoe, log -> the_log_aoe)
   because that is what a ground effect looks like on screen. Unit-attack effects (Xbow, IceWizard, MegaKnight
   jump) and tower shots ('-1') are dropped -- measured: most `effects` rows are those. Spell coordinates
   are clipped to [0, 1] (4 of 80,668 frames were past the back wall); unit coordinates are never clipped.
9. **BoardState carries `deck: tuple[int, ...]`** (8 vocab ids) beyond the spec so `to_tokens` can one-hot the
   hand/next by deck slot without a second argument. Hand/next match the deck by BASE key (engine `Knight`
   matches deck `knight_evo`) and take the deck's canonical (evo) class id. `my_next` needs `engine_deck`
   (record `final_decks[side]`) because play_frame `next` is a deck index; without it -1.
10. **Live reads.** `LiveReads(elixir_int, hand_names, next_name, tower_hp[6], t_sec, t_source,
    tower_alive=(True,)*6)`. `opp_elixir` None; king hp None unless given; `Detection.gy` is the y used
    (flyers' shadow-corrected point). `team == "unknown"` -> side -1, kept.
11. **degrade unmeasured constants** (all say so in code): `_FP_JITTER_TILES = 1.0` (how far a duplicate
    sits), `_CONF_RANGE = (0.35, 1.0)` (live conf draw; 0.35 = the deploy gate). Recall 0.855 / precision 0.886
    are the measured HANDOFF numbers; spells are subject to recall too; `pos_sigma_tiles` 0 / `unknown_team_rate`
    None by default. Measured over 2,000 draws on a 10-unit board (seed 123): recall and FP-per-kept both within
    +-0.02 of target (the test asserts it).
12. **Feature layout.** F = 14 (`UNIT_FEATURES`: cls, side one-hot x3, x, y, hp_frac, hp_known, deploying,
    deploying_known, age/30, age_known, conf, is_spell); S = 70 (`SCALAR_FEATURES`: t/300, double, overtime,
    my_elixir/10, exact, opp_elixir/10, opp_known, hand 4x9, next 9, tower hp x6, hp_known x6, alive x6).
13. **Test runner.** pytest is not installed in the icebow venv (`python -m pytest` -> "No module named pytest";
    nothing was installed per the task). The file is unittest-style with a `__main__` runner and is also
    pytest-collectable.

## Test output

Command (from `C:\Users\benpe\ClashBot`):
`icebow/.venv/Scripts/python.exe -m unittest pipeline.tests.test_obs_contract -v`

```
Ran 19 tests in 0.742s

OK
```
(19 tests, 0 skipped: 4 vocab, 1 decks, 2 geometry, 6 engine adapter incl. mirror + real frames, 2 live
adapter incl. the synthetic pair, 2 degrade, 2 tokens.) `python -m pytest` reports "No module named pytest".
The one failure during development was a float32-vs-float64 comparison inside the truncation test itself
(tokens are float32), fixed with an `assert_allclose(atol=1e-6)`.

## Spec items not satisfied / caveats

- Test 6 asks for "truncate by conf (live) / nearest-bridge (engine)"; one rule was picked (nearest river) as
  the spec allows -- the conf rule is not implemented.
- `deploying` on buildings is only partly right (decision 7); left as specified.
- mother_witch_hog threshold and the 81-hp GoblinBarrel body are guesses (decision 3).
- No detector king/princess tower classes exist in the vocab (checked the 230 names) -- towers are contract
  slots only, as the spec intended.
- Nothing outside `pipeline/` was modified; the detector, emulator, engine services and game were not run.

STATUS: complete
