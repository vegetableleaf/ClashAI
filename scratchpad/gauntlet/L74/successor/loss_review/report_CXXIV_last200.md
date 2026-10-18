# Live loss review (L74, standing) -- generated 2026-10-17 20:53

Ledger: 200 logs analysed (analyzed.txt); rows in matches.jsonl; tool review.py + report.py (+ pro_baseline.py, run once). Valid matches (result known, >= 5 plays, not dry-run): 200. **Factor population = R-lineage** (logs >= 20261004_205129: R1e and later) with board state: **200 matches, 102 W / 98 L / 0 D**; 728 threat episodes; 761 confirmed X-Bows.

**Result rule:** the ladder line in L70/live/overnight.out after the log's 'played' line; else the ladder_nav 'outcome' event within [end-20 s, end+300 s]; else tower-derived (crowns; equal crowns -> lower minimum tower HP loses). Sources: {'ladder': 200}. Agreement where both exist: nav vs ladder 200/200; tower-derived vs ladder 199/200 (error 0.5%, always toward WIN: the final blow is never in the log). Trophy deltas exist for 0 matches only -> not used.

## Summary

* **The economy is the main loss mechanism.** The bot meets 65% of pushes with < 4 elixir (pros 24%); median 3.0 vs pros 6.0. Within the same match, a push met with < 4 elixir is lost 14.0% [5.0%, 21.1%] more often (absolute); pros show no such penalty. Cause: cheap cards played at < 5 elixir 2-3x as often as pros (same total play rate).
* **9 of 98 losses ended with the enemy tower within one Rocket**; Rocket was in hand 78% of the final 20 s but in hand AND affordable 7%: the same economy problem.
* Other measured factors: locked X-Bows into a full opponent elixir bar, air in pushes, Golem/Lava/Balloon matchups, gate freezes at full elixir.
* **Contradicted** as loss causes on this data: Gate below threshold >= 3 s while threatened; Elixir wasted at the cap >= 5 in a match; Gate freeze >= 10 s at >= 9.5 elixir; Lethal Rocket window not used (>= 3 s); CPU starvation (>= 3 warnings).
* Top fix (P1, section 5): measure then remove the live-only early-spending shift (extrapolated gate input) or recalibrate the gate per elixir bucket on pro data.

## 1. Win/loss per checkpoint family (all valid matches)

| family | matches | W-L-D | win rate [95% CI] | with board state | first log | last log |
|---|---|---|---|---|---|---|
| rlarm_gae_u0250_grafted | 200 | 102-98-0 | 51% [44%, 58%] | 200 | 20261017_004246 | 20261017_132435 |

Older families (gen_s0, league1c, rseries_r1) mostly lack board state in their logs (no decision/frame events), so the factor analysis uses the R-lineage.

## 2. How the R-lineage loses

* 98 losses. The bot scored **0 crowns in 82 (84%)**; three-crowned in 10 (10%; 2 of them vs Golem). Score lines (bot-opp): 0-1 49, 0-2 14, 0-0 11, 1-2 10, 0-3 8, 1-1 4, 1-3 2.
* Opponent's first crown came in: 1x 44, OT 18, 2x 15, none 11, bot first 10. 93/200 matches reach overtime (46%); OT win rate 61%.
* Win rate by crowns conceded: 0: 90% (n=105), 1: 13% (n=61), 2: 0% (n=24), 3: 0% (n=10). Value of the first conceded crown (used for 'wins at stake'): **0.76**. Value of the first crown TAKEN: 0.74.
* Tower HP per match (taken / dealt), losses vs wins: 1x: L 5140 / 2356 vs W 2003 / 2653; 2x: L 2976 / 1156 vs W 966 / 2489; OT: L 1714 / 1131 vs W 742 / 1836

## 3. The economy, measured against pros (same definitions)

| measure | bot (R-lineage live) | pros (2,244 icebow sides) |
|---|---|---|
| own elixir when a push arrives (median) | **3.0** (losses 2.5, wins 3.5) | **6.0** |
| share of pushes met with < 4 elixir | **65%** | 24% |
| lost-episode rate at < 4 / >= 4 elixir | **43% / 27%** | 24% / 24% |
| lost-episode rate overall | 38% | 24% |
| first play within 2 s of a push | 58% (taps) | 64% (deploys) |
| >= 7 elixir spent in the 10 s before a push | 54% | 47% |
| elixir at play 1x / 2x / OT (bot = raw at TAP; +0.46 / +0.93 at deploy) | 6.11 / 5.55 / 5.44 | 7.61 / 7.01 / 6.64 |
| elixir wasted at the cap per match | 3.3 | 10.2 |
| plays/min with < 5 elixir: quiet / pressured | **1.47 / 2.58** | 0.89 / 1.53 |
| plays/min with >= 5 elixir: quiet / pressured | 4.32 / 1.54 | 4.29 / 3.55 |
| Rocket in hand (share of time) | 91% | 83% |
| locked X-Bows placed with opponent public elixir >= 7 | 56% | 46% |

Biggest per-card excess over pros (plays/min, card|context|elixir<5=lo): IceWizard|press|lo +0.25, Knight|press|lo +0.25, Log|press|lo +0.21, Skeletons|press|lo +0.19, Xbow|quiet|hi +0.19, IceWizard|quiet|lo +0.15. Biggest deficits: Knight|press|hi -0.36, Tesla|press|hi -0.33, IceWizard|press|hi -0.29, Tornado|press|hi -0.28, Skeletons|press|hi -0.27.

Per checkpoint family (the pattern is not one checkpoint's quirk):

| family | matches | gate tau (1x/2x/OT) | anti-leak | win rate | elixir at push start (median) | pushes met < 4 | tap elixir 1x / 2x / OT | plays/min at < 5 elixir |
|---|---|---|---|---|---|---|---|---|
| rlarm_gae_u0250_grafted | 200 | [0.35, 0.45, 0.55] | False | 51% | 3.0 | 65% | 6.1 / 5.5 / 5.4 | 4.05 |

Reading: total plays/min are the same as pros (9.9 vs 10.3), but the bot plays its cheap cards EARLY -- at < 5 elixir -- two to three times as often, so it never holds a bank: it meets 70% of pushes with < 4 elixir and almost never has the 6 elixir for a Rocket. Pros sit at full elixir far more (they waste more), so 'elixir leak' is not what separates the bot from pros. The push-Rocket worker measured the same model at elixir 5.2 at big-push start in SIM vs 3.0-3.6 live, and its follow-up A found the live 26-tick extrapolation raises the gate's p_play by a median +0.05..+0.09 relative to the training input path (live_path_test.out) -- a live-only push toward earlier plays. Which of the two (extrapolation, or live opponents' pressure) drives the live trickle is UNTESTED (proposal P1 measures it).

Natural experiment in the family table (b, confounded by checkpoint): the families that run tau_phase (.35/.45/.55) tap at 1-2 elixir MORE in 2x/OT than R1e (flat .35), while 1x (tau .35 in both) barely moves, and they make fewer low-elixir plays. The gate threshold sets the bank; the gate decision is the lever for P1.

## 4. Ranked loss factors

Episode rows: MH difference WITHIN matches (opponent and checkpoint held fixed), CI = match-cluster bootstrap; 'lost episode' = my towers lose >= 1000 HP or a tower falls. Wins at stake are associational CEILINGS (episode rows: tower-fall difference x episodes x 0.76; match rows: (WR without - WR with) x matches with). Labels: **(a) measured** = behaviour measured and its link to losing has a CI excluding 0; **(b) plausible-untested** = measured behaviour, link not established; **(c) contradicted** = the CI excludes 0 the other way (the claimed cause goes with winning or with fewer lost episodes). Ranked by wins at stake; (b)/(c) rows carry no stake.

| rank | factor | in losses | in wins | effect [95% CI] | crowns at stake | wins at stake | label |
|---|---|---|---|---|---|---|---|
| 1 | **Cheap low-elixir plays above the median (3.9/min at < 5 elixir)** | 74/98 (76%) | 25/102 (25%) | L-W 51.0% [37.9%, 61.4%]; WR with/without 25% / 76% | - | 50.5 | (a) |
| 2 | **Unconfirmed play (>= 1 in a match)** | 79/98 (81%) | 57/102 (56%) | L-W 24.7% [11.9%, 36.4%]; WR with/without 42% / 70% | - | 38.6 | (a) |
| 3 | **Low elixir when a push arrives (< 4)** | 263/380 eps (69%) | 208/348 eps (60%) | MH P(lost episode) 14.0% [5.0%, 21.1%] | 45.7 | 34.9 | (a) |
| 4 | **Air unit in the push** | 156/380 eps (41%) | 124/348 eps (36%) | MH P(lost episode) 12.3% [2.4%, 22.1%] | 31.5 | 24.1 | (a) |
| 5 | **Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** | 136/250 X-Bows | 197/348 | MH dealt20 -278 HP [-589, -17]; MH dud rate 7.9% [-1.9%, 17.6%] | 14.1 (93k HP x 0.152 crowns/1k HP) | 10.5 | (a) |
| 6 | **Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** | 9/98 (9%) | n/a (end state of losses) | by ending: regulation end (Rocket -> tie -> OT) 2, OT sudden death 5, OT end 2 | 9 | 7.2 | (a) |
| 7 | **Tornado as the first answer** | 39/380 eps (10%) | 15/348 eps (4%) | MH P(lost episode) 24.3% [7.1%, 38.0%] | 2.6 | 2.0 | (a) |
| 8 | **Gate below threshold >= 3 s while threatened** | 73/380 eps (19%) | 124/348 eps (36%) | MH P(lost episode) -11.2% [-19.7%, -3.5%] | 0.0 | 0.0 | (c) |
| 9 | **Elixir wasted at the cap >= 5 in a match** | 7/98 (7%) | 29/102 (28%) | L-W -21.3% [-31.4%, -10.9%]; WR with/without 81% / 45% | - | 0.0 | (c) |
| 10 | **Gate freeze >= 10 s at >= 9.5 elixir** | 2/98 (2%) | 9/102 (9%) | L-W -6.8% [-14.0%, -0.2%]; WR with/without 82% / 49% | - | 0.0 | (c) |
| 11 | **Lethal Rocket window not used (>= 3 s)** | 1/98 (1%) | 10/102 (10%) | L-W -8.8% [-16.1%, -2.5%]; WR with/without 91% / 49% | - | 0.0 | (c) |
| 12 | **CPU starvation (>= 3 warnings)** | 18/98 (18%) | 33/102 (32%) | L-W -14.0% [-25.5%, -1.9%]; WR with/without 65% / 46% | - | 0.0 | (c) |
| 13 | **X-Bow committed <= 10 s before a push** | 59/380 eps (16%) | 67/348 eps (19%) | MH P(lost episode) -4.9% [-14.0%, 4.2%] | 0.0 | - | (b) |
| 14 | **Offence spending before a push (>= 3 elixir)** | 68/380 eps (18%) | 65/348 eps (19%) | MH P(lost episode) 1.7% [-7.7%, 11.0%] | 0.3 | - | (b) |
| 15 | **Opponent public elixir lead >= 3 at push start** | 123/380 eps (32%) | 80/348 eps (23%) | MH P(lost episode) 0.5% [-10.6%, 10.7%] | 4.3 | - | (b) |
| 16 | **Slow first answer (> 2 s)** | 141/380 eps (37%) | 166/348 eps (48%) | MH P(lost episode) 3.3% [-4.0%, 10.1%] | 1.8 | - | (b) |
| 17 | **Heavy spending in the 10 s before a push (>= 7)** | 185/380 eps (49%) | 207/348 eps (59%) | MH P(lost episode) -3.0% [-11.0%, 4.5%] | 0.0 | - | (b) |
| 18 | **Sat at full elixir just before a push** | 7/380 eps (2%) | 16/348 eps (5%) | MH P(lost episode) -6.5% [-19.5%, 8.3%] | 0.0 | - | (b) |
| 19 | **Opponent archetype: Golem** | 11/98 (11%) | 5/102 (5%) | L-W 6.3% [-1.4%, 14.6%]; WR with/without 31% / 53% | - | - | (b) |
| 20 | **Opponent archetype: Lava Hound** | 5/98 (5%) | 3/102 (3%) | L-W 2.2% [-3.9%, 8.7%]; WR with/without 38% / 52% | - | - | (b) |
| 21 | **Opponent archetype: Balloon** | 6/98 (6%) | 6/102 (6%) | L-W 0.2% [-6.9%, 7.6%]; WR with/without 50% / 51% | - | - | (b) |
| 22 | **Log or Tornado on nothing (>= 2 in a match)** | 19/98 (19%) | 13/102 (13%) | L-W 6.6% [-3.6%, 16.9%]; WR with/without 41% / 53% | - | - | (b) |
| 23 | **Placement error >= 1 tile** | 0/98 (0%) | 2/102 (2%) | L-W -2.0% [-6.9%, 2.1%]; WR with/without 100% / 51% | - | - | (b) |
| 24 | **Rocket held >= 90% of the match** | 65/98 (66%) | 61/102 (60%) | L-W 6.5% [-6.8%, 19.5%]; WR with/without 48% / 55% | - | - | (b) |
| 25 | **Hero Ice Wizard ability pressed >= 3 times** | 13/98 (13%) | 18/102 (18%) | L-W -4.4% [-14.4%, 5.8%]; WR with/without 58% / 50% | - | - | (b) |

Rows overlap: 'low elixir when a push arrives', 'cheap low-elixir plays', 'one Rocket short' and 'offence spending before a push' are views of ONE mechanism (the spending economy, section 3); 'elixir wasted' and 'gate freeze' are one mechanism (W4). Do not add their stakes.

### 4a. Factor details (examples = log timestamp + tick range in L68/live_reader/live_play_<ts>.jsonl)

**1. Cheap low-elixir plays above the median (3.9/min at < 5 elixir)** -- confirmed plays tapped at < 5 elixir per minute
  * mean per match L 5.37 vs W 2.92/min (diff 2.45 [1.96, 2.94]); pros 2.41/min
  * the match-level link is weak because the whole lineage trickles (section 3); the episode-level cost is the 'low elixir when a push arrives' row

**2. Unconfirmed play (>= 1 in a match)** -- a tapped play the reader never confirmed

**3. Low elixir when a push arrives (< 4)** -- own elixir < 4 at threat-episode start
  * pooled lost-episode rate with/without: 43% / 27%; tower-fall MH difference 9.7% [4.4%, 15.0%]; informative matches 111
  * pros (same definition, pro_baseline.json): 24% of pro episodes start < 4 and their lost rate does not depend on it (24% vs 23% at 4-7)
  * robustness, MH lost-episode difference in subsets: 1x only -3.1% [-21.4%, 12.5%] (n=312); pushes >= 13 elixir 15.6% [-7.3%, 35.4%] (n=168); no air 19.6% [8.4%, 29.6%] (n=448); R1e n/a [n/a, n/a] (n=0); stack2k + towerref_w2 14.0% [5.0%, 21.1%] (n=728)
  * only 1% of pushes arrive after 10 s without a bot play (the bot is almost never banking when a push comes)
  * examples: 20261017_004246 t3470-3789; 20261017_004607 t694-995; 20261017_004607 t2961-3556

**4. Air unit in the push** -- an air unit among the threat bodies
  * pooled lost-episode rate with/without: 45% / 33%; tower-fall MH difference 11.3% [2.6%, 19.9%]; informative matches 61
  * examples: 20261017_004246 t3170-3769; 20261017_004246 t3470-3789; 20261017_004607 t2439-3031

**5. Locked X-Bow placed into a full opponent elixir bar (public counter >= 7)** -- enemy tower HP lost in the 20 s after a locked X-Bow, opponent estimate >= 7 vs < 7, within matches
  * share of locked X-Bows placed at >= 7: bot 56% vs pros 46% (pro dud rate 64% at >= 7 vs 53% at < 7; pro counter rebuilt from visible plays)
  * the live counter over-reads by n/a elixir on average (EVAL_ONLY truth, frame logs), so part of the >= 7 share is counter bias
  * HP -> crowns uses the fitted slope of crowns taken on HP dealt per match (0.152 crowns per 1,000 HP, 200 matches); informative matches 112
  * all locked X-Bows 33% dud, mean 1419 HP (n=598); in losses 43% dud, mean 1216 HP (n=250) vs wins 26% dud, mean 1565 HP (n=348)
  * enemy push on my half at placement 48% dud, mean 1080 HP (n=42) vs not 32% dud, mean 1444 HP (n=556)
  * < 1 elixir left after placing 41% dud, mean 1212 HP (n=81) vs >= 1 32% dud, mean 1451 HP (n=517)
  * by phase: 1x 22% dud, mean 1808 HP (n=228); 2x 40% dud, mean 1170 HP (n=239); OT 40% dud, mean 1195 HP (n=131)
  * a hard counter seen near it before it died 45% dud, mean 1094 HP (n=222); X-Bow life median 16.2 s
  * examples: 20261017_010804 t2640-3040 opp_el 9.0 dealt 171; 20261017_014323 t3222-3622 opp_el 7.9 dealt 40; 20261017_015149 t2459-2859 opp_el 10.0 dealt 0

**6. Lost while the enemy's lowest tower was within one Rocket (<= 497 HP) at the end** -- final enemy lowest-tower HP <= measured Rocket tower damage 497; see section 4b for elixir/Rocket availability
  * wins at stake = OT sudden death x1 + regulation end x OT win rate 61% + OT end x .5 (ceiling: needs 6 elixir + the Rocket on that tower in time)
  * examples: 20261017_004607 (regulation end (Rocket -> tie -> OT), enemy tower 269 HP); 20261017_014323 (OT sudden death, enemy tower 134 HP); 20261017_023527 (OT end, enemy tower 117 HP)

**7. Tornado as the first answer** -- the first play after threat start is Tornado
  * pooled lost-episode rate with/without: 67% / 35%; tower-fall MH difference 4.8% [-6.6%, 17.7%]; informative matches 42
  * examples: 20261017_004246 t2144-2742; 20261017_004246 t3470-3789; 20261017_015555 t3350-3677

**8. Gate below threshold >= 3 s while threatened** -- p_play <= its tau for >= 3 s with an affordable card before the first play
  * pooled lost-episode rate with/without: 24% / 43%; tower-fall MH difference -7.0% [-12.5%, -1.4%]; informative matches 96
  * examples: 20261017_004246 t2144-2742; 20261017_012441 t549-729; 20261017_022800 t647-1129

**9. Elixir wasted at the cap >= 5 in a match** -- sum over time at >= 9.9 elixir of the regen rate
  * pros waste 10.2 per match (55% of pro sides >= 5): banking is normal for this deck; the bot's waste comes from gate freezes (next row)
  * examples: 20261017_015149 longest stretch at the cap 16.1 s; 20261017_102208 longest stretch at the cap 5.8 s; 20261017_064045 longest stretch at the cap 5.8 s

**10. Gate freeze >= 10 s at >= 9.5 elixir** -- longest run of decisions with p_play < tau and no play at >= 9.5 elixir (decision logs)
  * W4 hazard_below_tau at >= 9 elixir (hbt9) targets exactly this and is being deployed
  * examples: 20261017_015149 freeze 17.5 s; 20261017_095049 freeze 10.0 s; 20261017_094727 freeze 9.8 s

**11. Lethal Rocket window not used (>= 3 s)** -- enemy princess <= 497 HP, Rocket in hand, >= 6 elixir for >= 3 s (or a Rocket tap), no Rocket on that tower
  * windows 40: rocketed 21, Rocket elsewhere 3; OT windows 18 (rocketed 18)
  * match-level association runs the other way because lethal windows happen when the bot is ahead; the real cost is the elixir-blocked end-state row

**12. CPU starvation (>= 3 warnings)** -- cpu_starved events

**13. X-Bow committed <= 10 s before a push** -- a confirmed X-Bow in the 10 s before threat start
  * pooled lost-episode rate with/without: 27% / 40%; tower-fall MH difference -2.9% [-9.4%, 4.2%]; informative matches 73
  * examples: 20261017_011120 t2768-3130; 20261017_015555 t2695-3053; 20261017_023527 t3719-4211

**14. Offence spending before a push (>= 3 elixir)** -- elixir on locked X-Bows or spells aimed past own y 18 in the 10 s before threat start
  * pooled lost-episode rate with/without: 32% / 39%; tower-fall MH difference 0.3% [-7.6%, 7.6%]; informative matches 76
  * examples: 20261017_010804 t1895-2310; 20261017_010804 t2894-3135; 20261017_015555 t687-881

**15. Opponent public elixir lead >= 3 at push start** -- opponent_elixir_estimate - own elixir >= 3
  * pooled lost-episode rate with/without: 38% / 37%; tower-fall MH difference 2.1% [-4.4%, 9.5%]; informative matches 96
  * examples: 20261017_004246 t3470-3789; 20261017_004607 t694-995; 20261017_010804 t2894-3135

**16. Slow first answer (> 2 s)** -- no play (tap) within 2 s of threat start
  * pooled lost-episode rate with/without: 37% / 38%; tower-fall MH difference 0.6% [-5.5%, 7.5%]; informative matches 120
  * pros (same definition, pro_baseline.json): pros answer within 2 s in 64%
  * by push size (pooled): push 7-10 elixir: lost 25% answered <= 2 s vs 26% slower; push 10-13 elixir: lost 34% answered <= 2 s vs 47% slower; push 13-+ elixir: lost 59% answered <= 2 s vs 63% slower. Slow answers are not worse at ANY size; the likely reading is that the bot waits on pushes its towers handle.
  * examples: 20261017_004246 t2144-2742; 20261017_004607 t2961-3556; 20261017_012441 t549-729

**17. Heavy spending in the 10 s before a push (>= 7)** -- confirmed card elixir in the 10 s before threat start >= 7
  * pooled lost-episode rate with/without: 30% / 46%; tower-fall MH difference -4.1% [-9.6%, 1.7%]; informative matches 122
  * pros (same definition, pro_baseline.json): pros 47% of episodes
  * examples: 20261017_004607 t694-995; 20261017_010804 t1895-2310; 20261017_010804 t2894-3135

**18. Sat at full elixir just before a push** -- >= 3 s at >= 9.9 elixir in the 15 s before threat start
  * pooled lost-episode rate with/without: 17% / 38%; tower-fall MH difference -7.4% [-16.4%, -1.3%]; informative matches 15
  * examples: 20261017_061002 t1892-2100; 20261017_062844 t931-1316

**19. Opponent archetype: Golem** -- primary class from public cards (live_eval.classify)

**20. Opponent archetype: Lava Hound** -- primary class from public cards (live_eval.classify)

**21. Opponent archetype: Balloon** -- primary class from public cards (live_eval.classify)

**22. Log or Tornado on nothing (>= 2 in a match)** -- Log with no enemy ground body in its path (no barrel in flight) or Tornado with no enemy within 5.5 tiles
  * Logs on nothing 9% of 1020; Tornadoes on nothing 15% of 381; Tornado centre on the enemy side 22% (pros 38%)

**23. Placement error >= 1 tile** -- any confirmed play with err_tiles >= 1

**24. Rocket held >= 90% of the match** -- Rocket in hand share of decisions >= .9 (pros 83% on average)

**25. Hero Ice Wizard ability pressed >= 3 times** -- ability events

### 4b. Why the finishing Rocket did not come (losses ending with the enemy tower <= 497 HP)

Last 20 s of those 9 losses: Rocket in hand 78% of the time; Rocket in hand AND >= 6 elixir 7%; matches that EVER had Rocket + 6 elixir in those 20 s: 5/9; median of the max elixir reached 6.3; Rocket taps in the window 8.
The card is there; the elixir is not. The owner's OT lethal-Rocket option only fires when Rocket is affordable, so on these end-states it can act only in the matches that reached 6 elixir; the economy fix (P1) is what makes the Rocket affordable.

### 4c. Win rate by opponent class (public cards; live_eval.classify)

| class | n | win rate [95% CI] | 3-crowned | lost-episode rate |
|---|---|---|---|---|
| Hog (incl. Royal Hogs) | 39 | 56% [41%, 71%] | 1 | 32% |
| Ram/Bridge spam | 22 | 50% [31%, 69%] | 0 | 29% |
| Spawners (Witch/huts) | 16 | 75% [51%, 90%] | 0 | 25% |
| Giant (incl. Goblin/Electro) | 16 | 38% [18%, 61%] | 0 | 34% |
| X-Bow/Mortar | 16 | 50% [28%, 72%] | 0 | 50% |
| Golem | 16 | 31% [14%, 56%] | 2 | 49% |
| Balloon | 12 | 50% [25%, 75%] | 1 | 39% |
| Other/no clear wincon | 12 | 83% [55%, 95%] | 0 | 25% |
| Mega Knight | 11 | 45% [21%, 72%] | 1 | 43% |
| Graveyard | 9 | 56% [27%, 81%] | 1 | 42% |
| Royal Giant | 8 | 25% [7%, 59%] | 1 | 48% |
| Lava Hound | 8 | 38% [14%, 69%] | 1 | 65% |
| Bait | 7 | 71% [36%, 92%] | 0 | 33% |
| P.E.K.K.A | 4 | 25% [5%, 70%] | 1 | 33% |
| Miner | 4 | 25% [5%, 70%] | 1 | 50% |

## 5. Fix proposals (learned, or decodings of the model's own learned quantities; nothing scripted; public information only)

Ranked by expected wins. Each is ONE experiment (one change at a time). Expected sizes are (b) estimates below the section-4 ceilings.

**P1. Bring live spending timing back to the model's own SIM/pro behaviour (economy).** Targets rows 'low elixir when a push arrives' and 'one Rocket short'. Step 1 (measurement, cheap, VM): SIM A/B of the live checkpoint with the live 26-tick extrapolation applied to its observations vs without, same seeds; if elixir at play / at push start drops toward live (live tap elixir 1x/2x/OT 6.1 / 5.5 / 5.4 vs SIM 7.1/6.6/6.7 measured by W4 on SIM v3 with the live config, HANDOFF), the extrapolation is the live cause. Step 2 (fix, decoding): evaluate the GATE on the non-extrapolated batch (the distribution it was trained and calibrated on) while card/cell keep the extrapolated batch; or (learned) fine-tune the gate on extrapolated training rows so it is calibrated on the live input. If step 1 shows no extrapolation effect, the cause is the live state mix and the fix is learned instead: per-elixir-bucket recalibration of the gate fitted on pro VAL rows (pros' measured play hazard by elixir and pressure, section 3), checked first offline (is the gate already calibrated per elixir bucket on pro rows?). Proof it worked (live, >= 100 matches): pushes met with < 4 elixir 65% -> <= 45%; median elixir at push start 3.0 -> >= 4; plays at < 5 elixir per min down >= 30%; lost-episode rate 38% -> <= 30%; Rocket+6 elixir in the last 20 s of close losses up; no rise in tower damage taken in 1x. Expected size (b): +3 to +6 pp win rate (about 1/3 of the low-elixir ceiling); risk: slower answers -- but slow answers are contradicted as a loss cause (row 'slow first answer').

**P2. OT sudden-death and end-game Rocket (pending option + P1).** 9 losses ended with the enemy tower within one Rocket. The owner's OT lethal-Rocket option (being deployed) converts only states where Rocket is affordable (section 4b). Proof: share of losses ending one Rocket short 9% -> lower; lethal windows rocketed up; OT win rate 61% up. Expected size (b): +1 to +2 pp alone, more on top of P1.

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

* Elixir regen measured from no-play intervals (elixir per 2.8 s): 1x 1.00, 2x 2.00, OT 2.22 (constants used: 1 / 2 / 2).
* Plays tapped before the previous play confirmed: 51 in 200 matches. Play-event elixir is the RAW elixir at the tap (checked 597/597).
* Hero Ice Wizard ability presses per match L 1.32 vs W 1.35.

