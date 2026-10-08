# Live loss review (L74, standing) -- generated 2026-10-08 17:43

Ledger: 1196 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 1163. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **528 matches, 268 W / 260 L / 0 D**; 2372 threat episodes; 1636 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'derived': 111, 'ladder': 1047, 'nav': 5}. Agreement where both exist: nav vs ladder 1047/1047; tower-derived vs ladder 521/532 (error 2.1%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 4 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 70% of pushes with < 4 elixir (pros 24%); median 2.7 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 17.4% [12.5%, 21.4%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **48 of 260 losses ended with the enemy tower within one Rocket**; Rocket was in hand 89% of the final 20 s but in hand AND affordable 7%: the same economy problem.
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
| towerref_w2 (current live) | 43 | 23-20-0 | 53% [39%, 67%] | 43 | 20261008_130524 | 20261008_172819 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 260 losses. The bot scored **0 crowns in 184 (71%)**; three-crowned in 48 (18%; 13 of them vs Golem). Score lines (bot-opp): 0-1 111, 1-2 37, 0-0 32, 0-3 32, 1-1 23, 1-3 16, 0-2 9.
* Opponent's first crown came in: 1x 99, 2x 47, OT 45, bot first 37, none 32. 217/528 matches reach overtime (41%); OT win rate 45%.
* Win rate by crowns conceded: 0: 89% (n=279), 1: 14% (n=155), 2: 0% (n=46), 3: 0% (n=48). Value of the first conceded crown (used for 'wins at stake'): **0.75**. Value of the first crown TAKEN: 0.53.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 5084 / 2352 vs W 1636 / 3178; 2x: L 3103 / 1483 vs W 983 / 2509; OT: L 1912 / 1087 vs W 542 / 1279

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **2.7** (losses 2.6, wins 2.8) | **6.0** |
| share of pushes met with < 4 elixir | **70%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **38% / 24%** | 24% / 24% |
| lost-episode rate overall | 33% | 24% |
| first play within 2 s of a push | 61% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 50% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 5.92 / 4.51 / 3.92 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 2.0 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **2.47 / 3.24** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 3.45 / 1.13 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 86% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 57% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): Knight|press|lo +0.36, Knight|quiet|lo +0.35, Skeletons|press|lo +0.34, Skeletons|quiet|lo +0.34, IceWizard|press|lo +0.32, IceWizard|quiet|lo +0.31. Biggest deficits: Tesla|press|hi -0.43, Knight|press|hi -0.40, Skeletons|press|hi -0.37, IceWizard|press|hi -0.35, Tornado|press|hi -0.30.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| R1e (r1e31_u0155) | 360 | 0.35 | False | 51% | 2.6 | 73% | 5.8 / 4.2 / 3.5 | 6.20 |
| candidate | 17 | 0.35 | False | 29% | 2.7 | 74% | 5.7 / 4.3 / 3.1 | 6.98 |
| rseries_r2l_u0120 | 6 | 0.35 | False | 50% | 2.6 | 82% | 6.4 / 4.3 / 2.7 | 5.61 |
| stack2k_cellref | 102 | [0.35, 0.45, 0.55] | True | 54% | 3.2 | 62% | 6.2 / 5.2 / 5.1 | 4.57 |
| towerref_w2 (current live) | 43 | [0.35, 0.45, 0.55] | False | 53% | 3.2 | 60% | 6.4 / 5.4 / 5.1 | 3.78 |

Reading: total plays/min are the same as pros (10.3 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.75; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Low elixir when a push arrives (< 4)** | 873/1251 eps (70%) | 788/1121 eps (70%) | MH P(lost episode) 17.4% [12.5%, 21.4%] | 138.8 | 104.1 | (a) |
| 2 | **Cheap low-elixir plays above the median (5.3/min at < 5 elixir)** | 153/260 (59%) | 110/268 (41%) | L-W 17.8% [9.3%, 26.0%]; WR with/without 42% / 60% | - | 46.8 | (a) |
| 3 | **Air unit in the push** | 433/1251 eps (35%) | 306/1121 eps (27%) | MH P(lost episode) 14.6% [8.3%, 20.4%] | 49.6 | 37.2 | (a) |
| 4 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 48/260 (18%) | n/a (end state of losses) | by ending: OT end 7, regulation end (Rocket -> tie -> OT) 17, OT sudden death 19, 3-crowned 5 | 43 | 30.2 | (a) |
| 5 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 360/639 X-Bows | 404/691 | MH dealt20 -448 HP [-646, -263]; MH dud rate 12.6% [6.1%, 18.5%] | 48.5 (342k HP x 0.142 crowns/1k HP) | 25.8 | (a) |
| 6 | **Offence spending before a push (>= 3 elixir)** | 283/1251 eps (23%) | 186/1121 eps (17%) | MH P(lost episode) 6.6% [1.2%, 11.3%] | 29.3 | 21.9 | (a) |
| 7 | **Opponent archetype: Golem** | 41/260 (16%) | 19/268 (7%) | L-W 8.7% [3.3%, 14.2%]; WR with/without 32% / 53% | - | 12.9 | (a) |
| 8 | **Elixir wasted at the cap >= 5 in a match** | 33/260 (13%) | 15/268 (6%) | L-W 7.1% [2.2%, 12.2%]; WR with/without 31% / 53% | - | 10.3 | (a) |
| 9 | **Gate freeze >= 10 s at >= 9.5 elixir** | 28/257 (11%) | 15/265 (6%) | L-W 5.2% [0.5%, 10.2%]; WR with/without 35% / 52% | - | 7.4 | (a) |
| 10 | **Tornado as the first answer** | 108/1251 eps (9%) | 79/1121 eps (7%) | MH P(lost episode) 19.9% [12.0%, 26.4%] | 2.2 | 1.7 | (a) |
| 11 | **Slow first answer (> 2 s)** | 465/1251 eps (37%) | 456/1121 eps (41%) | MH P(lost episode) -7.4% [-11.1%, -3.7%] | 0.0 | 0.0 | (c) |
| 12 | **Gate below threshold >= 3 s while threatened** | 289/1227 eps (24%) | 328/1098 eps (30%) | MH P(lost episode) -16.4% [-21.0%, -12.5%] | 0.0 | 0.0 | (c) |
| 13 | **Placement error >= 1 tile** | 48/260 (18%) | 72/268 (27%) | L-W -8.4% [-15.4%, -1.2%]; WR with/without 60% / 48% | - | 0.0 | (c) |
| 14 | **X-Bow committed <= 10 s before a push** | 210/1251 eps (17%) | 128/1121 eps (11%) | MH P(lost episode) -0.2% [-6.0%, 5.6%] | 2.6 | - | (b) |
| 15 | **Opponent public elixir lead >= 3 at push start** | 441/1251 eps (35%) | 383/1121 eps (34%) | MH P(lost episode) 4.2% [-0.1%, 8.3%] | 34.4 | - | (b) |
| 16 | **Heavy spending in the 10 s before a push (>= 7)** | 616/1251 eps (49%) | 565/1121 eps (50%) | MH P(lost episode) 0.8% [-3.5%, 4.9%] | 23.6 | - | (b) |
| 17 | **Sat at full elixir just before a push** | 51/1251 eps (4%) | 42/1121 eps (4%) | MH P(lost episode) -10.6% [-20.8%, 1.1%] | 0.0 | - | (b) |
| 18 | **Opponent archetype: Lava Hound** | 10/260 (4%) | 3/268 (1%) | L-W 2.7% [-0.0%, 5.9%]; WR with/without 23% / 51% | - | - | (b) |
| 19 | **Opponent archetype: Balloon** | 15/260 (6%) | 11/268 (4%) | L-W 1.7% [-2.2%, 5.6%]; WR with/without 42% / 51% | - | - | (b) |
| 20 | **Lethal Rocket window not used (>= 3 s)** | 12/260 (5%) | 16/268 (6%) | L-W -1.4% [-5.4%, 2.6%]; WR with/without 57% / 50% | - | - | (b) |
| 21 | **Log or Tornado on nothing (>= 2 in a match)** | 58/260 (22%) | 59/268 (22%) | L-W 0.3% [-6.8%, 7.4%]; WR with/without 50% / 51% | - | - | (b) |
| 22 | **Unconfirmed play (>= 1 in a match)** | 188/260 (72%) | 208/268 (78%) | L-W -5.3% [-12.6%, 2.1%]; WR with/without 53% / 45% | - | - | (b) |
| 23 | **CPU starvation (>= 3 warnings)** | 29/260 (11%) | 34/268 (13%) | L-W -1.5% [-7.1%, 4.1%]; WR with/without 54% / 50% | - | - | (b) |
| 24 | **Rocket held >= 90% of the match** | 172/260 (66%) | 163/268 (61%) | L-W 5.3% [-2.9%, 13.4%]; WR with/without 49% / 54% | - | - | (b) |
| 25 | **Hero Ice Wizard ability pressed >= 3 times** | 51/260 (20%) | 50/268 (19%) | L-W 1.0% [-5.8%, 7.7%]; WR with/without 50% / 51% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 38% / 24%; tower-fall MH difference 8.4% [5.1%, 11.3%]; informative matches 344
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 21.0% [12.6%, 28.4%] (n=1121); pushes >= 13 elixir 21.3% [14.7%, 27.8%] (n=1080); no air 17.1% [11.7%, 22.4%] (n=1633); R1e 17.5% [12.1%, 22.7%] (n=1707); stack2k + towerref_w2 17.1% [8.7%, 25.9%] (n=665)
  * only 4% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261004_212221 t499-1025; 20261004_212221 t3198-3693; 20261004_225921 t857-1127

**2. Cheap low-elixir plays above the median (5.3/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 5.78 vs W 5.11/min (diff 0.67 [0.31, 1.04]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**3. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 43% / 29%; tower-fall MH difference 6.7% [2.3%, 11.5%]; informative matches 178
  * examples: 20261004_212221 t499-1025; 20261004_212221 t2055-2457; 20261005_061128 t901-1381

**4. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 45% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261005_052057 (OT end, enemy tower 40 HP); 20261005_071827 (OT end, enemy tower 180 HP); 20261005_072708 (regulation end (Rocket -> tie -> OT), enemy tower 315 HP)

**5. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 57% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by 0.35 elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.142 crowns per 1,000 HP, 528 matches); informative matches 246
  * all locked X-Bows 32% dud, mean 1538 HP (n=1330); in losses 41% dud, mean 1296 HP (n=639) vs wins 23% dud, mean 1762 HP (n=691)
  * enemy push on my half at placement 47% dud, mean 1149 HP (n=100) vs not 31% dud, mean 1570 HP (n=1230)
  * < 1 elixir left after placing 38% dud, mean 1207 HP (n=347) vs >= 1 30% dud, mean 1655 HP (n=983)
  * by phase: 1x 23% dud, mean 1932 HP (n=606); 2x 37% dud, mean 1264 HP (n=526); OT 45% dud, mean 1061 HP (n=198)
  * a hard counter seen near it before it died 38% dud, mean 1422 HP (n=461); X-Bow life median 16.2 s
  * examples: 20261004_212221 t278-678 opp_el 7.9 dealt 51; 20261004_212221 t1817-2217 opp_el 7.4 dealt 0; 20261004_212221 t2609-3009 opp_el 7.1 dealt 51

**6. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 41% / 32%; tower-fall MH difference 6.2% [2.8%, 9.9%]; informative matches 277
  * examples: 20261004_212221 t3198-3693; 20261005_052057 t5513-6062; 20261005_061128 t2994-3587

**7. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**8. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261005_072708 longest stretch at the cap 67.3 s; 20261008_133745 longest stretch at the cap 18.6 s; 20261008_152744 longest stretch at the cap 23.4 s

**9. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261007_124151 freeze 91.0 s; 20261005_072708 freeze 68.0 s; 20261007_211825 freeze 59.3 s

**10. Tornado as the first answer** -- the first play after threat start is Tornado
  * pooled lost-episode rate with/without: 52% / 32%; tower-fall MH difference 1.2% [-4.2%, 6.5%]; informative matches 148
  * examples: 20261004_225921 t857-1127; 20261005_064528 t3180-3680; 20261005_070248 t731-1329

**11. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 30% / 36%; tower-fall MH difference -2.4% [-5.4%, 0.5%]; informative matches 382
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 19% answered <= 2 s vs 17% slower; push 10-13 elixir: lost 29% answered <= 2 s vs 23% slower; push 13-+ elixir: lost 48% answered <= 2 s vs 48% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261004_212221 t499-1025; 20261004_212221 t2055-2457; 20261004_225921 t857-1127

**12. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 21% / 38%; tower-fall MH difference -7.8% [-10.6%, -4.8%]; informative matches 320
  * examples: 20261005_061128 t2651-3246; 20261005_070248 t2180-2657; 20261005_070935 t2104-2675

**13. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**14. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 36% / 33%; tower-fall MH difference 0.8% [-3.5%, 5.0%]; informative matches 228
  * examples: 20261004_212221 t3198-3693; 20261005_061128 t2994-3587; 20261005_065159 t2788-3361

**15. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 35% / 33%; tower-fall MH difference 4.2% [1.1%, 6.9%]; informative matches 358
  * examples: 20261004_212221 t3198-3693; 20261004_225921 t857-1127; 20261005_052057 t5513-6062

**16. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 31% / 36%; tower-fall MH difference 2.0% [-0.7%, 4.6%]; informative matches 370
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261004_212221 t499-1025; 20261004_212221 t2055-2457; 20261004_212221 t3198-3693

**17. Sat at full elixir just before a push** -- >= 3 s at >= 9.9 elixir in the 15 s before threat start
  * pooled lost-episode rate with/without: 30% / 34%; tower-fall MH difference -10.5% [-17.5%, -3.6%]; informative matches 87
  * examples: 20261005_065159 t2788-3361; 20261005_072708 t2589-3186; 20261005_074149 t476-902

**18. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**19. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**20. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 77: rocketed 25, Rocket elsewhere 7; OT windows 26 (rocketed 14)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**21. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 10% of 2793; Tornadoes on nothing 16% of 1136; Tornado centre on the enemy side 48% (pros 38%)

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
| Hog (incl. Royal Hogs) | 102 | 47% [38%, 57%] | 4 | 37% |
| Giant (incl. Goblin/Electro) | 63 | 54% [42%, 66%] | 8 | 36% |
| Golem | 60 | 32% [21%, 44%] | 13 | 41% |
| Ram/Bridge spam | 58 | 50% [38%, 62%] | 5 | 30% |
| Spawners (Witch/huts) | 51 | 73% [59%, 83%] | 3 | 20% |
| Other/no clear wincon | 44 | 57% [42%, 70%] | 3 | 33% |
| X-Bow/Mortar | 31 | 48% [32%, 65%] | 1 | 26% |
| Balloon | 26 | 42% [26%, 61%] | 2 | 40% |
| Mega Knight | 22 | 50% [31%, 69%] | 2 | 33% |
| Royal Giant | 17 | 65% [41%, 83%] | 0 | 22% |
| Bait | 14 | 57% [33%, 79%] | 0 | 21% |
| Graveyard | 13 | 77% [50%, 92%] | 0 | 33% |
| Lava Hound | 13 | 23% [8%, 50%] | 4 | 60% |
| Miner | 10 | 60% [31%, 83%] | 2 | 36% |
| P.E.K.K.A | 4 | 25% [5%, 70%] | 1 | 31% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 5.9 / 4.5 / 3.9 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 70% -> <= 45%; median elixir at push start 2.7 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 33% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 48 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 18% -> lower; lethal windows rocketed up; OT win rate 45% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

**P3. Beatdown / air matchups (learned data weighting).** Golem / Lava Hound / Balloon are the worst classes (section 4c) and air in a push is the second-largest episode factor. Fix: up-weight pro rows from games against Golem / Lava / Balloon decks in the imitation data, and add those decks to the SIM/RL opponent pool. Proof: SIM win rate vs those archetypes (paired seeds) up without loss elsewhere; live class win rate up (needs ~60 matches per class for +-12 pp). Expected size (b): Golem 31% -> ~40% is about +1 pp overall.

**P4. X-Bow commit timing against the opponent's public elixir (learned).** Locked X-Bows placed into a full opponent bar deal less (section 4 row). Measure first: offline sensitivity of the X-Bow logit to the opponent-elixir input (perturb +-3 on pro rows); if near zero, add a training weight on pro X-Bow rows by the opponent-counter context (pros place 46% of X-Bows at >= 7 vs the bot's share in section 3). Also correct the counter's +0.3 over-read. Proof: share of X-Bows at >= 7 down toward pros, mean 20-s X-Bow damage up, X-Bows per match not down by more than 10%. Expected size (b): small, < 1 pp.

**P5. Gate freeze at full elixir (W4 hbt9, being deployed).** Proof: matches with a >= 10 s freeze at >= 9.5 elixir -> near 0; wasted elixir down; no rise in lost episodes. Expected size (b): < 1 pp (freeze matches are ~10% of losses).

Not proposed (contradicted or no measured link): faster first answers, less spending right before pushes, fewer unconfirmed plays / placement errors / CPU starvation, cycling Rocket out of the hand, fewer 'wasted' Logs/Tornadoes -- see their rows.

## 6. What this tool cannot measure yet

* Opponent card plays and their timing are inferred from first sightings of enemy bodies; spells without a projectile (Earthquake, Lightning, Poison, Freeze) are invisible, so 'X-Bow killed by a spell' and opponent spell cycles are not measured.
* Causality: every 'at stake' number is associational. Episode rows hold the match fixed (MH) but not the moment-to-moment situation; only an A/B can prove a fix.
* The 26-tick forecast's own error (model_bodies vs the next raw state) is not measured here (model bodies carry no entity address).
* Hand cycle / next card: logs carry the 4-card hand only; 'Rocket stuck' is measured as time in hand, not as cycle position.
* Tesla/Knight kiting and pull-to-centre quality, Tornado pulls into King/Tesla range, Ice Wizard ability value: positions are logged, but no hit/damage attribution per defender exists in the logs.
* Trophies: logged for a handful of matches only (the ladder_nav OCR prints totals rarely).
* Older families (gen_s0 / league1c / rseries_r1) have results but mostly no board state.
* Pro baselines come from pro-vs-pro replays (stronger opponents, lower tower levels): rates are comparable in kind, not in absolute value.

## 7. Diagnostics

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.01, 2x 2.01, OT 2.13 (constants used: 1 / 2 / 2).
* Opponent elixir counter vs EVAL_ONLY truth (114 frame-log matches): bias 0.35, mean abs error 0.54 elixir. Diagnostic only, never an input or a factor.
* Plays tapped before the previous play confirmed: 240 in 528 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.55 vs W 1.31.

