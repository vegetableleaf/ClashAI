# Live loss review (L74, standing) -- generated 2026-10-17 20:53

Ledger: 44 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 44. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **44 matches, 19 W / 25 L / 0 D**; 158 threat episodes; 165 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'ladder': 44}. Agreement where both exist: nav vs ladder 44/44; tower-derived vs ladder 44/44 (error 0.0%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 0 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 64% of pushes with < 4 elixir (pros 24%); median 2.8 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 17.0% [3.2%, 30.4%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **2 of 25 losses ended with the enemy tower within one Rocket**; Rocket was in hand 100% of the final 20 s but in hand AND affordable 2%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: Lethal Rocket window not used (>= 3 s).
* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.

## 1. Win/loss per checkpoint family (all valid matches)

| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |
|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 44 | 19-25-0 | 43% [30%, 58%] | 44 | 20261017_160806 | 20261017_203510 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 25 losses. The bot scored **0 crowns in 19 (76%)**; three-crowned in 2 (8%; 1 of them vs Golem). Score lines (bot-opp): 0-1 15, 1-1 4, 0-3 2, 0-0 2, 1-2 2.
* Opponent's first crown came in: OT 12, 1x 6, bot first 4, none 2, 2x 1. 28/44 matches reach overtime (64%); OT win rate 32%.
* Win rate by crowns conceded: 0: 89% (n=19), 1: 5% (n=20), 2: 33% (n=3), 3: 0% (n=2). Value of the first conceded crown (used for 'wins at stake'): **0.84**. Value of the first crown TAKEN: 0.65.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 3662 / 2095 vs W 2301 / 4395; 2x: L 2360 / 1279 vs W 1175 / 2564; OT: L 2224 / 1533 vs W 297 / 1307

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **2.8** (losses 2.8, wins 3.6) | **6.0** |
| share of pushes met with < 4 elixir | **64%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **40% / 32%** | 24% / 24% |
| lost-episode rate overall | 37% | 24% |
| first play within 2 s of a push | 61% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 54% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 6.15 / 6.02 / 5.47 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 5.2 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **1.78 / 2.19** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 4.13 / 1.65 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 91% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 63% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): Knight|press|lo +0.26, Skeletons|quiet|lo +0.26, Knight|quiet|lo +0.21, IceWizard|press|lo +0.21, Log|quiet|lo +0.20, IceWizard|quiet|hi +0.17. Biggest deficits: IceWizard|press|hi -0.33, Knight|press|hi -0.32, Tornado|press|hi -0.31, Skeletons|press|hi -0.28, Tesla|press|hi -0.25.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 44 | [0.35, 0.45, 0.55] | False | 43% | 2.8 | 64% | 6.2 / 6.0 / 5.5 | 3.97 |

Reading: total plays/min are the same as pros (9.7 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.84; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Low elixir when a push arrives (< 4)** | 77/113 eps (68%) | 24/45 eps (53%) | MH P(lost episode) 17.0% [3.2%, 30.4%] | 17.2 | 14.5 | (a) |
| 2 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 49/75 X-Bows | 36/60 | MH dealt20 -780 HP [-1359, -131]; MH dud rate 11.4% [-6.9%, 28.2%] | 11.2 (66k HP x 0.170 crowns/1k HP) | 7.3 | (a) |
| 3 | **Slow first answer (> 2 s)** | 41/113 eps (36%) | 20/45 eps (44%) | MH P(lost episode) 15.5% [1.0%, 29.5%] | 4.3 | 3.6 | (a) |
| 4 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 2/25 (8%) | n/a (end state of losses) | by ending: OT sudden death 2 | 2 | 2.0 | (a) |
| 5 | **Lethal Rocket window not used (>= 3 s)** | 0/25 (0%) | 5/19 (26%) | L-W -26.3% [-48.8%, -6.6%]; WR with/without 100% / 36% | - | 0.0 | (c) |
| 6 | **Air unit in the push** | 24/113 eps (21%) | 13/45 eps (29%) | MH P(lost episode) 5.4% [-32.8%, 44.8%] | 6.2 | - | (b) |
| 7 | **X-Bow committed <= 10 s before a push** | 16/113 eps (14%) | 7/45 eps (16%) | MH P(lost episode) 6.2% [-12.0%, 27.0%] | 2.2 | - | (b) |
| 8 | **Offence spending before a push (>= 3 elixir)** | 13/113 eps (12%) | 6/45 eps (13%) | MH P(lost episode) 6.0% [-13.7%, 34.1%] | 1.9 | - | (b) |
| 9 | **Opponent public elixir lead >= 3 at push start** | 30/113 eps (27%) | 8/45 eps (18%) | MH P(lost episode) 0.9% [-19.7%, 19.7%] | 2.2 | - | (b) |
| 10 | **Heavy spending in the 10 s before a push (>= 7)** | 63/113 eps (56%) | 23/45 eps (51%) | MH P(lost episode) -1.3% [-15.9%, 10.0%] | 7.5 | - | (b) |
| 11 | **Gate below threshold >= 3 s while threatened** | 27/113 eps (24%) | 12/45 eps (27%) | MH P(lost episode) -8.3% [-24.5%, 7.8%] | 2.5 | - | (b) |
| 12 | **Elixir wasted at the cap >= 5 in a match** | 4/25 (16%) | 6/19 (32%) | L-W -15.6% [-40.0%, 9.1%]; WR with/without 60% / 38% | - | - | (b) |
| 13 | **Gate freeze >= 10 s at >= 9.5 elixir** | 3/25 (12%) | 5/19 (26%) | L-W -14.3% [-38.1%, 8.8%]; WR with/without 62% / 39% | - | - | (b) |
| 14 | **Cheap low-elixir plays above the median (4.0/min at < 5 elixir)** | 15/25 (60%) | 6/19 (32%) | L-W 28.4% [-1.1%, 51.6%]; WR with/without 29% / 57% | - | - | (b) |
| 15 | **Opponent archetype: Golem** | 3/25 (12%) | 3/19 (16%) | L-W -3.8% [-26.9%, 16.9%]; WR with/without 50% / 42% | - | - | (b) |
| 16 | **Opponent archetype: Lava Hound** | 0/25 (0%) | 0/19 (0%) | L-W 0.0% [-16.8%, 13.3%]; WR with/without n/a / 43% | - | - | (b) |
| 17 | **Opponent archetype: Balloon** | 2/25 (8%) | 0/19 (0%) | L-W 8.0% [-9.8%, 25.0%]; WR with/without 0% / 45% | - | - | (b) |
| 18 | **Log or Tornado on nothing (>= 2 in a match)** | 2/25 (8%) | 4/19 (21%) | L-W -13.1% [-36.1%, 8.0%]; WR with/without 67% / 39% | - | - | (b) |
| 19 | **Unconfirmed play (>= 1 in a match)** | 20/25 (80%) | 12/19 (63%) | L-W 16.8% [-9.2%, 41.6%]; WR with/without 38% / 58% | - | - | (b) |
| 20 | **Placement error >= 1 tile** | 0/25 (0%) | 0/19 (0%) | L-W 0.0% [-16.8%, 13.3%]; WR with/without n/a / 43% | - | - | (b) |
| 21 | **CPU starvation (>= 3 warnings)** | 4/25 (16%) | 6/19 (32%) | L-W -15.6% [-40.0%, 9.1%]; WR with/without 60% / 38% | - | - | (b) |
| 22 | **Rocket held >= 90% of the match** | 15/25 (60%) | 12/19 (63%) | L-W -3.2% [-29.3%, 24.5%]; WR with/without 44% / 41% | - | - | (b) |
| 23 | **Hero Ice Wizard ability pressed >= 3 times** | 6/25 (24%) | 3/19 (16%) | L-W 8.2% [-16.9%, 30.2%]; WR with/without 33% / 46% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 40% / 32%; tower-fall MH difference 17.0% [6.1%, 29.4%]; informative matches 26
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 21.4% [-8.0%, 53.3%] (n=61); pushes >= 13 elixir 11.5% [-11.5%, 41.2%] (n=36); no air 13.4% [-2.3%, 27.2%] (n=121); R1e n/a [n/a, n/a] (n=0); stack2k + towerref_w2 17.0% [3.2%, 30.4%] (n=158)
  * only 2% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261017_163506 t1374-1871; 20261017_170310 t452-1040; 20261017_170616 t4515-4710

**2. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 63% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by n/a elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.170 crowns per 1,000 HP, 44 matches); informative matches 25
  * all locked X-Bows 34% dud, mean 1468 HP (n=135); in losses 47% dud, mean 1192 HP (n=75) vs wins 18% dud, mean 1813 HP (n=60)
  * enemy push on my half at placement 46% dud, mean 1254 HP (n=13) vs not 33% dud, mean 1491 HP (n=122)
  * < 1 elixir left after placing 39% dud, mean 1532 HP (n=18) vs >= 1 33% dud, mean 1458 HP (n=117)
  * by phase: 1x 23% dud, mean 1891 HP (n=56); 2x 38% dud, mean 1277 HP (n=48); OT 48% dud, mean 998 HP (n=31)
  * a hard counter seen near it before it died 45% dud, mean 1219 HP (n=51); X-Bow life median 15.8 s
  * examples: 20261017_162943 t3276-3676 opp_el 7.4 dealt 51; 20261017_162943 t4239-4639 opp_el 9.4 dealt 0; 20261017_163506 t1267-1667 opp_el 10.0 dealt 51

**3. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 43% / 33%; tower-fall MH difference 7.0% [-5.9%, 20.7%]; informative matches 26
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 25% answered <= 2 s vs 36% slower; push 10-13 elixir: lost 23% answered <= 2 s vs 45% slower; push 13-+ elixir: lost 61% answered <= 2 s vs 54% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261017_170310 t452-1040; 20261017_171023 t2640-2790; 20261017_182814 t4325-4692

**4. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 32% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261017_182814 (OT sudden death, enemy tower 391 HP); 20261017_184855 (OT sudden death, enemy tower 282 HP)

**5. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 14: rocketed 3, Rocket elsewhere 2; OT windows 2 (rocketed 2)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**6. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 59% / 30%; tower-fall MH difference 16.7% [-10.5%, 49.9%]; informative matches 9
  * examples: 20261017_170310 t452-1040; 20261017_170310 t2089-2681; 20261017_170310 t2789-3387

**7. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 35% / 37%; tower-fall MH difference 9.7% [-3.2%, 25.4%]; informative matches 13
  * examples: 20261017_163506 t1374-1871; 20261017_171023 t2640-2790; 20261017_171023 t3268-3865

**8. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 26% / 38%; tower-fall MH difference 10.2% [-7.6%, 32.2%]; informative matches 13
  * examples: 20261017_163506 t1374-1871; 20261017_171023 t3268-3865; 20261017_191430 t1105-1704

**9. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 34% / 38%; tower-fall MH difference 5.7% [-11.5%, 19.0%]; informative matches 21
  * examples: 20261017_170616 t4515-4710; 20261017_171023 t1374-1847; 20261017_171023 t2640-2790

**10. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 31% / 43%; tower-fall MH difference 8.7% [-1.6%, 17.2%]; informative matches 27
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261017_163506 t1374-1871; 20261017_170616 t4515-4710; 20261017_171023 t2640-2790

**11. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 23% / 41%; tower-fall MH difference 6.4% [-4.2%, 20.6%]; informative matches 24
  * examples: 20261017_171023 t2640-2790; 20261017_182814 t4325-4692; 20261017_184327 t3218-3696

**12. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261017_191430 longest stretch at the cap 51.1 s; 20261017_190905 longest stretch at the cap 23.1 s; 20261017_203152 longest stretch at the cap 3.1 s

**13. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261017_191430 freeze 51.1 s; 20261017_190905 freeze 24.1 s; 20261017_170616 freeze 14.8 s

**14. Cheap low-elixir plays above the median (4.0/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 4.49 vs W 3.17/min (diff 1.32 [0.33, 2.32]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**15. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**16. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**17. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**18. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 9% of 244; Tornadoes on nothing 10% of 61; Tornado centre on the enemy side 23% (pros 38%)

**19. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**20. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**21. CPU starvation (>= 3 warnings)** -- cpu_starved events

**22. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**23. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 2 losses: Rocket in hand 100% of the time; Rocket in hand AND >= 6 elixir 2%; matches that EVER had Rocket + 6 elixir in those 20 s: 1/2; median of the max elixir reached 7.2; Rocket taps in the window 2.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 12 | 17% [5%, 45%] | 1 | 31% |
| X-Bow/Mortar | 6 | 100% [61%, 100%] | 0 | 0% |
| Golem | 6 | 50% [19%, 81%] | 1 | 43% |
| Giant (incl. Goblin/Electro) | 5 | 20% [4%, 62%] | 0 | 33% |
| Ram/Bridge spam | 4 | 0% [0%, 49%] | 0 | 47% |
| Other/no clear wincon | 3 | 67% [21%, 94%] | 0 | 0% |
| Spawners (Witch/huts) | 2 | 50% [9%, 91%] | 0 | 30% |
| Graveyard | 2 | 100% [34%, 100%] | 0 | 50% |
| Balloon | 2 | 0% [0%, 66%] | 0 | 40% |
| Mega Knight | 1 | 100% [21%, 100%] | 0 | 50% |
| Royal Giant | 1 | 100% [21%, 100%] | 0 | 56% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 6.2 / 6.0 / 5.5 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 64% -> <= 45%; median elixir at push start 2.8 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 37% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 2 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 8% -> lower; lethal windows rocketed up; OT win rate 32% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

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

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.02, 2x 2.03, OT 2.12 (constants used: 1 / 2 / 2).
* Plays tapped before the previous play confirmed: 20 in 44 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.72 vs W 1.16.

