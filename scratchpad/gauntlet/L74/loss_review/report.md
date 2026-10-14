# Live loss review (L74, standing) -- generated 2026-10-14 13:04

Ledger: 2863 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 2804. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **2169 matches, 1144 W / 1025 L / 0 D**; 7704 threat episodes; 5417 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'derived': 265, 'ladder': 2513, 'nav': 26}. Agreement where both exist: nav vs ladder 2514/2515; tower-derived vs ladder 1965/1998 (error 1.7%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 14 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 67% of pushes with < 4 elixir (pros 24%); median 3.1 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 15.6% [13.1%, 17.9%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **156 of 1025 losses ended with the enemy tower within one Rocket**; Rocket was in hand 64% of the final 20 s but in hand AND affordable 7%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: X-Bow committed <= 10 s before a push; Slow first answer (> 2 s); Heavy spending in the 10 s before a push (>= 7); Gate below threshold >= 3 s while threatened; Sat at full elixir just before a push; Lethal Rocket window not used (>= 3 s); Placement error >= 1 tile.
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
| stack2k_cellref | 103 | 56-47-0 | 54% [45%, 64%] | 103 | 20261008_040027 | 20261008_125939 |
| towerref_w2 (current live) | 1034 | 554-480-0 | 54% [51%, 57%] | 1034 | 20261008_130524 | 20261014_090142 |
| wk_bait_u0060_g | 182 | 122-60-0 | 67% [60%, 73%] | 182 | 20261011_114328 | 20261014_122836 |
| adapt_fixed | 46 | 20-26-0 | 43% [30%, 58%] | 46 | 20261012_043946 | 20261012_072918 |
| adapt_alone | 47 | 20-27-0 | 43% [30%, 57%] | 47 | 20261012_073501 | 20261012_184346 |
| adapt2_final_grafted | 211 | 99-112-0 | 47% [40%, 54%] | 211 | 20261012_194040 | 20261013_092832 |
| newsim_base_r1_final_grafted | 163 | 83-80-0 | 51% [43%, 58%] | 163 | 20261013_094957 | 20261014_110433 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 1025 losses. The bot scored **0 crowns in 788 (77%)**; three-crowned in 180 (18%; 41 of them vs Golem). Score lines (bot-opp): 0-1 503, 0-3 123, 1-2 121, 0-0 109, 1-3 56, 1-1 55, 0-2 53.
* Opponent's first crown came in: 1x 356, OT 239, 2x 217, none 109, bot first 104. 1012/2169 matches reach overtime (47%); OT win rate 55%.
* Win rate by crowns conceded: 0: 90% (n=1150), 1: 15% (n=659), 2: 2% (n=179), 3: 1% (n=181). Value of the first conceded crown (used for 'wins at stake'): **0.75**. Value of the first crown TAKEN: 0.62.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 4737 / 2055 vs W 1572 / 2472; 2x: L 2799 / 1332 vs W 903 / 2422; OT: L 1567 / 947 vs W 593 / 1344

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **3.1** (losses 3.0, wins 3.2) | **6.0** |
| share of pushes met with < 4 elixir | **67%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **41% / 26%** | 24% / 24% |
| lost-episode rate overall | 36% | 24% |
| first play within 2 s of a push | 57% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 44% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 6.24 / 5.24 / 4.79 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 2.2 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **1.82 / 2.56** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 4.37 / 1.41 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 69% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 60% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): IceWizard|press|lo +0.18, Valkyrie|quiet|hi +0.17, Knight|press|lo +0.16, IceWizard|quiet|lo +0.16, Skeletons|quiet|lo +0.15, Skeletons|press|lo +0.15. Biggest deficits: Tesla|press|hi -0.42, Knight|press|hi -0.40, IceWizard|press|hi -0.37, Skeletons|press|hi -0.33, Log|press|hi -0.31.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| R1e (r1e31_u0155) | 360 | 0.35 | False | 51% | 2.4 | 79% | 5.8 / 4.2 / 3.5 | 6.20 |
| candidate | 17 | 0.35 | False | 29% | 2.0 | 80% | 5.7 / 4.3 / 3.1 | 6.98 |
| rseries_r2l_u0120 | 6 | 0.35 | False | 50% | 2.6 | 82% | 6.4 / 4.3 / 2.7 | 5.61 |
| stack2k_cellref | 103 | [0.35, 0.45, 0.55] | True | 54% | 3.2 | 64% | 6.2 / 5.2 / 5.1 | 4.56 |
| towerref_w2 (current live) | 1034 | [0.35, 0.45, 0.55] | False | 54% | 3.3 | 63% | 6.5 / 5.6 / 5.2 | 3.70 |
| wk_bait_u0060_g | 182 | 0.35 | False | 67% | 3.0 | 72% | 6.8 / 4.9 / 3.8 | 4.49 |
| adapt_fixed | 46 | [0.35, 0.45, 0.55] | False | 43% | 3.4 | 61% | 5.9 / 5.4 / 5.2 | 4.35 |
| adapt_alone | 47 | [0.35, 0.45, 0.55] | False | 43% | 3.3 | 64% | 6.0 / 5.3 / 5.1 | 4.38 |
| adapt2_final_grafted | 211 | [0.35, 0.45, 0.55] | False | 47% | 3.2 | 65% | 6.0 / 5.5 / 5.2 | 4.18 |
| newsim_base_r1_final_grafted | 163 | [0.35, 0.45, 0.55] | False | 51% | 2.6 | 66% | 5.5 / 5.3 / 5.1 | 4.47 |

Reading: total plays/min are the same as pros (10.2 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.75; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Low elixir when a push arrives (< 4)** | 2761/4098 eps (67%) | 2371/3606 eps (66%) | MH P(lost episode) 15.6% [13.1%, 17.9%] | 382.6 | 287.0 | (a) |
| 2 | **Cheap low-elixir plays above the median (4.2/min at < 5 elixir)** | 612/1025 (60%) | 472/1144 (41%) | L-W 18.4% [14.3%, 22.5%]; WR with/without 44% / 62% | - | 199.4 | (a) |
| 3 | **Air unit in the push** | 1550/4098 eps (38%) | 1208/3606 eps (33%) | MH P(lost episode) 10.3% [7.1%, 13.4%] | 187.0 | 140.3 | (a) |
| 4 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 156/1025 (15%) | n/a (end state of losses) | by ending: OT end 31, regulation end (Rocket -> tie -> OT) 48, OT sudden death 62, 3-crowned 15 | 141 | 103.7 | (a) |
| 5 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 1205/2017 X-Bows | 1415/2367 | MH dealt20 -405 HP [-498, -310]; MH dud rate 8.6% [5.2%, 12.3%] | 153.1 (1061k HP x 0.144 crowns/1k HP) | 94.4 | (a) |
| 6 | **Opponent public elixir lead >= 3 at push start** | 1151/4098 eps (28%) | 943/3606 eps (26%) | MH P(lost episode) 5.9% [3.3%, 8.5%] | 123.8 | 92.9 | (a) |
| 7 | **Rocket held >= 90% of the match** | 493/1025 (48%) | 439/1144 (38%) | L-W 9.7% [5.6%, 13.9%]; WR with/without 47% / 57% | - | 92.2 | (a) |
| 8 | **Offence spending before a push (>= 3 elixir)** | 659/4098 eps (16%) | 453/3606 eps (13%) | MH P(lost episode) 7.0% [3.4%, 10.5%] | 64.4 | 48.3 | (a) |
| 9 | **Opponent archetype: Golem** | 134/1025 (13%) | 83/1144 (7%) | L-W 5.8% [3.3%, 8.4%]; WR with/without 38% / 54% | - | 34.9 | (a) |
| 10 | **Log or Tornado on nothing (>= 2 in a match)** | 199/1025 (19%) | 171/1144 (15%) | L-W 4.5% [1.3%, 7.7%]; WR with/without 46% / 54% | - | 29.1 | (a) |
| 11 | **Tornado as the first answer** | 339/4098 eps (8%) | 208/3606 eps (6%) | MH P(lost episode) 14.0% [9.2%, 18.9%] | 22.3 | 16.7 | (a) |
| 12 | **Opponent archetype: Lava Hound** | 23/1025 (2%) | 12/1144 (1%) | L-W 1.2% [0.1%, 2.4%]; WR with/without 34% / 53% | - | 6.6 | (a) |
| 13 | **X-Bow committed <= 10 s before a push** | 462/4098 eps (11%) | 290/3606 eps (8%) | MH P(lost episode) -4.2% [-8.2%, -0.4%] | 0.0 | 0.0 | (c) |
| 14 | **Slow first answer (> 2 s)** | 1681/4098 eps (41%) | 1633/3606 eps (45%) | MH P(lost episode) -4.8% [-7.2%, -2.6%] | 0.0 | 0.0 | (c) |
| 15 | **Heavy spending in the 10 s before a push (>= 7)** | 1764/4098 eps (43%) | 1621/3606 eps (45%) | MH P(lost episode) -2.6% [-5.4%, -0.1%] | 19.2 | 0.0 | (c) |
| 16 | **Gate below threshold >= 3 s while threatened** | 974/4079 eps (24%) | 1185/3594 eps (33%) | MH P(lost episode) -14.0% [-16.5%, -11.7%] | 0.0 | 0.0 | (c) |
| 17 | **Sat at full elixir just before a push** | 139/4098 eps (3%) | 129/3606 eps (4%) | MH P(lost episode) -8.1% [-14.7%, -2.1%] | 0.0 | 0.0 | (c) |
| 18 | **Lethal Rocket window not used (>= 3 s)** | 27/1025 (3%) | 66/1144 (6%) | L-W -3.1% [-4.8%, -1.5%]; WR with/without 71% / 52% | - | 0.0 | (c) |
| 19 | **Placement error >= 1 tile** | 147/1025 (14%) | 229/1144 (20%) | L-W -5.7% [-8.8%, -2.5%]; WR with/without 61% / 51% | - | 0.0 | (c) |
| 20 | **Elixir wasted at the cap >= 5 in a match** | 110/1025 (11%) | 125/1144 (11%) | L-W -0.2% [-2.8%, 2.4%]; WR with/without 53% / 53% | - | - | (b) |
| 21 | **Gate freeze >= 10 s at >= 9.5 elixir** | 96/1022 (9%) | 102/1141 (9%) | L-W 0.5% [-2.0%, 2.9%]; WR with/without 52% / 53% | - | - | (b) |
| 22 | **Opponent archetype: Balloon** | 60/1025 (6%) | 60/1144 (5%) | L-W 0.6% [-1.3%, 2.6%]; WR with/without 50% / 53% | - | - | (b) |
| 23 | **Unconfirmed play (>= 1 in a match)** | 725/1025 (71%) | 784/1144 (69%) | L-W 2.2% [-1.7%, 6.1%]; WR with/without 52% / 55% | - | - | (b) |
| 24 | **CPU starvation (>= 3 warnings)** | 177/1025 (17%) | 230/1144 (20%) | L-W -2.8% [-6.1%, 0.5%]; WR with/without 57% / 52% | - | - | (b) |
| 25 | **Hero Ice Wizard ability pressed >= 3 times** | 195/1025 (19%) | 187/1144 (16%) | L-W 2.7% [-0.5%, 5.9%]; WR with/without 49% / 54% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 41% / 26%; tower-fall MH difference 7.5% [5.8%, 9.0%]; informative matches 1226
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 14.8% [10.6%, 19.3%] (n=3424); pushes >= 13 elixir 12.2% [5.4%, 19.2%] (n=1551); no air 16.7% [13.6%, 19.5%] (n=4946); R1e 19.6% [12.6%, 25.9%] (n=1236); stack2k + towerref_w2 15.0% [12.4%, 17.3%] (n=6468)
  * only 16% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261004_212221 t499-953; 20261004_225921 t911-1127; 20261004_225921 t2044-2509

**2. Cheap low-elixir plays above the median (4.2/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 4.79 vs W 3.86/min (diff 0.93 [0.76, 1.10]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**3. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 44% / 32%; tower-fall MH difference 6.8% [4.1%, 9.3%]; informative matches 708
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261005_061128 t901-1381

**4. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 55% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261005_052057 (OT end, enemy tower 40 HP); 20261005_071827 (OT end, enemy tower 180 HP); 20261005_072708 (regulation end (Rocket -> tie -> OT), enemy tower 315 HP)

**5. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 60% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by 0.21 elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.144 crowns per 1,000 HP, 2169 matches); informative matches 812
  * all locked X-Bows 32% dud, mean 1500 HP (n=4384); in losses 40% dud, mean 1301 HP (n=2017) vs wins 24% dud, mean 1669 HP (n=2367)
  * enemy push on my half at placement 37% dud, mean 1330 HP (n=274) vs not 31% dud, mean 1511 HP (n=4110)
  * < 1 elixir left after placing 36% dud, mean 1267 HP (n=766) vs >= 1 31% dud, mean 1549 HP (n=3618)
  * by phase: 1x 25% dud, mean 1821 HP (n=1910); 2x 36% dud, mean 1312 HP (n=1753); OT 38% dud, mean 1106 HP (n=721)
  * a hard counter seen near it before it died 40% dud, mean 1327 HP (n=1610); X-Bow life median 15.9 s
  * examples: 20261004_212221 t278-678 opp_el 7.9 dealt 51; 20261004_212221 t1817-2217 opp_el 7.4 dealt 0; 20261004_212221 t2609-3009 opp_el 7.1 dealt 51

**6. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 40% / 35%; tower-fall MH difference 5.9% [4.0%, 7.7%]; informative matches 1093
  * examples: 20261005_052057 t5513-6062; 20261005_061128 t2994-3587; 20261005_064528 t855-1158

**7. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**8. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 45% / 35%; tower-fall MH difference 5.8% [3.1%, 8.8%]; informative matches 701
  * examples: 20261005_052057 t5513-6062; 20261005_061128 t2994-3587; 20261005_065159 t2788-3361

**9. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**10. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 10% of 8811; Tornadoes on nothing 17% of 3797; Tornado centre on the enemy side 38% (pros 38%)

**11. Tornado as the first answer** -- the first play after threat start is Tornado
  * pooled lost-episode rate with/without: 57% / 35%; tower-fall MH difference 4.1% [0.5%, 7.9%]; informative matches 431
  * examples: 20261005_070248 t731-1329; 20261005_070510 t778-1224; 20261005_070510 t4059-4648

**12. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**13. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 38% / 36%; tower-fall MH difference -0.2% [-3.2%, 2.6%]; informative matches 524
  * examples: 20261005_061128 t2994-3587; 20261005_065159 t2788-3361; 20261005_071827 t3438-3995

**14. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 34% / 38%; tower-fall MH difference -1.7% [-3.3%, -0.0%]; informative matches 1385
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 24% answered <= 2 s vs 22% slower; push 10-13 elixir: lost 39% answered <= 2 s vs 42% slower; push 13-+ elixir: lost 63% answered <= 2 s vs 65% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261004_225921 t911-1127

**15. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 35% / 37%; tower-fall MH difference 0.6% [-1.5%, 2.5%]; informative matches 1058
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261004_212221 t499-953; 20261004_212221 t2055-2457; 20261004_212221 t3975-4376

**16. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 24% / 41%; tower-fall MH difference -5.4% [-7.1%, -3.6%]; informative matches 1178
  * examples: 20261005_061128 t2651-3246; 20261005_070248 t2180-2657; 20261005_070510 t474-666

**17. Sat at full elixir just before a push** -- >= 3 s at >= 9.9 elixir in the 15 s before threat start
  * pooled lost-episode rate with/without: 33% / 36%; tower-fall MH difference -7.1% [-11.3%, -2.9%]; informative matches 231
  * examples: 20261005_065159 t2788-3361; 20261005_072708 t2589-3186; 20261005_074149 t554-882

**18. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 333: rocketed 133, Rocket elsewhere 37; OT windows 110 (rocketed 85)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**19. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**20. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261011_075055 longest stretch at the cap 223.8 s; 20261010_205119 longest stretch at the cap 82.2 s; 20261010_222039 longest stretch at the cap 72.7 s

**21. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261011_075055 freeze 224.8 s; 20261007_124151 freeze 91.0 s; 20261010_205119 freeze 83.5 s

**22. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**23. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**24. CPU starvation (>= 3 warnings)** -- cpu_starved events

**25. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 155 losses: Rocket in hand 64% of the time; Rocket in hand AND >= 6 elixir 7%; matches that EVER had Rocket + 6 elixir in those 20 s: 55/155; median of the max elixir reached 6.5; Rocket taps in the window 87.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 459 | 55% [51%, 60%] | 24 | 31% |
| Giant (incl. Goblin/Electro) | 233 | 55% [48%, 61%] | 21 | 35% |
| Ram/Bridge spam | 230 | 53% [47%, 60%] | 21 | 38% |
| Golem | 217 | 38% [32%, 45%] | 41 | 50% |
| Other/no clear wincon | 191 | 57% [49%, 63%] | 14 | 38% |
| Spawners (Witch/huts) | 186 | 58% [50%, 64%] | 10 | 33% |
| X-Bow/Mortar | 126 | 56% [47%, 64%] | 4 | 32% |
| Balloon | 120 | 50% [41%, 59%] | 9 | 38% |
| Mega Knight | 105 | 48% [38%, 57%] | 11 | 34% |
| Royal Giant | 70 | 63% [51%, 73%] | 2 | 23% |
| Bait | 61 | 54% [42%, 66%] | 2 | 35% |
| Miner | 51 | 47% [34%, 60%] | 8 | 39% |
| Graveyard | 49 | 65% [51%, 77%] | 0 | 35% |
| P.E.K.K.A | 36 | 47% [32%, 63%] | 4 | 23% |
| Lava Hound | 35 | 34% [21%, 51%] | 10 | 65% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 6.2 / 5.2 / 4.8 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 67% -> <= 45%; median elixir at push start 3.1 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 36% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 156 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 15% -> lower; lethal windows rocketed up; OT win rate 55% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

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

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.01, 2x 2.01, OT 2.16 (constants used: 1 / 2 / 2).
* Opponent elixir counter vs EVAL_ONLY truth (446 frame-log matches): bias 0.21, mean abs error 0.58 elixir. Diagnostic only, never an input or a factor.
* Plays tapped before the previous play confirmed: 1847 in 2169 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.33 vs W 1.10.

