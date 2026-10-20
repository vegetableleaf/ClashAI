# W9 -- exact identities for every card / evolution / hero form (2026-10-20)

Owner 10-20: "the substitution of minion giant as a balloon is not that sound and i'd rather have exact identities and
stats rather than a substitution". Labels: (a) measured, (b) plausible but untested, (c) contradicted.

## 1. Is the 10-12 device pull stale vs the live build 160402012?

- (a) **Not stale by identity.** `raw_id_census.py` read every live log (4,534 `live_play_*.jsonl`, 2026-09-25 .. 10-20
  10:21): the reader reported **167 distinct card ids, all 167 present in the 10-12 tables** (`raw_id_census.json`).
  Minion Giant 26000107: 210 bodies in 50 logs since 10-07 (W1's COVERAGE.md shows 0 because its census was keyed by
  catalog name and ran before the 07:41 catalog patch).
- (b) Ids cannot prove that no balance change landed after 10-12. W1's live-vs-SIM HP check (791 (card, level, max_hp)
  triples, 23.0 M body-frames, `parity/output/metrics/static.json`) finds no card whose live HP contradicts the table
  except the known families in section 7.
- A fresh pull (not done: the emulator is in use) = `bash scratchpad/gauntlet/L74/apktables/pull_device_update.sh`
  (adb access to `/data/data/com.supercell.clashroyale/update`), then `check_build.py share/clashroyale_160402012_kit/apk
  --device-update <new>/update --old-table research/ext/Royale/RoyaleSim/data/derived/cards-15.535.json --out
  scratchpad/gauntlet/L74/apktables/out/device_builds --label device-<date>`, then re-run `gen_catalog.py check` and
  `inventory.py` against the new build directory (`--device`).

## 2. Inventory (full table: `INVENTORY.md`, data: `inventory.json`, script: `inventory.py`)

206 records in the 10-12 device tables = 145 cards + 43 evolutions + 18 hero forms. 184 are ladder records
(123 standard cards + all 43 evolutions + all 18 hero forms); 22 are event / summon variants (Super*, *_Chess,
TriWizards, PrinceBuff, GoblinParty*, GoblinRocketSilo, BarbarianLauncher, WarmSpell, Global*, MergeMaiden_Normal /
_Mounted = the Spirit Empress's two bodies). Champions are cards (8, all with their own class).

| column (184 ladder records) | before W9 | after W9 |
|---|---|---|
| live catalog names the id with its exact form | 181 (no AngryBarbarians_EV1 13000043, ElectroGiant_EV1 13000075, ElectroWizard_hero 203000042; IceWizard_hero 203000023 only through reader_identity_aliases) | **184** |
| unit vocab gives it its own class (a form = base class + form flag) | 181 (Balloon, MinionGiant, Balloon_hero shared `balloon`) | **184** |
| reader id -> class + form exact | 178 | **184** |
| live checkpoint's GenModel card_vocab has the card (123 cards) | 122 (no `minion-giant`) | 122 + stand-in (section 5) |
| SIM 0.1.36 plays it in that form | 182 (Hero Electro Wizard refused; Mirror needs a prior play = not a gap) | 182 (SIM untouched) |
| SIM table = device table (W1 static_check) | 182 (ElectroGiant_EV1, ElectroWizard_hero differ) | 182 |
| SIM body HP at L11 = device record HP x L11 multiplier (records whose play makes a body) | 166 / 167 (PrinceBuff, event) | same |

Event / summon variants keep their aliases (SuperKnight -> knight, ...): (a) 0 reader bodies in 4,534 logs for every
one of them except MergeMaiden_Normal / _Mounted (51 / 85 bodies), which ARE the ladder card's bodies (spirit_empress /
spirit_empress_air). Deliberately not given tokens.

## 3. Catalog (`gen_catalog.py`; file: research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json)

LOCAL change in the gitignored research/ext repo (IMAX9D/cr-native-sandbox, not committed there). Backups next to it:
`live_card_catalog.pre_w9_20261020.json` (= the file this morning, with the stop-gap MinionGiant row) and
`live_card_catalog.pre_miniongiant_20261020.json` (= the untouched libg 15.535.29 catalog = its git HEAD). Schema kept
(kind, every row key); one top-level `w9_extension` provenance key added; `counts` recomputed (153 rows, 123 standard,
43 evolutions, 18 hero forms).

- Ids: global id = table class x 1e6 + named-row index (spells_characters 26, buildings 27, other 28, evolved 13,
  hero_form 203). (a) The rule reproduces all 145 base ids, all 41 libg evolution ids and all 16 libg hero ids exactly,
  and every one of the 167 live reader ids.
- Filled (fields that were null): IceWizard hero form 203000023 + ability (2 elixir, 1 charge, 0 / 0 ms);
  ElectroWizard hero form 203000042 + ability (2, 1, cast 450, trigger 250); AngryBarbarians evolution 13000043 (device
  evo_cycles 1); ElectroGiant evolution 13000075; summon_character of IceWizard / ElectroWizard / ThreeMusketeers / TriWizards;
  Goblinstein's active ability.
- Corrected: FirespiritHut type building -> troop (device SummonCharacter `Furnace_rework`; W1: its bodies crossed the
  river 245 times live). Stop-gap MinionGiant row replaced by the derived row (unlock_arena Arena9 -> Arena5).
- Kept, but the device disagrees (libg 15.535.29 values; no pipeline consumer reads them -- listed for the lead):
  29 of 41 `evolution_cycles` (libg -> device: 3 -> 2 x10, 1 -> 2 x9, 2 -> 1 x8, 3 -> 1 x2; e.g. Knight 3 vs 2,
  Princess 1 vs 2: a different count, not a constant offset; dataset_gen reads RoyaleSim's evo_cycles, not these); Goblins hero_character (GoblinHero_Flag_Building vs
  GoblinHero); Tombstone hero_character; Monk ability cast / trigger 933 / 933 vs 700 / 700; GiantBuffer ability
  (absent from the apktables record); Rage / Heal summon_character.

## 4. Vocab (pipeline/vocab.py)

| new id | class | init source (embedding row copied on load) | evidence |
|---|---|---|---|
| 232 | `minion_giant` | `balloon` (12) | MinionGiant 26000107: 4-elixir Rare troop, flying (height 3000), buildings only, speed 60, base HP 710 (1817 at L11); Balloon: flying, buildings only, speed 60 -- the alias it replaces. Differs: range 4 tiles vs melee, damage 66 per 1.7 s base. |

- `APPENDED_CLASSES` (append-only; ids 0..231 pinned by sha256 in the test). N_VOCAB 232 -> 233, `N_BASE` = 232.
- Removed the `MinionGiant -> balloon` alias. `body_identity.EXT_CLASS` is now `{}`.
- Live HP (a): all 8 Minion Giant max_hp values the reader saw (1036, 1370, 1505, 1654, 1817, 2193, 2641, 2903) are
  exactly 710 x the level ladder at levels 5, 8, 9, 10, 11, 13, 15, 16. SIM 0.1.36 makes a 1817-HP body at L11.
- `icebow/config/cards.yaml`: a `minion_giant` row (4 elixir, air, buildings only), so the live opponent-elixir
  counter charges 4 (was 5 as balloon; with no row it would charge nothing).

## 5. Model loading (pipeline/model_v3.py, rl_royale.py, dataset_gen.py, e1_eval.py, live_gen.py)

- `S1Model._load_from_state_dict` (every loader and wrapper routes through it; GenModel inherits it): a cls_emb of an
  older vocab grows by `vocab.grown_rows` -- old rows byte-identical, row 232 = old balloon row, pad row (old 232) moves
  to 233. Any other row count -> ValueError; a wrong width -> torch's own size error.
- `model_v3.grow_optimizer_state` + 2 lines in `rl_royale._restore`: a run saved before the append resumes (its Adam
  exp_avg / exp_avg_sq rows grow the same way; no-op when shapes match).
- Card-identity table (GenModel `card_vocab`, per checkpoint, 123 keys: no `minion-giant`): `dataset_gen.CARD_STANDINS
  = {"minion-giant": "balloon"}` + `checkpoint_gid()` used by `e1_eval.GenPolicy` and `live_gen.GenPilot`. Without it,
  removing the alias makes the live pilot raise KeyError on a deck holding Minion Giant (the 07:47-08:35 parity battles
  played one -- (a) logs live_play_20261020_075330 .. 083004) and drops opponent Minion Giant plays from opp_past /
  opp_cycle. This IS a card-level stand-in for checkpoints that predate the card; a dataset built from data that holds
  the card gives it its own card_vocab row. See concern C1.
- Outputs identical (a): `test_live_checkpoint_outputs_identical_on_real_rows` loads the live checkpoint
  (rlarm_stepd_ctrl_nos2_u0130_grafted.pt, 233-row cls_emb) both ways and runs 48 real IL rows of its dataset
  (gen_dataset_v32_fv5: rows 0-15 + the first 32 of the 64 rows in rows 0-2999 that hold balloon tokens): every output tensor equal (torch.equal); the same rows with their
  balloon tokens set to minion_giant give equal outputs too.
- Paths checked: rl_royale (init via model_gen.load_model / engine_play.load_model, actors get the learner's state dict,
  resume via _restore), e1_eval.load_policy, live_gen.GenPilot (model_gen.load_model) -- all build with vocab.N_VOCAB.

## 6. Tests and smoke

- `pipeline/tests/test_vocab_extension.py`: 11 passed (append-only ids, Minion Giant class, grown_rows map + refusals,
  S1 grow + identical outputs, shape refusals, optimizer growth (toy + the live run's u0130 optimizer, then an Adam
  step), real-checkpoint identical outputs on real rows, card stand-in, catalog round trip (every id unique, catalog
  name/form round trip, the 5 new ids, every ladder card its own class), live deck_of with Minion Giant).
- Updated to the new truth: test_obs_contract (122 -> 123 in-use cards; it already failed after the 07:41 catalog
  patch), test_identity_ext (26000107 -> minion_giant; 13000043 is now named by the catalog, form 1), test_cue_inputs
  (cls_emb compared through grown_rows).
- Targeted run (36 files: vocab / obs / identity / live / model / dataset / e1_eval / rl tests): 529 passed, 16 failed,
  10 skipped (`tests_targeted.out`, before the 3 test updates above). After the updates (`tests_after.out`):
  test_obs_contract + identity_ext + identity_fv5 + body_identity + vocab_extension + cue_inputs = 88 passed,
  8 skipped, exit 0. Remaining 15 of the targeted run are not this change: 14 test_live_options (laptop venv has no cv2 + another
  worker's uncommitted live_options.py edit: `{'Log': 16} != {'Log': 15}`), 1 test_predict_drops (GenPilot built
  without `.model`; failing since the 10-17 cue line 7265e4c).
- pyflakes: no undefined names in any changed file.
- **rl_royale --smoke: UNVERIFIED** -- live parity battles were running on the laptop (logs written 10:59). Pod command
  (any free pod with /workspace/cb_stepd at this commit):

```bash
cd /workspace/cb_stepd && PYTHONPATH=$PWD ROYALE_RUNTIME=fin13-linux ROYALE_HEROIW_FORM=hero OMP_NUM_THREADS=1 \
  MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 flock /workspace/cpu.lock /workspace/venvf13/bin/python \
  -m pipeline.rl_royale --config scratchpad/gauntlet/L74/stepd/cfg/stepd_l16_proopp_s74.yaml --run smoke_w9 --smoke \
  critic_warmup_updates=1 > /workspace/stepd/smoke_w9.log 2>&1; grep 'SMOKE PASS' /workspace/stepd/smoke_w9.log
/workspace/venvf13/bin/python -m pytest -q pipeline/tests/test_vocab_extension.py   # the real-row tests skip on a pod
```

## 7. SIM gap list for W8 (ranked by live frequency; SIM = royalesim 0.1.36 laptop wheel, the fork36 base)

| # | card / form | live (reader bodies / logs, or body-frames) | gap | evidence |
|---|---|---|---|---|
| 1 | Hero Electro Wizard (203000042) | 217 bodies / 62 logs | cannot load the form; table crown_tower_damage_percent 100 vs device 0 | probe: `ElectroWizard has no loadable hero form: ability ElectroWizardHero_Ability: effect surge is not simulated`; W1 static_check |
| 2 | Skeleton King summoned skeletons | 18,471 body-frames (L15 / L16) | live max_hp 1 vs SIM table 32 -> 119 / 130 | W1 live_vs_sim; body_identity MEASURED_HP; cause (reader vs SIM) not settled |
| 3 | Clone (cloned bodies) | 10,206 body-frames (L12-16); 101 plays | SIM has no 1-HP clone body; W1 J5a deploy agreement 0.00 (n 60) | W1 live_vs_sim + COVERAGE.md |
| 4 | level-17 bodies: Mirror (355 / 1260 HP), Hero Tombstone 7425, Hero Balloon 832 | 1,128 + 168 + 136 body-frames | SIM has no level 17 (a Mirror of a level-16 card, body_identity MIRROR_LEVEL 450 %); (b) the two hero readings may be ability bodies instead -- not separated | W1 live_vs_sim |
| 5 | Evo Electro Giant (13000075) | 43 bodies / 24 logs | table evo_delevel_pulse.hit_speed_ms 50 vs device missing | W1 static_check |
| 6 | SuperHogRider, GlobalLightning (event) | 0 | absent from the SIM catalogue | probe vs device card list |
| 7 | PrinceBuff (event) | 0 | first body 2304 HP at L11 vs device record 3686 | probe |

Not a SIM gap: **D1's 1,007 `unsupported_forms BarbarianLauncher`**. (a) The SIM loads Hero Barb Log (probe: OK, a
716-HP barbarian by tick 60). The cause is `scratchpad/gauntlet/L74/pro2/build_rows.card_catalog()`: it keeps the
FIRST catalog row per slug, and the event building BarbarianLauncher (27000011, aliased to barbarian_barrel) precedes
BarbLog (28000015), so `barbarian-barrel-hero` decks asked the SIM for a hero BarbarianLauncher. Same bug sends
`spirit-empress` to MergeMaiden_Normal (26000104, the ground body only) instead of MergeMaiden (28000024). (a) Fix,
verified on the catalog: iterate `sorted(cards, key=lambda c: not c['standard_1v1'])` -> exactly those 2 slugs change
(barbarian-barrel -> BarbLog, spirit-empress -> MergeMaiden). NOT applied: build_rows.py carries another worker's
uncommitted edits. Since this change, `minion-giant` crawl decks resolve to MinionGiant (before: no slug ->
`unsupported_source_card`).

## 8. Concerns

- C1 (card identity): checkpoints' card_vocab predates Minion Giant; the stand-in reads it through balloon's card row.
  Exact would need appending `minion-giant` to card_vocab (+ card_id / card_b / wait_b rows) and relaxing the trainer's
  `card_vocab ==` checks against datasets (rl_royale proagree / shaping_phi) to prefix-equality. Architecture: lead's call.
- C2 (live): live_play imports the main working tree at every battle start, so these changes are live from the next
  battle: Minion Giant token 232 (outputs identical at init), opp elixir charges 4 for it; Evo Elite Barbarians / Evo
  Electro Giant / Hero E-Wiz reader bodies now carry form 1 / 1 / 2 (identity-ext gave form 0) and their plays now
  reach the opponent-elixir counter and opp_past (before: unknown ids, never charged). (b) effect on play untested.
  Battles 10:43-10:59 after the edits ended normally (end events, 42-59 plays each).
- C3: a checkpoint SAVED by this code has 234 cls_emb rows and will not load in code before this commit (pods on old
  checkouts).
- C4: pods keep their own unextended catalog copy; pro2 drives there still lack the 4 form ids. Copy the laptop file if
  wanted (not done: pods belong to running jobs).
- C5 (remaining body substitutions, identity-ext ON live): DarkPrinceHero_Mount -> ram_rider, MusketeerTurret -> tesla,
  SkeletonTrooper -> bandit, TombstoneHero_Monster -> giant, ChampionGuard -> knight (EXT_BODIES). The same append
  mechanism gives each its own class with the current substitute as init source (outputs identical at init) -- not done
  (bodies, not cards; outside this ticket).

## Files

Scripts: `dump_tables.py` (table ids), `raw_id_census.py` (+ `raw_id_census.json`), `sim_probe.py` (+
`sim_probe_0136.json`), `gen_catalog.py` (+ `gen_catalog_write.out`), `inventory.py` (+ `inventory.json`,
`INVENTORY.md`). `dump_device_1012.txt` = the id dump of the 10-12 tables (local only, not committed: decoded game
tables stay out of git, as apktables/README says).
