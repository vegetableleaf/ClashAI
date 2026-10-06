# Spawner identity audit: live reader vs training data vs SIM vs public opponent model (L73, 2026-10-06)

All numbers below come from the scripts in this folder. Raw output is in `results.json`. Nothing in `pipeline/` was edited.
Live checkpoint: R1e `rseries_r1e31_u0155.pt`, feature version 4 (fv4). In fv4, a body's identity comes from
`vocab.engine_unit_id(name, max_hp)`, called at `obs_contract.py:327`. Codex's corrected body contract runs only when
`feature_version >= 5` (`obs_contract.py:322-325` → `body_identity.resolve`).

## Data used

| Stage | Source | Size |
|---|---|---|
| Live | `L68/live_reader/live_play_*.jsonl`: logs that contain `frame` events, plus `decision` public audits (the model batch actually used) | 164 logs, 316,298 frames; 29 R1e-fv4 logs with 9,718 audited decisions |
| Training | Native re-drive recordings (`ext/corpus_*/*_public_v1`), passed through `tag_native_recording` + `recording_observers` exactly as `dataset_gen` does. The true command log and true elixir are used only as the measuring stick | 1,474 replays sampled from 9,961 that contain a spawner card (seed 20261006, ≤80 per card/form) + 150 control replays |
| Training archive | `gen_dataset_v31_public.npz` vs Codex's `spawner_identity_20261005/gen_dataset_v5_public.npz`, compared row by row in a stream | 15,974,787 tokens |
| SIM | The pinned runtime `Royale-20261005` (RoyaleSim 015f9b0 / 0.1.13), activated in a fresh process | controlled deployments |

## Issue table

Abbreviations: "child→parent" = a spawned body (for example a Witch skeleton) is labelled as the card that made it. T = training (native recordings → dataset), L = live, S = SIM. "Mismatch" = training and live represent the unit differently.

| # | Stage | Mechanism (file:line) | How often (measured) | What the model is told | T vs L mismatch? | Codex fix? |
|---|---|---|---|---|---|---|
| 1 | T, L, S (all) | **child→parent labelling.** The engine, the reader and the pinned SIM give every child the producer's `card_id` and name. `engine_unit_id` splits by `max_hp` only for golem/lava/egolem/recruits/mother witch (`vocab.py:165-195`), so Witch, Night Witch, Furnace, Tombstone, Goblin Hut and Barbarian Hut children all become the parent. | **Training archive:** 78.5% of all `witch` tokens are skeletons (213,960/272,661); `night_witch` 70.4% bats (152,004/215,866); `tombstone` 69.2% (297,628/430,322); `goblin_hut` 61.0% (112,944/185,202); `furnace` 38.3% fire spirits (108,101/282,451); `barbarian_hut` 72.9% (1,281/1,758). This matches Codex's 885,918 total exactly. **Live R1e batch:** 540 decisions with Witch bodies show 1,807 `witch` tokens against 447 readable Witches (4.0×); 398/540 decisions are inflated and 98/540 show `witch` tokens with no readable Witch at all. Night Witch: 161 tokens vs 43 parents (39/43 decisions). Furnace: 460 vs 292 (142/293 decisions). | Sees ~4 full-HP Witches (hp_frac=1) instead of 1 Witch + 3 skeletons. Each skeleton or bat is tokenised as an 839/906-HP ranged unit. | No. T, L and the pinned S all agree. **Exception:** the OLD runtime that R1e's RL used named Furnace children `FireSpirits` (L71 `sim_identity_probe.json`), so R1e's RL saw `fire_spirit` while IL and live see `furnace` (see #8). | **Partly.** fv5 `body_identity.resolve` fixes these 6 families in the v5 archive, SIM and live. **It is not deployed:** live is R1e fv4. tower_spatial_v7 (fv7) ran it in 9 logs and was withdrawn. Codex's zero-adaptation test of R1e on corrected inputs got worse (Witch PLAY 17→15/113, Night Witch 11→8/80; Codex's numbers, not rerun). |
| 2 | T, L | **Evo Witch body becomes unreadable** (`hp = max_hp = -1`, kind 15) partway through her life. `from_engine` drops `hp<=0` bodies (`obs_contract.py:320`) and so does `public_frame` (`public_observation.py:69`). | Native: every unreadable Witch is form 1 (2,518 body-frames in the scanned replays; 5,077 in the full sample). Live: 1,214 frames, **all `card_id` 13000007 (Evo Witch)**. | The Witch disappears from the board while her skeletons stay, still labelled `witch`. | No (T and L agree). SIM Evo Witch stays readable (`sim_evo_probe.json`), so S disagrees. | **No.** `resolve` returns `unknown_hp` before the drop, and the body is dropped either way. |
| 3 | Public model T, L | **Phantom Witch plays.** This follows from #2. Once the parent is dropped, the parent rule in `PlayDetector.feed` (`opp_elixir_count.py:220`) never sees her, because `public_frame` already filtered her out. Its `max_hp<=0` branch is therefore dead code on the fv4 path. Each skeleton wave more than 60 ticks after she vanishes is charged as a new 5-elixir Witch play. | Native: **232 phantom Witch plays against 556 true Evo Witch plays (+42%)**, in 104 of 169 Evo Witch opponent sides. Base Witch: 0/78. All 232 coincide with an unreadable parent present (`mechanism_check.json`). Live replica of PublicObserver: **13 phantoms among 92 inferred Witch plays, in 8/30 Witch matches**, worst estimate shift −9.8. | "Opponent spent 5 more elixir" (11.3 phantom elixir per affected side). Elixir MAE 0.64 → 0.92, bias +0.38 → −0.17 (the model thinks the opponent is poorer). `opp_past` holds a phantom in 13.5% of frames and `opp_cycle` resets Witch to "just played". | No (T and L agree). Pinned S has no phantoms, so RL never practised this. | **No.** |
| 4 | T, L, S | **Mother Witch cursed hogs and some goblins carry `card_id -1`**, kind 15/14, and are dropped (`obs_contract.py:309`, `live_mem.py:50`, `public_observation.py:69`). The `mother_witch_hog` class is never produced. | Native: 2,499 hog body-frames (max_hp 629) in 30 Mother Witch replays; the archive has **0** `mother_witch_hog` tokens. Live: 1 hog-sized body (915 = 629×1.455, the same level ratio as Witch 1220/839) and 8 goblin-sized bodies, all unnamed. | Cursed hogs are invisible: troops walking at the tower that the model cannot see. | No (both drop them). S: no curse happened in the probe, so **untested**. | **No** (Mother Witch is not in FAMILIES). |
| 5 | L only | **Elixir Golem split thresholds are fixed at level-11 HP** (`vocab.py:173`). Live opponents are at levels 14–16. | Live: 40 golemite bodies (1108/1218 HP) → `elixir_golem`; 75 blob bodies (524/576) → `elixir_golemite`, in 11 logs. Training (level 11) and SIM label correctly. | Sees 3 Elixir Golems instead of 1 + 2 golemites, or golemites instead of blobs. | **YES, live only. The model never saw this.** | No |
| 6 | T, L, S | **Families Codex did not cover** keep child→parent: Skeleton Barrel skeletons, Goblin Giant spear goblins, Goblin Drill goblins and its second 2560-HP body, Goblin Cage brawler, Phoenix egg, Goblinstein/Suspicious Bush sub-bodies, Graveyard (correct: `_SPELL_BODY` → skeletons). | Native bodies: Skeleton Barrel 8,361 skeletons vs 1,096 barrels; Goblin Giant 1,445 goblins vs 322 giants; Goblin Drill 4,106 goblins vs 1,250 drills (+1,245 extra 2560-HP bodies); Goblin Cage 766 brawlers vs 782 cages; Phoenix 320 eggs vs 431 phoenixes. Live survey: Skeleton Barrel 192 child bodies, Goblin Giant 74, Goblin Drill 30, Skeleton King 111 `max_hp=1` bodies → `skeleton_king`. | Sees many barrels, giants or drills where there are 81–202-HP children. | No (all stages agree). | **No.** fv5 leaves them `legacy`. |
| 7 | L (fv5 path) | **The resolver cannot decide some live HP values across levels** (`body_identity.py:123` keeps the parent when an HP value matches more than one level). | Live: Furnace 343 HP (17+2 bodies) is `ambiguous_hp`; Evo Witch child 144 HP (12) is `unknown_hp`. In the fv7 live batch, 27/158 Furnace decisions still showed extra `furnace` tokens. | Some children stay labelled as parents even under fv5. | Not in training: the dataset is level 11 only. | Residual of Codex's fix |
| 8 | S (R1e's RL) | **The old runtime named Furnace children `FireSpirits`** (Codex's L71 probe). `public_frame(sim)` maps them to the FireSpirits card, and the parent rule cannot see a different key, so every wave is a phantom 1-elixir `fire_spirit` play. | Counterfactual on the pinned engine (`sim_furnace_naming.json`): one Furnace → 2 phantom `fire_spirit` plays; tokens become `fire_spirit` instead of `furnace`. Applies to R1e's RL (checkpoint 2026-10-04 20:14, before the 10-05 pin). | During RL, R1e saw correct fire spirits but a polluted opponent history. | **Three-way disagreement for R1e:** IL `furnace`, RL `fire_spirit`, live `furnace`. | n/a (the upstream engine changed). The pinned runtime now gives `FirespiritHut` 215, matching native. |
| 9 | Public model T, L | **Missed real plays from the spawn heuristics** (`opp_elixir_count.py:220-223`). The parent rule assumes children are weaker than the parent. The death-spawn rule fires when any weaker same-card body vanished within 1.5 tiles in the last 60 ticks. | Native: Goblin Cage 34/785 real cages missed (the 1080-HP brawler is "stronger parent"; 19 with the brawler on board, 15 just died); Tombstone 23/1,251; Witch 12/749 (8 absorbed by a just-charged phantom); Goblin Hut 6/794; Night Witch 3/543. Phoenix: 10 phantom of 352. | "Opponent did not play that card": estimate too high, and the card is missing from the cycle. | No | No |
| 10 | T/L vs S | **Child form**: in native and live, children carry the evo/hero card id, so in fv4 they get form 1/2. SIM children have `status_flags` 0, so form 0. **Hero Tombstone** differs by source: SIM gives 2 readable 529-HP hero bodies per play; native/live give 1 readable 529 + 1 unreadable (kind 13, dropped; live 1,571 frames) + a 4,224-HP kind-15 body with id 203000088, which fv4 labels `tombstone` f2. | Native child forms: Witch 3,176 f1, Furnace 1,630 f1, Tombstone 5,429 f2, Skeleton Barrel 2,774 f1. | Skeletons tokenised as Evo Witches or Hero Tombstones. | T and L agree; S disagrees. | Partly: fv5 sets child form 0 for the 6 families only. |

Not spawner problems, but seen while measuring (out of scope): SIM `public_frame` maps champions (status flag 16 → form 2) to no native id, so Skeleton King and Goblinstein plays never register in SIM (`sim_probe.json`, plays `[]`). Spirit Empress mounted is charged as `spirit_empress_air` and the real `spirit_empress` play is counted as missed (78 pairs in Furnace decks).

## What Codex's "corrected observation" changes, verified

Checked by a stream diff of the two archives (`dataset_diff.json`). It changes **only the board class of child tokens in 6 families**: tombstone→skeletons 297,628, witch→skeletons 213,960, night_witch→bats 152,004, goblin_hut→spear_goblins 112,944, furnace→fire_spirit 108,101, barbarian_hut→barbarians 1,281. No other array changes (Codex's own verifier).

It does **not** touch:
- `opp_past`, `opp_cycle` or the elixir scalar (issues 3 and 9);
- the dropped unreadable Evo Witch (#2);
- the dropped hogs (#4);
- live Elixir Golem levels (#5);
- the uncovered families (#6).

It also needs a retrained checkpoint. The v4/v5 IL and Rocket arms trained on it failed acceptance, and R1e does worse on it zero-shot. In short, it is a correct fix for half of issue #1, it was never deployed, and it misses the elixir and history pollution, which hits hardest exactly in Witch matches.

## Ranked fix list (do not implement without the owner)

1. **Keep unreadable bodies in the public observer** (fixes #3 and part of #9). In `public_frame` (`public_observation.py:69`), drop only `hp<=0` bodies whose `max_hp>0` (truly dead). Pass `max_hp<=0` bodies through so the existing `PlayDetector` branch (`opp_elixir_count.py:220`) holds them as parents.
   - Touches: the counter, `opp_past` and `opp_cycle` in T, L and S.
   - Verify without retraining: rerun `native_audit.py` (expect Witch phantoms 232→≈0, and Evo Witch MAE back to ≈0.64) and `live_audit.py` (13→0).
   - Caveat: R1e was trained on the polluted features. The scalar becomes more accurate but moves slightly away from what R1e learned. Measure the action change with R1e on fixed vs original features (same method as Codex's diagnosis) before going live.
2. **Live-only Elixir Golem threshold** (#5). Scale the `_sub_egolem` cut points by the level ratio implied by the same match's largest observed Elixir Golem body, or move Elixir Golem/Golem/Lava Hound into `body_identity`'s catalog tables.
   - Training stays identical (level 11), so **no retraining is needed**: this restores training/live parity.
   - Verify: `map_live.py` should show 1108/1218 → golemite and 524/576 → blob.
3. **Give unnamed `card_id -1` troops an identity** (#4). Resolve kind 14/15 non-tower bodies by catalog HP (cursed hog 629×level) to `mother_witch_hog`/`goblins`, otherwise to an "unknown troop" token.
   - Needs a dataset rebuild and retraining: the class has 0 training tokens.
   - Verify with `live_unnamed.py` and the native census.
4. **Fix the observer's spawn heuristics** (#9). Exempt death-spawns that are stronger than their parent (Goblin Cage→Brawler, Phoenix egg) from the parent rule. Require the death-spawn source to be the parent class (via `resolve`), not any weaker same-card body.
   - Verify with `native_audit.py`: missed cages 34→≈0, missed tombstones 23→lower.
5. **Deploy child identity only with a retrained checkpoint** (#1, #6, #7, #10). Extend `body_identity.FAMILIES` to skeleton_barrel, goblin_giant, goblin_drill, goblin_cage, phoenix and mother_witch. Disambiguate ambiguous HP using the level of the same-side parent seen in that match. Keep child form = 0 everywhere.
   - The upstream RoyaleSim 9c7ae7c / 0.1.17 `unit_type` column (not in the pinned 0.1.13) gives exact child types in SIM. Use it **as a test oracle** for `resolve()` on SIM. Do not use it as a model input: native and live have no such column.
   - Verify: SIM oracle agreement, the native census and the live `map_live.py` table. This one needs IL+RL retraining; Codex's v4/v5 arms show a recipe alone did not pass.
6. **Unreadable Evo Witch on the board** (#2). Keep her as a body with unknown hp, rather than dropping her in `from_engine`, in T, L and S together.
   - Needs retraining (Evo Witch is common: 937 of 1,015 recorded Witch decks are Evo).
   - First find out why her HP becomes −1 in both the native client and the reader. **Untested.**
7. **Hero Tombstone representation** (#10). Inspect the 4,224-HP body and the unreadable kind-13 body before deciding. **Untested.**

## Scripts, outputs and commands

Scripts, all CPU:

| Script | Command | What it does |
|---|---|---|
| `survey_live.py` | `python` | Live census |
| `map_live.py` | `python` | Live body → fv4/fv5 class |
| `live_audit.py` | `python` | Live model batch + observer replica |
| `summarize_live.py` | `python` | Live summary |
| `live_unnamed.py` | `python` | Unnamed live bodies |
| `prefilter.py` | `python` | Pick recordings that contain spawner cards |
| `native_audit.py 80` | `python` | Native census + observer vs truth; 3 workers |
| `summarize_native.py` | `python` | Native summary |
| `mechanism_check.py` | `python` | Why each phantom/missed play happened |
| `dataset_diff.py` | `python` | Archive stream diff |
| `sim_probe.py`, `sim_pinned_ids.py`, `sim_evo_probe.py`, `sim_furnace_naming.py` | `research/ext/Royale/.venv/Scripts/python.exe` (pinned runtime activated) | SIM checks |

Outputs: `results.json` (merged); per-script `*.json`; `native_audit_raw.json`; `live_audit_raw.json`.

## Limits

- The live observer replica has no projectiles or effects (they are not logged), so body-less spells are missing. The phantom effect is therefore reported as a with/without difference, not as absolute error.
- Native truth matching uses a window of +150/−5 ticks.
- The native sample is stratified, so it is not a population rate.
- I did not measure win-rate effect.
