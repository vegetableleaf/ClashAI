# Opponent models in the ClashBot simulator: current state (as of 10-26)

Read-only research. I read the HANDOFF from HEAD with `git show`, not the stale working copy. Docs live under `C:\Users\benpe\ClashBot\scratchpad\gauntlet\L74\` unless a path says otherwise.

## Bottom line

- **No opponent has passed the human-likeness gate.**
  - The best Ranked-calibrated opponent is W14 I u40 (`4ff9fe93`). It passes 6 of 12 cells on all 233 Ranked matches, and 5 of 12 on the owner's newer target (the most recent 100 Ranked matches).
  - It reached 10 of 12 only with a CLX tap handicap that was later shown to be overstated. The corrected re-run (`w18_Iu40_tl2`) was never reported.
  - The most human-like nets are too weak. Live-imitation scores style 0.58 but CLX beats it 87.9% of the time. The best strength match (I u40) scores style 0.78.
  - **Style vs strength:** across W7, W14 and W18, the knobs and training rounds either made the opponent stronger or more human-like, not both.
- **One network plays every deck.** No opponent is a per-deck or per-archetype model; each one only gets its deck's cards as input. The only archetype-specific opponents ever trained were the Stage-2 Hog pair (242 Hog decks), and both failed. The owner's 10-17 request for imitation opponents per deck style (Hog cycle, bridge spam, beatdown, Mega Knight) was never built.
- **Every RL-trained opponent was trained only against icebow.** The configs set `league_icebow_share: 1.0` and `league_learner_icebow_share: 0.0`.
- **The promotion-gate opponent E4 is a former live icebow model.** It is a defence-RL checkpoint replayed with other decks, and it is about 20-25% too soft.
- **The SIM still over-predicts live results** (`memory/measure1026/q1_ot.out`). CLXIII's SIM win rates against the current gate opponents (E4 72.6%, calibrated I u40 "cal" 58.8%) sit 11-25 pp above its live 47.8%.

## 1. Every opponent model built

| Model (sha) | Training data and method | Setting | Key measurements | Source |
|---|---|---|---|---|
| gen_v1_s0 | Pro imitation | T .3 | SIM opponent before 10-11. Old live model won ~70% vs it in the SIM, ~50% live. Style 0.75; 0.54 at d20 r20, but then F1 wins 78.1% | HANDOFF 10-11, 10-15 |
| **E4** = `rdef_e4_u0020` (raw 7fb66681; graft 430faaee `..._barrel2k_cellref_towerref_w2.pt`) | The icebow defence-RL arm E4 (branch outcome labels, 20 updates). It was the live icebow model on 10-10. Used as the "CAL set c" generalist opponent from 10-11 (`livecal.py:21`) | T .1, decide 10 | Style 0.93 (13k ladder), 0.97 (F1), 1.01 vs Ranked. Answers within 3 s: 0.48 vs live 0.26. Plays/min in 2x: 12.2 vs 8.5. Pocket share after our princess falls 15.8% vs live 41%. Punishes a wasted Log 14.6% vs 19.2%. HP lost per push elixir 60.4 vs 79.7 (0.76x). Push cells failed: 8 of 42. CLX SIM win 72.3% vs Ranked 48.1%. Lock rate 0.585, shut-outs 3%. Live as icebow: 20-32 | OPP_MODEL §3, §8; PUSH_CAL §2; LEDGER S4 |
| **gen_v32_s0** (61011b6c), pro imitation | 14,661 replays, 3,517,863 rows (1,012,450 plays), 4,283 decks, both sides, level 11 | T .1, decide 40 | CLX win 74.8% (480 games) / 73.2% (1,920). Opponent takes a princess 23.3 / 22.8%. Style 0.79 / 0.77. O4: 3 of 6 cells fail | OPP_MODEL §6.2b, §7.1 |
| **O2** (f03f36d3), live imitation | gen_v32_s0 fine-tuned on 43,714 opponent-seat rows (11,934 plays) from 1,075 live matches at ≥12k trophies; time-ordered holdout of 15,885 rows | T .1, decide 40 | Cell NLL 6.44→3.19, placement error 5.2→3.3 tiles, card 0.509→0.532. **Timing (gate) head unchanged at 0.685.** Style **0.58**, but CLX wins **87.9%**; opponent takes a princess 16.0% | §6.2–6.2b |
| **O2b** (0882374c) | O2 after relabelling 2,586 spell plays at their projectile target | T .1, decide 40 | Style 0.65; CLX 83.8%; opponent takes 19.8%. The relabel bought 4-6 pp of strength | §6.2b |
| Stage-2 `s2_all_il_sA/B` | gen_v32_s0 + 130 PPO updates vs a frozen CXXXVIII; win-only reward; level-11 towers; `decks_live_train` | – | Never gated. A stalling exploiter: overtime 66-75%, both sides take a princess 1.7-3.6% (live 13.6-17.1%), style 0.96. Learner win vs it 56→62%. Training against it cost the learner −4.4/−6.2 pp vs E4 | §4 |
| Stage-2 `s2_hog_il` / `s2_hog_e4` (Hog-only) | 65 updates vs CXXXVIII on `stage2/pools/decks_hog_train.json` (242 decks, 621 sides) | – | Failed the Hog gate. il u65 wins 51.2% vs live 28.6% | `stage2/LEDGER.md` |
| Exploiters 862bfe92, gae_exploit (pod 23419) | RL vs a frozen learner | – | 862bfe92: CXXXVIII wins 51.7%, overtime 70.3%. Exploiter vs u250: +9.38 pp | §2.3; HANDOFF 10-17 |
| **W7** C1 → R4 → **R6 u20** (34522564, `w7opp.pt`); R4 u100 (ea1d0804) | O2b + RL as the opponent-to-be on census decks vs a frozen icebow mix (CLX / CLIII / CLIX / CXXXVIII); win-only; KL 0.1. R4 added `league_opp_live`. R6 added a gate KL anchor to O2b | T .1, decide 40 | O4 vs the 13.5-14k ladder (n 138): CLX 63.2% vs 62.3; opponent takes 36.2; overtime 54.9; both took 11.9; style 0.71. **All 6 overall cells pass**; the Hog CLX-takes cell fails (z 2.26). **Vs Ranked: 3 of 12** (CLX 64.0 vs 48.1; vs tank/bridge-spam decks, "BEAT", 56.9 vs 25.3; win in overtime 70.1 vs 47.3). 1-1 X-Bow lock 48.2 vs 12.2 | §7, §8 R0 |
| **W14** A/A2/A3/B/C/D/E/E2/F/I/I2/J/K | Same recipe on fin15, starting from R6 u20. Levers: lr ×3/×10, gate-free (B), tank decks ×3 (E), overtime starts (I), CLX-only mix (J), gate anchor (K) | T .1, decide 40 | B u20 (40275759): CLX 57.0, style 0.53, 5/12. A3 u35 (45a1c8b0): 53.0, style 0.75. E u40 (e5198fb7): 50.7, style 0.68, 4/12. **I u40 (4ff9fe93, = `w14opp_I`): CLX 48.8 vs 48.1; BEAT 41.0 vs 25.3; win in overtime 57.6 vs 47.3; both took 13.3 vs 5.6; regulation loss 26.5 vs 18.9; style 0.78; 6/12** | §8.1–8.2 |
| I u40 under gate v2 (recent 100 Ranked) | – | – | 5/12 without the handicap; 10/12 with the overstated handicap (fails both took 13.3 and style 0.72) | §8.3–8.4; DIAG_12 §10, §8.14 |
| I u40 **"cal"** (eval-time decode) | No training | decide 20 + tau .2 | **1 of 42 push cells fail** (default decode: 12). CLX wins 59.6% vs it. Elixir per push 9.10 vs live 7.61 | HANDOFF 10-23 08:11 |
| **W18** R1 `princess_redirect`, R2 `lead_protect`, R3 `play_cost` (u40) | I u40 + one reward term each | – | Push cells failed 8 / 12 / 9. Elixir per push 9.38 / 9.63 / 9.58 vs live 7.61, so **push size is not fixed**. R3 cal lock 0.563, shut-outs 7%. **Their gate-v2 scores were never recorded** | `push_cal/report_w18.out`; LEDGER |
| W18 R4 / R4b, P-D probe | R4 = R1 + `xbow_start_share` 0.25 (841 live Ranked X-Bow states). P-D = a scripted probe | – | Built, smoke PASS. P-D: a tower-front building cuts the 12-s lock 17.9→10.6% and lane damage −47% | DIAG_12 §8.11–8.14 |
| **D1** `oppD1_deny_s74` (+ s75 replication) | The R4 recipe + CLXIII in the external pool, no hazard play, 60 updates (`cfg/oppD1_deny_s74.yaml`) | Calibrated decode | u60: CLXIII wins 49.5%, lock 0.544, shut-outs 8%. u40: 46.6% / 0.562 / 6%. Live: CLX 0.565 / 9%, CLXIII 0.462 / 16%. "Hardest SIM opponent and closest to live denial" | LEDGER 10-25 |

**Training pools since 10-25:**
- Memory arms: D1 u60 0.15 + I u40 0.15 + W18 R3 0.10, calibrated decode, counter-deck file cx3 (LEDGER lines 130-131).
- Promotion gate: E4 + cal, 3,840 games.

## 2. SIM-vs-live gaps: explained and unexplained

**Explained:**
- **Tower level (O0):** half of the SIM-vs-live gap is level. Tower 15→16 moves SIM win +7.8 vs live +15.8, and princesses lost −7.7 vs −19.7.
- **The "1.75x bigger SIM pushes" gap was a scorer bug.** `sim_value` priced each spawned unit at its whole card; one rule on both sides closes ~90% of it.
- **About half of the overtime gap was CLX's own tap handicap** (P-A2: win in overtime −5.2, before the drain −8.5). This is an upper bound: the corrected lost-tap rate is only 1.5-2% per tap (W21).
- **The 3-crown overtime state explains 40-55% of the 0-0 overtime gap.**
- **Overtime lane focus:** SIM 46.6% of troop elixir on CLX's weakest princess vs live 66.9%.
- **X-Bow denial:**
  - Blockers inside the X-Bow's 3.5 s deploy window vs tank decks: 43% SIM vs 66% live. That timing is half of the tank-deck lock gap.
  - The SIM opponent never places a deep building: 0 of 102.
  - Bridge X-Bow lock rate: 58.8 vs 46.4%.
- **CLX 48.1% Ranked vs 64% in the SIM:** all of it is in overtime. CLX loses 33.0% of Ranked matches in overtime vs 16.5% in the SIM.
- **Tempo:**

  | | SIM (I u40) | Ranked humans |
  |---|---|---|
  | plays/min in 2x | 11.36 | 8.33 |
  | answer time | 4.72 s | 5.98 s |
  | push mean | 3.90 | 3.28 |

**Not explained:**
- Both sides taking a princess runs ~2.3x too often in both directions; the trailing opponent's scoring is untested.
- Regulation losses: +6.3 pp remainder.
- Pocket troops are just as frequent (44.7 vs 41%), yet the 1-1 X-Bow lock stays 36 vs 12%.
- **The 10-26 crown-state measurement** (`measure1026/q1_ot.out`, live CLX+CLXIII n 809 vs SIM CLXIII, E4 / cal):

  | Cell | Live | SIM E4 | SIM cal |
  |---|---|---|---|
  | Win | 48.6 | 72.6 | 58.8 |
  | Win in overtime | 48.0 | 69.6 | 66.1 |
  | Tiebreak win | 41.0 | 61.2 | 48.4 |
  | Lost exactly one princess, took none ("1-0 down" at drain) | **29.4** | 13.6 | 21.6 (17.6 pooled) |
  | Took exactly one princess, lost none ("1-0 up") | 32.0 | 51.0 | 44.3 |

- **Mortar decks:** SIM CLXIII wins 28.8% vs Mortar decks vs 66.8% vs other decks (−37.9 pp; `sim_mortar.out`). The live Mortar analysis (`live_siege.out`) was never written.

## 3. Human data available

**Live logs** (`scratchpad/gauntlet/L68/live_reader/live_play_*.jsonl`, 5,509 files; that count includes other accounts and failed logs):
- 2,271 main-account matches at ≥12k trophies, 51,285 detected opponent plays (22.6 per match). 2-tick frame logs exist for 1,085.
- Since 10-20: Ranked CLX 510, CLXIII 299, CLXIV 10.
- My estimate (not counted): ~3,100 main-account matches in total.

**What is observed per opponent play** (OPP_MODEL §5):
- First-sighting tick, card, cost, first-sighting position (late after a reader gap for 23.8% of plays), body count, and the public elixir counter before the play.
- Bodiless spells are visible only on the 2-tick frame path, about 4.5 per match.
- The full deck is seen in 38% of 13k matches; ≥7 cards in 72%.
- O1 knew the deck for 644 of 1,075 matches (57 completed from the census).
- Inferred hand is 99.4% exact where it can be determined (88% of plays).
- The public elixir counter reads +1.3-1.4 too high without spells; it is within 0.5 of the live counter 93.8 / 96.2% of the time.

**Per-archetype live coverage (≥12k):**

| Archetype | Matches | Archetype | Matches |
|---|---|---|---|
| Hog | 352 | Royal Giant | 83 |
| weak_other | 845 | P.E.K.K.A bridge | 44 |
| other | 621 | Lava | 42 |
| hyperbait | 148 | Royal Giant + Monk | 30 |
| Golem | 106 | | |

- Ranked 233, by win condition: Hog 15%, MK 14%, Goblin Barrel 9%; most win conditions have n 6-36. Tank/bridge-spam (BEAT) decks: n 83 (31 in the recent 100).
- Card census (10-17): 179 opponent cards; ~107 cards cover 90% of opponent plays.

**Pro corpus:** 14,661 replays (`L73/gen_v32/build.out`):
- 3.52M rows, both sides, **4,283 decks**, driven through the native engine at level 11.
- Top deck is icebow: 2,265 sides, 307k rows. Sources: RoyaleAPI crawls (icebow 2,073 battles, Hog-EQ 953, ending 09-06) plus the HF-derived pilot shards s0-s3.

**HF IL_Replay** (`scratchpad/gauntlet/L67/hf/replays`, 52 parquet files):
- 252,238 replays, 17.8M actions, 504,476 deck-sides, **52,566 decks**. The top 1,000 decks hold 73.7% of sides; 1,121 decks have ≥50 sides.
- 854,195 ability presses; trophies and dates are stripped.
- **Almost entirely unused for opponents** (only 603 icebow replays were driven).

**Other sources:**
- PRO2: 1,069 new owner-saved pages, 83,733 plays (379 Log Bait sides). Rows were never built because the only available driver is RoyaleSim.
- The polite RoyaleAPI crawler was stopped on 10-08 by Cloudflare.
- The official-API census (`crapi/`, battlelogs, no placements) ran briefly on the VM; it is backed up in `vm_backup_20261009`.

**Deck pools:**
- `mix/decks_live_train.json` (`decks_live_eval.json` is the eval version): 1,919 live opponents from 10-01..10-15 mapped to 895 HF decks (829 exact, 1,086 approximate). Never refreshed for Ranked.
- Variants: `w14/decks_live_train_beat3.json`, `mix/decks_live_train_cx3.json`, `memory/decks_live_train_beat3_cx3.json`.
- `livecal/census_evo.json` / `census_lad.json`: the top 1,000 HF decks.

## 4. How opponents plug into training and evaluation

**Training** (`C:\Users\benpe\ClashBot\pipeline\rl_royale.py`):
- `league_exploiters` (lines 1666-1712): `{ckpt, decks, share}` plus per-opponent `T` / `decide_every` / `reaction_ticks` / `tau`; a list form was added 10-25. `own_opp_cfg` (1715) applies the per-opponent settings.
- `league_opp_live` (1733-1764) gives the external and frozen opponents the live decision stack.
- Other keys: `league_opp_policy` (live|sample), `league_opp_T`, and global `opp_decide_every` / `opp_reaction_ticks` (188-213); `ot_start_share` (1863); `xbow_start_share` (1900); `league_external`; `league_decks` / `league_deck_weights` (the weights are unused).

**Evaluation:**
- `L74/gap/gap.py` lines 200-205: `--opp-ckpt` (default E4), `--opp-T` .1, `--opp-decide-every`, `--opp-reaction-ticks`, `--census-file`.
- `pipeline/search_s0.py --opp-gen`. `--opp-tau` and `--tap-loss` are applied through `push_cal/gate_eval.sh` and `w18/w18_eval.sh`.

**Deck conditioning:** `pipeline/model_gen.py:1-16, 255-261`. One GenModel pools the card and form embeddings of the deck it holds, picks cards with a pointer head over the hand, and waits with a pointer over the deck. There is no archetype, player or style token.

**Decode knobs, measured:**
- decide 10 → 40 makes the imitation nets more human and stronger.
- decide 60 / 80 and reaction delays buy style but open the game.
- Opponent tau 0.55 fixes style (0.58) and overtime with no strength cost, but X-Bow denial gets worse. Tau ≥0.65 collapses the opponent.

## 5. Why each effort fell short

**Recorded diagnoses:**
- **E4:** its push policy is soft, but the exact behaviour was never found (multi-card pushes do 24% less damage).
- **Imitation nets:** they cannot learn timing (gate head flat at 0.685) and are trained on mis-sighted live data.
- **RL rounds:** win-only RL saturates at ~0.47 training win. A policy that wins by fast tempo in regulation scores the same as one that wins the chip race into overtime, so knobs never change *how* it wins (DIAG_12 §4).
- **Style:** the floor of the W7 family is O2b's 0.65, and RL drifts the opponent toward faster answers.
- **Overall:** every opponent is trained only against icebow, scored mainly on matchup-blind averages, and never checked against the sealed live block that O5 planned.

**Metrics that exist for "plays like a human of this deck":**
- Style distance per archetype or signature card (`human/BEHAVIOUR.md`): RMS of Cohen's d over 9 position-free features, floor 0.05, bound 0.65. Per-archetype live n is small.
- Held-out live NLL on card / cell / gate, per deck (O2).
- O4 crown cells per archetype (only cells with live n ≥30).
- The push gate: 7 metrics × (all + 5 archetypes) = 42 cells, each within ±25%.
- X-Bow lock rate and shut-out share per archetype (`memory/xbow_arch.py`).
- The planned O5 sealed live-block prediction, which was never run.

**Gaps:**
- No per-deck NLL or style report has ever been produced. HF has the volume to support one (1,121 decks with ≥50 sides).

**Owed:**
- The gate-v2 scores for W18 R1-R3 and the corrected-handicap I u40 run.
- The Mortar live output.
