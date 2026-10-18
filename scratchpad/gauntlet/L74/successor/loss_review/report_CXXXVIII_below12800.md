# Live loss review (L74, standing) -- generated 2026-10-17 20:53

Ledger: 32 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 32. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **32 matches, 21 W / 11 L / 0 D**; 105 threat episodes; 114 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'ladder': 32}. Agreement where both exist: nav vs ladder 32/32; tower-derived vs ladder 32/32 (error 0.0%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 0 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 64% of pushes with < 4 elixir (pros 24%); median 3.4 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 12.9% [-6.7%, 32.3%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **1 of 11 losses ended with the enemy tower within one Rocket**; Rocket was in hand 27% of the final 20 s but in hand AND affordable 4%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: X-Bow committed <= 10 s before a push; Offence spending before a push (>= 3 elixir); Heavy spending in the 10 s before a push (>= 7).
* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.

## 1. Win/loss per checkpoint family (all valid matches)

| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |
|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 32 | 21-11-0 | 66% [48%, 80%] | 32 | 20261017_132941 | 20261017_152453 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 11 losses. The bot scored **0 crowns in 10 (91%)**; three-crowned in 2 (18%; 0 of them vs Golem). Score lines (bot-opp): 0-1 7, 0-3 2, 0-2 1, 1-1 1.
* Opponent's first crown came in: 1x 5, OT 3, 2x 2, bot first 1. 14/32 matches reach overtime (44%); OT win rate 79%.
* Win rate by crowns conceded: 0: 100% (n=20), 1: 11% (n=9), 2: 0% (n=1), 3: 0% (n=2). Value of the first conceded crown (used for 'wins at stake'): **0.89**. Value of the first crown TAKEN: 0.71.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 6014 / 2739 vs W 1426 / 2833; 2x: L 2350 / 1286 vs W 1052 / 2376; OT: L 1152 / 806 vs W 365 / 1564

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **3.4** (losses 2.8, wins 3.7) | **6.0** |
| share of pushes met with < 4 elixir | **64%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **36% / 16%** | 24% / 24% |
| lost-episode rate overall | 29% | 24% |
| first play within 2 s of a push | 49% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 50% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 6.54 / 6.11 / 5.46 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 5.5 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **1.31 / 1.95** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 4.23 / 1.75 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 89% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 54% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): Knight|press|lo +0.21, Skeletons|quiet|hi +0.19, Knight|quiet|lo +0.17, Tesla|quiet|lo +0.13, Log|press|lo +0.12, IceWizard|quiet|lo +0.11. Biggest deficits: Tornado|press|hi -0.35, Skeletons|press|hi -0.30, Knight|press|hi -0.29, Log|press|hi -0.27, Tesla|press|hi -0.26.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 32 | [0.35, 0.45, 0.55] | False | 66% | 3.4 | 64% | 6.5 / 6.1 / 5.5 | 3.26 |

Reading: total plays/min are the same as pros (9.2 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.89; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Cheap low-elixir plays above the median (2.9/min at < 5 elixir)** | 10/11 (91%) | 5/21 (24%) | L-W 67.1% [31.4%, 82.2%]; WR with/without 33% / 94% | - | 9.1 | (a) |
| 2 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 1/11 (9%) | n/a (end state of losses) | by ending: OT end 1 | 1 | 0.5 | (a) |
| 3 | **X-Bow committed <= 10 s before a push** | 10/42 eps (24%) | 10/63 eps (16%) | MH P(lost episode) -37.8% [-56.0%, -21.1%] | 0.0 | 0.0 | (c) |
| 4 | **Offence spending before a push (>= 3 elixir)** | 10/42 eps (24%) | 9/63 eps (14%) | MH P(lost episode) -35.1% [-53.6%, -16.8%] | 0.0 | 0.0 | (c) |
| 5 | **Heavy spending in the 10 s before a push (>= 7)** | 19/42 eps (45%) | 34/63 eps (54%) | MH P(lost episode) -23.2% [-43.5%, -0.5%] | 1.6 | 0.0 | (c) |
| 6 | **Low elixir when a push arrives (< 4)** | 32/42 eps (76%) | 35/63 eps (56%) | MH P(lost episode) 12.9% [-6.7%, 32.3%] | 0.0 | - | (b) |
| 7 | **Air unit in the push** | 8/42 eps (19%) | 23/63 eps (37%) | MH P(lost episode) 28.5% [-4.3%, 58.8%] | 0.9 | - | (b) |
| 8 | **Opponent public elixir lead >= 3 at push start** | 9/42 eps (21%) | 14/63 eps (22%) | MH P(lost episode) 14.4% [-15.2%, 45.4%] | 4.8 | - | (b) |
| 9 | **Slow first answer (> 2 s)** | 18/42 eps (43%) | 36/63 eps (57%) | MH P(lost episode) 10.8% [-7.3%, 32.3%] | 0.0 | - | (b) |
| 10 | **Gate below threshold >= 3 s while threatened** | 11/42 eps (26%) | 29/63 eps (46%) | MH P(lost episode) 6.3% [-14.9%, 27.7%] | 0.0 | - | (b) |
| 11 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 19/28 X-Bows | 37/75 | MH dealt20 -459 HP [-1159, 310]; MH dud rate 8.1% [-20.1%, 31.2%] | 3.0 (26k HP x 0.117 crowns/1k HP) | - | (b) |
| 12 | **Elixir wasted at the cap >= 5 in a match** | 4/11 (36%) | 6/21 (29%) | L-W 7.8% [-22.3%, 39.7%]; WR with/without 60% / 68% | - | - | (b) |
| 13 | **Gate freeze >= 10 s at >= 9.5 elixir** | 2/11 (18%) | 3/21 (14%) | L-W 3.9% [-20.3%, 34.8%]; WR with/without 60% / 67% | - | - | (b) |
| 14 | **Opponent archetype: Golem** | 0/11 (0%) | 2/21 (10%) | L-W -9.5% [-28.9%, 17.3%]; WR with/without 100% / 63% | - | - | (b) |
| 15 | **Opponent archetype: Lava Hound** | 1/11 (9%) | 0/21 (0%) | L-W 9.1% [-8.1%, 37.7%]; WR with/without 0% / 68% | - | - | (b) |
| 16 | **Opponent archetype: Balloon** | 1/11 (9%) | 0/21 (0%) | L-W 9.1% [-8.1%, 37.7%]; WR with/without 0% / 68% | - | - | (b) |
| 17 | **Lethal Rocket window not used (>= 3 s)** | 0/11 (0%) | 1/21 (5%) | L-W -4.8% [-22.7%, 21.4%]; WR with/without 100% / 65% | - | - | (b) |
| 18 | **Log or Tornado on nothing (>= 2 in a match)** | 1/11 (9%) | 1/21 (5%) | L-W 4.3% [-15.1%, 33.2%]; WR with/without 50% / 67% | - | - | (b) |
| 19 | **Unconfirmed play (>= 1 in a match)** | 7/11 (64%) | 15/21 (71%) | L-W -7.8% [-39.7%, 22.3%]; WR with/without 68% / 60% | - | - | (b) |
| 20 | **Placement error >= 1 tile** | 1/11 (9%) | 0/21 (0%) | L-W 9.1% [-8.1%, 37.7%]; WR with/without 0% / 68% | - | - | (b) |
| 21 | **CPU starvation (>= 3 warnings)** | 0/11 (0%) | 0/21 (0%) | L-W 0.0% [-15.5%, 25.9%]; WR with/without n/a / 66% | - | - | (b) |
| 22 | **Rocket held >= 90% of the match** | 5/11 (45%) | 14/21 (67%) | L-W -21.2% [-50.3%, 12.8%]; WR with/without 74% / 54% | - | - | (b) |
| 23 | **Hero Ice Wizard ability pressed >= 3 times** | 2/11 (18%) | 5/21 (24%) | L-W -5.6% [-30.6%, 26.7%]; WR with/without 71% / 64% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Cheap low-elixir plays above the median (2.9/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 4.68 vs W 2.54/min (diff 2.14 [1.19, 3.07]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**2. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 79% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261017_145920 (OT end, enemy tower 43 HP)

**3. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 10% / 33%; tower-fall MH difference -2.7% [-17.2%, 15.6%]; informative matches 13
  * examples: 20261017_144040 t2795-2994; 20261017_151038 t311-884

**4. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 11% / 33%; tower-fall MH difference -2.8% [-16.6%, 11.6%]; informative matches 13
  * examples: 20261017_144040 t2795-2994; 20261017_151038 t311-884

**5. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 15% / 42%; tower-fall MH difference 3.1% [-11.4%, 23.2%]; informative matches 17
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261017_134527 t878-1445; 20261017_142523 t3199-3798; 20261017_144040 t1060-1421

**6. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 36% / 16%; tower-fall MH difference -7.2% [-17.3%, 0.0%]; informative matches 15
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 10.7% [-14.3%, 40.0%] (n=45); pushes >= 13 elixir -28.6% [-71.4%, 0.0%] (n=25); no air 11.9% [-13.9%, 37.6%] (n=74); R1e n/a [n/a, n/a] (n=0); stack2k + towerref_w2 12.9% [-6.7%, 32.3%] (n=105)
  * only 3% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_134527 t878-1445

**7. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 39% / 24%; tower-fall MH difference 2.9% [0.0%, 9.3%]; informative matches 8
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_151038 t311-884

**8. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 26% / 29%; tower-fall MH difference 21.0% [0.0%, 50.8%]; informative matches 10
  * examples: 20261017_141825 t819-1179; 20261017_144040 t2795-2994; 20261017_145920 t825-1172

**9. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 28% / 29%; tower-fall MH difference -0.3% [-11.8%, 11.4%]; informative matches 20
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 17% answered <= 2 s vs 12% slower; push 10-13 elixir: lost 36% answered <= 2 s vs 33% slower; push 13-+ elixir: lost 46% answered <= 2 s vs 67% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_134527 t878-1445

**10. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 25% / 31%; tower-fall MH difference -3.5% [-10.4%, 2.5%]; informative matches 21
  * examples: 20261017_133313 t639-1230; 20261017_134527 t878-1445; 20261017_134527 t1115-1445

**11. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 54% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by n/a elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.117 crowns per 1,000 HP, 32 matches); informative matches 20
  * all locked X-Bows 29% dud, mean 1463 HP (n=103); in losses 46% dud, mean 1118 HP (n=28) vs wins 23% dud, mean 1592 HP (n=75)
  * enemy push on my half at placement 45% dud, mean 1150 HP (n=11) vs not 27% dud, mean 1501 HP (n=92)
  * < 1 elixir left after placing 50% dud, mean 1443 HP (n=12) vs >= 1 26% dud, mean 1466 HP (n=91)
  * by phase: 1x 19% dud, mean 1928 HP (n=36); 2x 36% dud, mean 1225 HP (n=45); OT 32% dud, mean 1189 HP (n=22)
  * a hard counter seen near it before it died 41% dud, mean 1385 HP (n=39); X-Bow life median 16.2 s
  * examples: 20261017_134527 t1553-1953 opp_el 9.4 dealt 51; 20261017_134527 t2685-3085 opp_el 8.7 dealt 0; 20261017_134527 t3333-3733 opp_el 10.0 dealt 0

**12. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261017_134527 longest stretch at the cap 6.8 s; 20261017_141825 longest stretch at the cap 8.6 s; 20261017_140433 longest stretch at the cap 4.9 s

**13. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261017_142944 freeze 10.5 s; 20261017_141825 freeze 10.0 s; 20261017_134527 freeze 7.5 s

**14. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**15. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**16. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**17. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 6: rocketed 5, Rocket elsewhere 0; OT windows 4 (rocketed 4)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**18. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 11% of 152; Tornadoes on nothing 4% of 23; Tornado centre on the enemy side 17% (pros 38%)

**19. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**20. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**21. CPU starvation (>= 3 warnings)** -- cpu_starved events

**22. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**23. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 1 losses: Rocket in hand 27% of the time; Rocket in hand AND >= 6 elixir 4%; matches that EVER had Rocket + 6 elixir in those 20 s: 1/1; median of the max elixir reached 7.1; Rocket taps in the window 0.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 9 | 44% [19%, 73%] | 0 | 41% |
| Spawners (Witch/huts) | 5 | 100% [57%, 100%] | 0 | 36% |
| Giant (incl. Goblin/Electro) | 5 | 60% [23%, 88%] | 0 | 18% |
| Ram/Bridge spam | 3 | 67% [21%, 94%] | 0 | 29% |
| Golem | 2 | 100% [34%, 100%] | 0 | 11% |
| Mega Knight | 2 | 50% [9%, 91%] | 1 | 40% |
| Lava Hound | 1 | 0% [0%, 79%] | 1 | 67% |
| Other/no clear wincon | 1 | 100% [21%, 100%] | 0 | 33% |
| Graveyard | 1 | 100% [21%, 100%] | 0 | 0% |
| X-Bow/Mortar | 1 | 100% [21%, 100%] | 0 | n/a |
| Balloon | 1 | 0% [0%, 79%] | 0 | 0% |
| Bait | 1 | 100% [21%, 100%] | 0 | n/a |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 6.5 / 6.1 / 5.5 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 64% -> <= 45%; median elixir at push start 3.4 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 29% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 1 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 9% -> lower; lethal windows rocketed up; OT win rate 79% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

**P3. Beatdown / air matchups (learned data weighting).** Golem / Lava Hound / Balloon are the worst classes (section 4c) and air in a push is the second-largest episode factor. Fix: up-weight pro rows from games against Golem / Lava / Balloon decks in the imitation data, and add those decks to the SIM/RL opponent pool. Proof: SIM win rate vs those archetypes (paired seeds) up without loss elsewhere; live class win rate up (needs ~60 matches per class for +-12 pp). Expected size (b): Golem 31% -> ~40% is about +1 pp overall.

**P4. X-Bow commit timing against the opponent's public elixir (learned).** Locked X-Bows placed into a full opponent bar deal less (section 4 row). Measure first: offline sensitivity of the X-Bow logit to the opponent-elixir input (perturb +-3 on pro rows); if near zero, add a training weight on pro X-Bow rows by the opponent-counter context (pros place 46% of X-Bows at >= 7 vs the bot's share in section 3). Also correct the counter's +0.3 over-read. Proof: share of X-Bows at >= 7 down toward pros, mean 20-s X-Bow damage up, X-Bows per match not down by more than 10%. Expected size (b): small, < 1 pp.

**P5. Gate freeze at full elixir (W4 hbt9, being deployed).** Proof: matches with a >= 10 s freeze at >= 9.5 elixir -> near 0; wasted elixir down; no rise in lost episodes. Expected size (b): < 1 pp (freeze matches are ~10% of losses).

Not proposed (contradicted or no measured link): faster first answers, less spending right before pushes, fewer unconfirmed plays / placement errors / CPU starvation, cycling Rocket out of the hand, fewer 'wasted' Logs/Tornadoes -- see their rows.

## 6. What this tool cannot measure yet

* Opponent card plays and their timing are inferred from first sightings of enemy bodies; spells without a projectile (Earthquake, Lightning, Poison, Freeze) are invisible, so 'X-Bow killed by a spell' and opponent spell cycles are not measured.
* Enemy body values (threat episodes, spell hits): the reader labels spawned children with the parent card, so review.py values a body at card value x its max_hp / the card's largest max_hp in the match, and Graveyard / Goblin Barrel bodies per unit (L74 econ2 fix; REVIEW_BODY_FIX=on). Before the fix a Witch's skeletons counted 5 elixir each.
* Causality: every 'at stake' number is associational. Episode rows hold the match fixed (MH) but not the moment-to-moment situation; only an A/B can prove a fix.
* The 26-tick forecast's own error (model_bodies vs the next raw state) is not measured here (model bodies carry no entity address).
* Hand cycle / next card: logs carry the 4-card hand only; 'Rocket stuck' is measured as time in hand, not as cycle position.
* Tesla/Knight kiting and pull-to-centre quality, Tornado pulls into King/Tesla range, Ice Wizard ability value: positions are logged, but no hit/damage attribution per defender exists in the logs.
* Trophies: logged for a handful of matches only (the ladder_nav OCR prints totals rarely).
* Older families (gen_s0 / league1c / rseries_r1) have results but mostly no board state.
* Pro baselines come from pro-vs-pro replays (stronger opponents, lower tower levels): rates are comparable in kind, not in absolute value.

## 7. Diagnostics

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.00, 2x 2.01, OT 2.12 (constants used: 1 / 2 / 2).
* Plays tapped before the previous play confirmed: 11 in 32 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.55 vs W 1.38.

