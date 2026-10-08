# Live loss review (L74, standing) -- generated 2026-10-08 18:28

Ledger: 1206 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 1173. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **538 matches, 271 W / 267 L / 0 D**; 1807 threat episodes; 1669 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'derived': 113, 'ladder': 1047, 'nav': 13}. Agreement where both exist: nav vs ladder 1047/1047; tower-derived vs ladder 521/532 (error 2.1%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 4 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 75% of pushes with < 4 elixir (pros 24%); median 2.5 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 17.9% [12.2%, 23.1%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **48 of 267 losses ended with the enemy tower within one Rocket**; Rocket was in hand 89% of the final 20 s but in hand AND affordable 7%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: Slow first answer (> 2 s); Gate below threshold >= 3 s while threatened; Placement error >= 1 tile.
* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.

## 1. Win/loss per checkpoint family (all valid matches)

| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |
|---|---|---|---|---|---|---|
| gen_s0 | 101 | 40-59-2 | 40% [31%, 49%] | 54 | 20260925_183254 | 20261004_132916 |
| league1c_u0075 | 201 | 102-99-0 | 51% [44%, 58%] | 27 | 20261002_201818 | 20261003_085834 |
| rseries_r1_u0155 | 303 | 155-148-0 | 51% [46%, 57%] | 38 | 20261003_090220 | 20261004_095316 |
| R1e (r1e31_u0155) | 390 | 198-192-0 | 51% [46%, 56%] | 360 | 20261004_205129 | 20261008_033553 |
| candidate | 17 | 5-12-0 | 29% [13%, 53%] | 17 | 20261006_124440 | 20261006_180120 |
| rseries_r2l_u0120 | 6 | 3-3-0 | 50% [19%, 81%] | 6 | 20261007_211123 | 20261007_212939 |
| stack2k_cellref | 102 | 55-47-0 | 54% [44%, 63%] | 102 | 20261008_040027 | 20261008_125939 |
| towerref_w2 (current live) | 53 | 26-27-0 | 49% [36%, 62%] | 53 | 20261008_130524 | 20261008_180623 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 267 losses. The bot scored **0 crowns in 188 (70%)**; three-crowned in 50 (19%; 13 of them vs Golem). Score lines (bot-opp): 0-1 114, 1-2 38, 0-0 33, 0-3 32, 1-1 23, 1-3 18, 0-2 9.
* Opponent's first crown came in: 1x 101, OT 47, 2x 47, bot first 39, none 33. 223/538 matches reach overtime (41%); OT win rate 45%.
* Win rate by crowns conceded: 0: 88% (n=282), 1: 14% (n=159), 2: 0% (n=47), 3: 0% (n=50). Value of the first conceded crown (used for 'wins at stake'): **0.74**. Value of the first crown TAKEN: 0.53.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 5138 / 2376 vs W 1637 / 3182; 2x: L 3072 / 1470 vs W 998 / 2516; OT: L 1897 / 1086 vs W 539 / 1280

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **2.5** (losses 2.5, wins 2.6) | **6.0** |
| share of pushes met with < 4 elixir | **75%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **44% / 29%** | 24% / 24% |
| lost-episode rate overall | 40% | 24% |
| first play within 2 s of a push | 63% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 51% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 5.91 / 4.52 / 3.95 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 2.1 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **2.70 / 2.98** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 3.61 / 0.99 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 86% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 58% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): Knight|quiet|lo +0.41, Skeletons|quiet|lo +0.38, IceWizard|quiet|lo +0.35, Knight|press|lo +0.30, Skeletons|press|lo +0.29, Log|quiet|lo +0.28. Biggest deficits: Tesla|press|hi -0.45, Knight|press|hi -0.42, Skeletons|press|hi -0.39, IceWizard|press|hi -0.38, Log|press|hi -0.32.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| R1e (r1e31_u0155) | 360 | 0.35 | False | 51% | 2.4 | 79% | 5.8 / 4.2 / 3.5 | 6.20 |
| candidate | 17 | 0.35 | False | 29% | 2.0 | 80% | 5.7 / 4.3 / 3.1 | 6.98 |
| rseries_r2l_u0120 | 6 | 0.35 | False | 50% | 2.6 | 82% | 6.4 / 4.3 / 2.7 | 5.61 |
| stack2k_cellref | 102 | [0.35, 0.45, 0.55] | True | 54% | 3.2 | 64% | 6.2 / 5.2 / 5.1 | 4.57 |
| towerref_w2 (current live) | 53 | [0.35, 0.45, 0.55] | False | 49% | 2.7 | 71% | 6.2 / 5.3 / 5.1 | 3.87 |

Reading: total plays/min are the same as pros (10.3 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.74; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Low elixir when a push arrives (< 4)** | 777/1045 eps (74%) | 577/762 eps (76%) | MH P(lost episode) 17.9% [12.2%, 23.1%] | 119.0 | 88.6 | (a) |
| 2 | **Cheap low-elixir plays above the median (5.3/min at < 5 elixir)** | 155/267 (58%) | 113/271 (42%) | L-W 16.4% [7.9%, 24.5%]; WR with/without 42% / 59% | - | 43.8 | (a) |
| 3 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 48/267 (18%) | n/a (end state of losses) | by ending: OT end 7, regulation end (Rocket -> tie -> OT) 17, OT sudden death 19, 3-crowned 5 | 43 | 30.1 | (a) |
| 4 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 368/653 X-Bows | 411/700 | MH dealt20 -456 HP [-658, -268]; MH dud rate 12.7% [6.2%, 18.5%] | 50.3 (355k HP x 0.142 crowns/1k HP) | 26.4 | (a) |
| 5 | **Opponent public elixir lead >= 3 at push start** | 351/1045 eps (34%) | 250/762 eps (33%) | MH P(lost episode) 6.0% [0.6%, 11.0%] | 34.0 | 25.3 | (a) |
| 6 | **Offence spending before a push (>= 3 elixir)** | 201/1045 eps (19%) | 95/762 eps (12%) | MH P(lost episode) 6.8% [0.9%, 14.4%] | 25.7 | 19.1 | (a) |
| 7 | **Opponent archetype: Golem** | 41/267 (15%) | 20/271 (7%) | L-W 8.0% [2.6%, 13.4%]; WR with/without 33% / 53% | - | 12.1 | (a) |
| 8 | **Elixir wasted at the cap >= 5 in a match** | 35/267 (13%) | 15/271 (6%) | L-W 7.6% [2.7%, 12.6%]; WR with/without 30% / 52% | - | 11.2 | (a) |
| 9 | **Gate freeze >= 10 s at >= 9.5 elixir** | 30/264 (11%) | 15/268 (6%) | L-W 5.8% [1.0%, 10.7%]; WR with/without 33% / 52% | - | 8.4 | (a) |
| 10 | **Tornado as the first answer** | 108/1045 eps (10%) | 59/762 eps (8%) | MH P(lost episode) 11.6% [2.8%, 20.8%] | 1.1 | 0.8 | (a) |
| 11 | **Slow first answer (> 2 s)** | 374/1045 eps (36%) | 298/762 eps (39%) | MH P(lost episode) -7.1% [-12.4%, -2.1%] | 0.0 | 0.0 | (c) |
| 12 | **Gate below threshold >= 3 s while threatened** | 224/1026 eps (22%) | 225/750 eps (30%) | MH P(lost episode) -17.4% [-23.1%, -12.2%] | 0.0 | 0.0 | (c) |
| 13 | **Placement error >= 1 tile** | 48/267 (18%) | 72/271 (27%) | L-W -8.6% [-15.5%, -1.6%]; WR with/without 60% / 48% | - | 0.0 | (c) |
| 14 | **Air unit in the push** | 384/1045 eps (37%) | 238/762 eps (31%) | MH P(lost episode) 8.0% [-0.1%, 15.6%] | 24.4 | - | (b) |
| 15 | **X-Bow committed <= 10 s before a push** | 137/1045 eps (13%) | 63/762 eps (8%) | MH P(lost episode) -6.2% [-14.0%, 2.3%] | 0.0 | - | (b) |
| 16 | **Heavy spending in the 10 s before a push (>= 7)** | 529/1045 eps (51%) | 401/762 eps (53%) | MH P(lost episode) -4.4% [-9.2%, 0.6%] | 0.0 | - | (b) |
| 17 | **Sat at full elixir just before a push** | 38/1045 eps (4%) | 21/762 eps (3%) | MH P(lost episode) -9.4% [-23.0%, 3.9%] | 0.0 | - | (b) |
| 18 | **Opponent archetype: Lava Hound** | 10/267 (4%) | 3/271 (1%) | L-W 2.6% [-0.1%, 5.7%]; WR with/without 23% / 51% | - | - | (b) |
| 19 | **Opponent archetype: Balloon** | 15/267 (6%) | 12/271 (4%) | L-W 1.2% [-2.6%, 5.1%]; WR with/without 44% / 51% | - | - | (b) |
| 20 | **Lethal Rocket window not used (>= 3 s)** | 12/267 (4%) | 17/271 (6%) | L-W -1.8% [-5.8%, 2.2%]; WR with/without 59% / 50% | - | - | (b) |
| 21 | **Log or Tornado on nothing (>= 2 in a match)** | 59/267 (22%) | 59/271 (22%) | L-W 0.3% [-6.7%, 7.3%]; WR with/without 50% / 50% | - | - | (b) |
| 22 | **Unconfirmed play (>= 1 in a match)** | 193/267 (72%) | 211/271 (78%) | L-W -5.6% [-12.8%, 1.7%]; WR with/without 52% / 45% | - | - | (b) |
| 23 | **CPU starvation (>= 3 warnings)** | 30/267 (11%) | 34/271 (13%) | L-W -1.3% [-6.8%, 4.2%]; WR with/without 53% / 50% | - | - | (b) |
| 24 | **Rocket held >= 90% of the match** | 179/267 (67%) | 165/271 (61%) | L-W 6.2% [-2.0%, 14.1%]; WR with/without 48% / 55% | - | - | (b) |
| 25 | **Hero Ice Wizard ability pressed >= 3 times** | 52/267 (19%) | 50/271 (18%) | L-W 1.0% [-5.6%, 7.7%]; WR with/without 49% / 51% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 44% / 29%; tower-fall MH difference 8.8% [4.6%, 13.1%]; informative matches 258
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 19.2% [9.3%, 29.9%] (n=838); pushes >= 13 elixir 19.7% [7.4%, 33.2%] (n=385); no air 18.2% [10.5%, 24.8%] (n=1185); R1e 19.6% [12.6%, 25.9%] (n=1236); stack2k + towerref_w2 15.0% [5.8%, 23.9%] (n=571)
  * only 3% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261004_212221 t499-953; 20261004_225921 t911-1127; 20261004_225921 t2044-2509

**2. Cheap low-elixir plays above the median (5.3/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 5.73 vs W 5.10/min (diff 0.63 [0.26, 0.99]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**3. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 45% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261005_052057 (OT end, enemy tower 40 HP); 20261005_071827 (OT end, enemy tower 180 HP); 20261005_072708 (regulation end (Rocket -> tie -> OT), enemy tower 315 HP)

**4. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 58% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by 0.33 elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.142 crowns per 1,000 HP, 538 matches); informative matches 251
  * all locked X-Bows 31% dud, mean 1543 HP (n=1353); in losses 41% dud, mean 1310 HP (n=653) vs wins 23% dud, mean 1761 HP (n=700)
  * enemy push on my half at placement 48% dud, mean 1216 HP (n=71) vs not 31% dud, mean 1561 HP (n=1282)
  * < 1 elixir left after placing 38% dud, mean 1215 HP (n=348) vs >= 1 29% dud, mean 1657 HP (n=1005)
  * by phase: 1x 22% dud, mean 1941 HP (n=617); 2x 37% dud, mean 1262 HP (n=536); OT 45% dud, mean 1067 HP (n=200)
  * a hard counter seen near it before it died 37% dud, mean 1425 HP (n=471); X-Bow life median 16.2 s
  * examples: 20261004_212221 t278-678 opp_el 7.9 dealt 51; 20261004_212221 t1817-2217 opp_el 7.4 dealt 0; 20261004_212221 t2609-3009 opp_el 7.1 dealt 51

**5. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 42% / 39%; tower-fall MH difference 5.7% [1.7%, 9.7%]; informative matches 290
  * examples: 20261005_052057 t5513-6062; 20261005_061128 t2994-3587; 20261005_064528 t855-1158

**6. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 48% / 39%; tower-fall MH difference 8.7% [3.6%, 14.0%]; informative matches 185
  * examples: 20261005_052057 t5513-6062; 20261005_061128 t2994-3587; 20261005_065159 t2788-3361

**7. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**8. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261005_072708 longest stretch at the cap 67.3 s; 20261008_133745 longest stretch at the cap 18.6 s; 20261008_152744 longest stretch at the cap 23.4 s

**9. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261007_124151 freeze 91.0 s; 20261005_072708 freeze 68.0 s; 20261007_211825 freeze 59.3 s

**10. Tornado as the first answer** -- the first play after threat start is Tornado
  * pooled lost-episode rate with/without: 54% / 39%; tower-fall MH difference 0.6% [-6.1%, 7.8%]; informative matches 129
  * examples: 20261005_070248 t731-1329; 20261005_070510 t778-1224; 20261005_070510 t4059-4648

**11. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 38% / 41%; tower-fall MH difference -1.5% [-5.2%, 2.3%]; informative matches 317
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 25% answered <= 2 s vs 23% slower; push 10-13 elixir: lost 43% answered <= 2 s vs 46% slower; push 13-+ elixir: lost 70% answered <= 2 s vs 78% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261004_225921 t911-1127

**12. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 28% / 45%; tower-fall MH difference -7.5% [-11.2%, -3.8%]; informative matches 261
  * examples: 20261005_061128 t2651-3246; 20261005_070248 t2180-2657; 20261005_070510 t474-666

**13. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**14. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 49% / 36%; tower-fall MH difference 3.9% [-2.4%, 9.9%]; informative matches 152
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261005_061128 t901-1381

**15. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 39% / 40%; tower-fall MH difference -1.1% [-7.4%, 5.3%]; informative matches 138
  * examples: 20261005_061128 t2994-3587; 20261005_065159 t2788-3361; 20261005_071827 t3438-3995

**16. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 35% / 46%; tower-fall MH difference -1.9% [-5.4%, 1.6%]; informative matches 301
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261004_212221 t3975-4376

**17. Sat at full elixir just before a push** -- >= 3 s at >= 9.9 elixir in the 15 s before threat start
  * pooled lost-episode rate with/without: 42% / 40%; tower-fall MH difference -8.8% [-17.9%, -0.0%]; informative matches 53
  * examples: 20261005_065159 t2788-3361; 20261005_072708 t2589-3186; 20261005_074149 t554-882

**18. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**19. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**20. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 81: rocketed 27, Rocket elsewhere 7; OT windows 28 (rocketed 16)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**21. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 10% of 2843; Tornadoes on nothing 16% of 1154; Tornado centre on the enemy side 48% (pros 38%)

**22. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**23. CPU starvation (>= 3 warnings)** -- cpu_starved events

**24. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**25. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 47 losses: Rocket in hand 89% of the time; Rocket in hand AND >= 6 elixir 7%; matches that EVER had Rocket + 6 elixir in those 20 s: 22/47; median of the max elixir reached 5.8; Rocket taps in the window 8.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 104 | 46% [37%, 56%] | 5 | 38% |
| Giant (incl. Goblin/Electro) | 63 | 54% [42%, 66%] | 8 | 41% |
| Golem | 61 | 33% [22%, 45%] | 13 | 48% |
| Ram/Bridge spam | 59 | 49% [37%, 62%] | 5 | 39% |
| Spawners (Witch/huts) | 52 | 71% [58%, 82%] | 3 | 30% |
| Other/no clear wincon | 44 | 57% [42%, 70%] | 3 | 42% |
| X-Bow/Mortar | 31 | 48% [32%, 65%] | 1 | 39% |
| Balloon | 27 | 44% [28%, 63%] | 2 | 44% |
| Mega Knight | 22 | 50% [31%, 69%] | 2 | 37% |
| Royal Giant | 17 | 65% [41%, 83%] | 0 | 20% |
| Bait | 15 | 53% [30%, 75%] | 0 | 36% |
| Graveyard | 14 | 71% [45%, 88%] | 0 | 47% |
| Lava Hound | 13 | 23% [8%, 50%] | 4 | 66% |
| Miner | 11 | 55% [28%, 79%] | 3 | 45% |
| P.E.K.K.A | 5 | 40% [12%, 77%] | 1 | 28% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 5.9 / 4.5 / 4.0 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 75% -> <= 45%; median elixir at push start 2.5 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 40% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 48 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 18% -> lower; lethal windows rocketed up; OT win rate 45% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

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

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.01, 2x 2.01, OT 2.13 (constants used: 1 / 2 / 2).
* Opponent elixir counter vs EVAL_ONLY truth (124 frame-log matches): bias 0.33, mean abs error 0.52 elixir. Diagnostic only, never an input or a factor.
* Plays tapped before the previous play confirmed: 247 in 538 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.55 vs W 1.30.

