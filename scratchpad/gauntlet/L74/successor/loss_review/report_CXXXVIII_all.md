# Live loss review (L74, standing) -- generated 2026-10-17 20:53

Ledger: 76 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 76. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **76 matches, 40 W / 36 L / 0 D**; 263 threat episodes; 279 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'ladder': 76}. Agreement where both exist: nav vs ladder 76/76; tower-derived vs ladder 76/76 (error 0.0%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 0 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 64% of pushes with < 4 elixir (pros 24%); median 3.2 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 15.6% [3.5%, 26.7%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **3 of 36 losses ended with the enemy tower within one Rocket**; Rocket was in hand 76% of the final 20 s but in hand AND affordable 2%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: Lethal Rocket window not used (>= 3 s).
* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.

## 1. Win/loss per checkpoint family (all valid matches)

| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |
|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 76 | 40-36-0 | 53% [42%, 63%] | 76 | 20261017_132941 | 20261017_203510 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 36 losses. The bot scored **0 crowns in 29 (81%)**; three-crowned in 4 (11%; 1 of them vs Golem). Score lines (bot-opp): 0-1 22, 1-1 5, 0-3 4, 0-0 2, 1-2 2, 0-2 1.
* Opponent's first crown came in: OT 15, 1x 11, bot first 5, 2x 3, none 2. 42/76 matches reach overtime (55%); OT win rate 48%.
* Win rate by crowns conceded: 0: 95% (n=39), 1: 7% (n=29), 2: 25% (n=4), 3: 0% (n=4). Value of the first conceded crown (used for 'wins at stake'): **0.88**. Value of the first crown TAKEN: 0.69.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 4381 / 2292 vs W 1842 / 3575; 2x: L 2357 / 1281 vs W 1111 / 2465; OT: L 1922 / 1328 vs W 333 / 1442

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **3.2** (losses 2.8, wins 3.7) | **6.0** |
| share of pushes met with < 4 elixir | **64%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **38% / 25%** | 24% / 24% |
| lost-episode rate overall | 33% | 24% |
| first play within 2 s of a push | 56% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 53% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 6.32 / 6.06 / 5.47 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 5.3 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **1.59 / 2.09** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 4.17 / 1.69 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 90% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 59% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): Knight|press|lo +0.24, Knight|quiet|lo +0.20, IceWizard|press|lo +0.17, Skeletons|quiet|lo +0.17, Tesla|quiet|lo +0.15, Log|quiet|lo +0.14. Biggest deficits: Tornado|press|hi -0.32, Knight|press|hi -0.31, IceWizard|press|hi -0.29, Skeletons|press|hi -0.29, Tesla|press|hi -0.25.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| rlarm_gae_cue_u250_u0130_grafted | 76 | [0.35, 0.45, 0.55] | False | 53% | 3.2 | 64% | 6.3 / 6.1 / 5.5 | 3.68 |

Reading: total plays/min are the same as pros (9.5 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.88; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Cheap low-elixir plays above the median (3.5/min at < 5 elixir)** | 26/36 (72%) | 11/40 (28%) | L-W 44.7% [22.4%, 61.2%]; WR with/without 30% / 74% | - | 16.5 | (a) |
| 2 | **Low elixir when a push arrives (< 4)** | 109/155 eps (70%) | 59/108 eps (55%) | MH P(lost episode) 15.6% [3.5%, 26.7%] | 14.3 | 12.6 | (a) |
| 3 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 68/103 X-Bows | 73/135 | MH dealt20 -637 HP [-1138, -180]; MH dud rate 9.9% [-4.0%, 24.7%] | 14.2 (90k HP x 0.158 crowns/1k HP) | 9.9 | (a) |
| 4 | **Slow first answer (> 2 s)** | 59/155 eps (38%) | 56/108 eps (52%) | MH P(lost episode) 13.5% [1.7%, 26.1%] | 4.6 | 4.0 | (a) |
| 5 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 3/36 (8%) | n/a (end state of losses) | by ending: OT end 1, OT sudden death 2 | 3 | 2.5 | (a) |
| 6 | **Lethal Rocket window not used (>= 3 s)** | 0/36 (0%) | 6/40 (15%) | L-W -15.0% [-29.1%, -2.5%]; WR with/without 100% / 49% | - | 0.0 | (c) |
| 7 | **Air unit in the push** | 32/155 eps (21%) | 36/108 eps (33%) | MH P(lost episode) 15.4% [-10.2%, 40.0%] | 7.3 | - | (b) |
| 8 | **X-Bow committed <= 10 s before a push** | 26/155 eps (17%) | 17/108 eps (16%) | MH P(lost episode) -13.3% [-30.5%, 0.9%] | 1.8 | - | (b) |
| 9 | **Offence spending before a push (>= 3 elixir)** | 23/155 eps (15%) | 15/108 eps (14%) | MH P(lost episode) -13.3% [-28.6%, 4.9%] | 1.5 | - | (b) |
| 10 | **Opponent public elixir lead >= 3 at push start** | 39/155 eps (25%) | 22/108 eps (20%) | MH P(lost episode) 5.8% [-8.5%, 22.7%] | 6.8 | - | (b) |
| 11 | **Tornado as the first answer** | 9/155 eps (6%) | 2/108 eps (2%) | MH P(lost episode) 17.7% [-5.9%, 40.9%] | 0.0 | - | (b) |
| 12 | **Heavy spending in the 10 s before a push (>= 7)** | 82/155 eps (53%) | 57/108 eps (53%) | MH P(lost episode) -9.6% [-21.3%, 2.7%] | 9.2 | - | (b) |
| 13 | **Gate below threshold >= 3 s while threatened** | 38/155 eps (25%) | 41/108 eps (38%) | MH P(lost episode) -1.7% [-14.8%, 11.3%] | 1.5 | - | (b) |
| 14 | **Sat at full elixir just before a push** | 9/155 eps (6%) | 7/108 eps (6%) | MH P(lost episode) 10.8% [-20.9%, 40.9%] | 0.0 | - | (b) |
| 15 | **Elixir wasted at the cap >= 5 in a match** | 8/36 (22%) | 12/40 (30%) | L-W -7.8% [-26.4%, 12.1%]; WR with/without 60% / 50% | - | - | (b) |
| 16 | **Gate freeze >= 10 s at >= 9.5 elixir** | 5/36 (14%) | 8/40 (20%) | L-W -6.1% [-22.8%, 11.5%]; WR with/without 62% / 51% | - | - | (b) |
| 17 | **Opponent archetype: Golem** | 3/36 (8%) | 5/40 (12%) | L-W -4.2% [-18.8%, 11.1%]; WR with/without 62% / 51% | - | - | (b) |
| 18 | **Opponent archetype: Lava Hound** | 1/36 (3%) | 0/40 (0%) | L-W 2.8% [-6.3%, 14.2%]; WR with/without 0% / 53% | - | - | (b) |
| 19 | **Opponent archetype: Balloon** | 3/36 (8%) | 0/40 (0%) | L-W 8.3% [-2.0%, 21.8%]; WR with/without 0% / 55% | - | - | (b) |
| 20 | **Log or Tornado on nothing (>= 2 in a match)** | 3/36 (8%) | 5/40 (12%) | L-W -4.2% [-18.8%, 11.1%]; WR with/without 62% / 51% | - | - | (b) |
| 21 | **Unconfirmed play (>= 1 in a match)** | 27/36 (75%) | 27/40 (68%) | L-W 7.5% [-12.8%, 26.6%]; WR with/without 50% / 59% | - | - | (b) |
| 22 | **Placement error >= 1 tile** | 1/36 (3%) | 0/40 (0%) | L-W 2.8% [-6.3%, 14.2%]; WR with/without 0% / 53% | - | - | (b) |
| 23 | **CPU starvation (>= 3 warnings)** | 4/36 (11%) | 6/40 (15%) | L-W -3.9% [-19.5%, 12.4%]; WR with/without 60% / 52% | - | - | (b) |
| 24 | **Rocket held >= 90% of the match** | 20/36 (56%) | 26/40 (65%) | L-W -9.4% [-30.0%, 12.1%]; WR with/without 57% / 47% | - | - | (b) |
| 25 | **Hero Ice Wizard ability pressed >= 3 times** | 8/36 (22%) | 8/40 (20%) | L-W 2.2% [-15.9%, 20.7%]; WR with/without 50% / 53% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Cheap low-elixir plays above the median (3.5/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 4.55 vs W 2.84/min (diff 1.71 [0.97, 2.46]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**2. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 38% / 25%; tower-fall MH difference 8.5% [-0.1%, 17.3%]; informative matches 41
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only 16.1% [-6.7%, 39.3%] (n=106); pushes >= 13 elixir -4.6% [-27.9%, 19.3%] (n=61); no air 13.0% [-0.5%, 25.5%] (n=195); R1e n/a [n/a, n/a] (n=0); stack2k + towerref_w2 15.6% [3.5%, 26.7%] (n=263)
  * only 2% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_134527 t878-1445

**3. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 59% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by n/a elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.158 crowns per 1,000 HP, 76 matches); informative matches 45
  * all locked X-Bows 32% dud, mean 1466 HP (n=238); in losses 47% dud, mean 1172 HP (n=103) vs wins 21% dud, mean 1690 HP (n=135)
  * enemy push on my half at placement 46% dud, mean 1206 HP (n=24) vs not 30% dud, mean 1495 HP (n=214)
  * < 1 elixir left after placing 43% dud, mean 1496 HP (n=30) vs >= 1 30% dud, mean 1461 HP (n=208)
  * by phase: 1x 22% dud, mean 1906 HP (n=92); 2x 37% dud, mean 1252 HP (n=93); OT 42% dud, mean 1077 HP (n=53)
  * a hard counter seen near it before it died 43% dud, mean 1291 HP (n=90); X-Bow life median 15.9 s
  * examples: 20261017_134527 t1553-1953 opp_el 9.4 dealt 51; 20261017_134527 t2685-3085 opp_el 8.7 dealt 0; 20261017_134527 t3333-3733 opp_el 10.0 dealt 0

**4. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 36% / 32%; tower-fall MH difference 4.0% [-5.0%, 13.9%]; informative matches 46
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 22% answered <= 2 s vs 23% slower; push 10-13 elixir: lost 27% answered <= 2 s vs 41% slower; push 13-+ elixir: lost 56% answered <= 2 s vs 60% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_134527 t878-1445

**5. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 48% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261017_145920 (OT end, enemy tower 43 HP); 20261017_182814 (OT sudden death, enemy tower 391 HP); 20261017_184855 (OT sudden death, enemy tower 282 HP)

**6. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 20: rocketed 8, Rocket elsewhere 2; OT windows 6 (rocketed 6)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**7. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 50% / 28%; tower-fall MH difference 10.8% [-5.3%, 27.9%]; informative matches 17
  * examples: 20261017_133313 t639-1230; 20261017_133313 t1747-2345; 20261017_151038 t311-884

**8. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 23% / 35%; tower-fall MH difference 4.2% [-5.8%, 15.6%]; informative matches 26
  * examples: 20261017_144040 t2795-2994; 20261017_151038 t311-884; 20261017_163506 t1374-1871

**9. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 18% / 36%; tower-fall MH difference 4.1% [-7.5%, 19.3%]; informative matches 26
  * examples: 20261017_144040 t2795-2994; 20261017_151038 t311-884; 20261017_163506 t1374-1871

**10. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 31% / 34%; tower-fall MH difference 11.2% [-1.3%, 24.2%]; informative matches 31
  * examples: 20261017_141825 t819-1179; 20261017_144040 t2795-2994; 20261017_145920 t825-1172

**11. Tornado as the first answer** -- the first play after threat start is Tornado
  * pooled lost-episode rate with/without: 55% / 33%; tower-fall MH difference -14.6% [-24.5%, -6.3%]; informative matches 10
  * examples: 20261017_144040 t2011-2388; 20261017_185911 t4627-4994; 20261017_194723 t3729-4295

**12. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 25% / 43%; tower-fall MH difference 6.6% [-1.8%, 16.4%]; informative matches 44
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261017_134527 t878-1445; 20261017_142523 t3199-3798; 20261017_144040 t1060-1421

**13. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 24% / 38%; tower-fall MH difference 1.9% [-5.7%, 10.8%]; informative matches 45
  * examples: 20261017_133313 t639-1230; 20261017_134527 t878-1445; 20261017_134527 t1115-1445

**14. Sat at full elixir just before a push** -- >= 3 s at >= 9.9 elixir in the 15 s before threat start
  * pooled lost-episode rate with/without: 31% / 34%; tower-fall MH difference -2.1% [-17.8%, 15.2%]; informative matches 14
  * examples: 20261017_201510 t2832-3367; 20261017_202500 t512-1083; 20261017_203152 t3278-3781

**15. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261017_191430 longest stretch at the cap 51.1 s; 20261017_190905 longest stretch at the cap 23.1 s; 20261017_203152 longest stretch at the cap 3.1 s

**16. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261017_191430 freeze 51.1 s; 20261017_190905 freeze 24.1 s; 20261017_170616 freeze 14.8 s

**17. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**18. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**19. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**20. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 9% of 396; Tornadoes on nothing 8% of 84; Tornado centre on the enemy side 21% (pros 38%)

**21. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**22. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**23. CPU starvation (>= 3 warnings)** -- cpu_starved events

**24. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**25. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 3 losses: Rocket in hand 76% of the time; Rocket in hand AND >= 6 elixir 2%; matches that EVER had Rocket + 6 elixir in those 20 s: 2/3; median of the max elixir reached 7.1; Rocket taps in the window 2.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 21 | 29% [14%, 50%] | 1 | 35% |
| Giant (incl. Goblin/Electro) | 10 | 40% [17%, 69%] | 0 | 25% |
| Golem | 8 | 62% [31%, 86%] | 1 | 34% |
| Ram/Bridge spam | 7 | 29% [8%, 64%] | 0 | 41% |
| X-Bow/Mortar | 7 | 100% [65%, 100%] | 0 | 0% |
| Spawners (Witch/huts) | 7 | 86% [49%, 97%] | 0 | 33% |
| Other/no clear wincon | 4 | 75% [30%, 95%] | 0 | 20% |
| Mega Knight | 3 | 67% [21%, 94%] | 1 | 43% |
| Graveyard | 3 | 100% [44%, 100%] | 0 | 25% |
| Balloon | 3 | 0% [0%, 56%] | 0 | 36% |
| Lava Hound | 1 | 0% [0%, 79%] | 1 | 67% |
| Bait | 1 | 100% [21%, 100%] | 0 | n/a |
| Royal Giant | 1 | 100% [21%, 100%] | 0 | 56% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 6.3 / 6.1 / 5.5 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 64% -> <= 45%; median elixir at push start 3.2 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 33% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 3 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 8% -> lower; lethal windows rocketed up; OT win rate 48% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

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

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.01, 2x 2.02, OT 2.12 (constants used: 1 / 2 / 2).
* Plays tapped before the previous play confirmed: 31 in 76 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.67 vs W 1.27.

