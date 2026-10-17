# Night 10-16 parity diagnosis: own Skeletons + own Tornado

Worker report (DONE_WITH_CONCERNS), saved by the lead from the worker's final message (subagents could not write this
file). Base T = the Tesla worker's in-flight harness (fights_inflight.py) + the lead's seed fix (fights_T.py); every patch
is a diff against T. Captured strict cohort, royalesim 0.1.35, K=8.

## 0. Dependence on in-flight shots (H1)
- (a) Before H1, 18 of the 28 imperfect own Skeletons / Tornado fights had a shot in flight at t0; in 24/24 such shots the target
  took the hit live and never in the SIM.
- (a) The worker's independent version of the same fix: overall 0.877 -> 0.907; T: 0.877 -> 0.913 [0.887, 0.936], Skeletons
  0.817 -> 0.864, Tornado 0.831 -> 0.884.
- (a) Two H1 gaps: the Princess's 5 arrow rows injected as 5 full SIM shots (221202@2961 kills a 276-hp IW that lives at 31 live;
  no captured score change; the trim `volley_trim.patch` broke opp Elite Archer hero 213647@2273 -> REJECTED); shots at proxy
  children skipped (23 shots / 22 strict fights) -> `proxy_target.patch` (= knight H6, landed).

## 1. Failing fights under H1 (Skeletons 16/78, Tornado 3/21)
| fight | class | evidence |
|---|---|---|
| Skel 165635@403 | U | own skeleton dies 445 live vs 463 SIM; which Minion Horde member picks which skeleton differs; ceiling 0.464, aK 0.375 |
| Skel 171357@340 | U | ceiling 0.464, aK 0.625 |
| Skel 213647@3157 | U | ceiling 0.25 |
| Skel 214908@432 | U | ceiling 0.179 |
| Skel 170249@2047 | unresolved | Bats pick different skeletons; ceiling 0.464, aK 0 (noise never reproduces live) |
| Skel 165921@2630 | S upstream | (a) Evo Musketeer snipe target: fixed in 0.1.36 by targeting.SNIPE_TOWER_FILTER (reverting only that law on 0.1.36 brings back the failure) |
| Skel 214002@1724 | S upstream | (a) fixed in 0.1.36 by status.HIT_STUN_SPAN (same law-revert test) |
| Skel 170937@2551 | S | (a) live Goblin Machine rocket lands among all 3 Skeletons at 2575, all die at 2591; the SIM never fires it (= Tesla S1); a Giant also snapped 565 mt |
| Skel 170937@4024 | S + H/S | (a) third death = Goblin Machine rocket (4080 live vs 4138 SIM); Goblin Machine snapped 289 mt; clamping the snap gives 4040 / 4068 (live 4040 / 4070) |
| Skel 171357@2392 | H2 | (a) Hero Goblins flag (4090 hp, Goblins card id) set the card's top max_hp, every later 323-hp Goblins play dropped as children (= knight H1, landed) |
| Skel 214908@2843 | H | (a) an Evo Tesla pulse already on the board at t0 (fx row, 350 ms left); the Prince gets Tesla_EV1_WithDamage at 2844 and takes 237 live; the SIM never creates the pulse -- seeding live area effects at t0 not built |
| Skel 220124@2480 | S/H | (a) a princess arrow hits the Evo Knight for 158 live but 63 SIM (0.4x: the SIM still has it fortified); t0 flag status_unset:Knight_Fortify_EV1 |
| Skel 220623@4768 | H1 gap | (a) arrow at a Witch skeleton not injected (proxy); with proxy_target SIM [4862 x3] vs live [4850, 4862, 4862] -- still 2 ticks over tolerance |
| Skel 214220@1658 | unresolved, S cand. (b) | Bandit path diverges at t0+8 (0.53 tiles); Rascals snapped 352 mt at setup |
| Skel 214535@1508 | unresolved (b) | Tombstone death-spawned skeletons (placement, timing) |
| Skel 221839@1889 | unresolved | Skeleton Army swarm vs our 3 Skeletons; ceiling 1.0, aK 0; a swarm member snapped 380 mt; clamp raises aK 0 -> 0.75, a0 still fails |
| Torn 165635@459 | H scoring | (a) our Tornado's crown % sits in its BUFF (30%), not the card row -> fights.py used 100%; its tower threshold became 0.8 x 134; live the 40-hp Tornado tick and the X-Bow's 98 land in separate frame gaps, in the SIM together (139) credited as Tornado tower damage -> `dot_crown.patch` |
| Torn 215432@1411 | S upstream | (a) status.ATTRACT_ONSET fixes it in 0.1.36 -- the same law breaks 221202@394 -> +1 / -1 on our Tornado |
| Torn 221202@3294 | U | ceiling 0.464 |

## 2. Clusters (Skeletons + Tornado)
in-flight shots 4 + 1 (fixed by H1); U 5; upstream 0.1.36 laws 3; Goblin Machine rocket 2; bridge snap present in 4; one each:
H2, Evo Tesla area at t0, Evo Knight fortify, proxy target, Tornado crown %; unresolved 4.

## 3. Fixes measured on T (captured strict, common fights)
| patch | mechanism | overall | own Skel | own Tornado | regressions |
|---|---|---|---|---|---|
| hero_summon_top.patch | top max_hp over the card's own units only (106 opp Goblins bodies dropped in 5 of the 55 projectile-row logs) | 0.913 -> 0.921 [0.900, 0.939] | 0.864 -> 0.878 | - | a0 6 F->T, 0 T->F; 2 fights left strict (NO_HERO); uncaptured 0.893 -> 0.897 -- superseded by knight H1 (landed) |
| proxy_target.patch | proxy children allowed as shot targets | 0.913 -> 0.914 | 0.864 -> 0.868 | - | 0 -- = knight H6 (landed) |
| dot_crown.patch | crown % read from the buff for damage-over-time spells (Poison, Tornado, Earthquake) | 0.913 -> 0.914 | - | 0.884 -> 0.934 | 0; uncaptured 2 F->T, 0 regressions |
| all three (fights_TALL.py) | | 0.913 -> 0.923 [0.903, 0.940]; full n 1004 0.922 | 0.882 [0.801, 0.942] | 0.930 (n 20) | a0 8 F->T, 0 T->F; 37 parity tests pass |
| snap_clamp.patch | clamp a snapped body into its nearest passable half-cell | 0.913 -> 0.913 | +0.009 | - | opp Skeleton Army -0.03 -- NOT recommended (knight H3 landed instead) |

**S candidate: bridge passability (b, untested in the engine).** Live ground troops on the river band stand outside the SIM's
bridge cells in 236 of 3,740 samples (a). SIM passable x [2500, 4500) and [13500, 15500); live bodies as far out as ~2000-5000
and 12500-16000. Engine grid `passable_half_cells` (file:line not pinned). Fights with a snapped body agree 0.741 vs 0.873
overall, 0.453 vs 0.825 for Skeletons (a, correlation not cause). Fixture 170937@2551: a Giant at (4773, 16537) live.

## 4. Answers
- "SIM ahead +0.2-0.3 tiles": (a) at the first walking frame the SIM is exactly one tick ahead (~90 mt for Skeletons) in 57 of 131
  Skeletons bodies, 0 in 74; Knights 18 of 43 vs 25 -> (c) not Skeleton-specific (the 10-13 "Knight not" contradicted on captured
  logs); (c) not per-member stagger / formation (birth positions match to 0 mt). Cause: the harness creates the unit on the
  EARLIER of the two possible ticks in a 2-tick frame gap = U (the ceiling draws it). The reader removes it by capturing each
  body's spawn tick or deploy timer at first sighting.
- "Hit timing" class on captured logs: (c) does not survive -- each deterministic case had a concrete earlier divergence
  (in-flight dart, missing Goblins, upstream law, pulse area, Evo Knight fortify); (a) where phase-3 rows exist the killer's
  attack progress at acquisition is the same live and SIM.
- Skeletons' own bodies or others: (a) the first divergence is on ANOTHER body in 14 of the 16 Skeletons failures.

## 5. Gain estimate for own Skeletons (b; now 0.882, ceiling 0.913)
two upstream laws ~+0.03 (~0.91); Goblin Machine rocket ~+0.03 (~0.94); Evo Tesla area at t0 + Evo Knight fortify ~+0.03
(~0.97); ~5 U + 4 unresolved remain. n 78 -> CI ~+-0.07, so a lower bound >= 0.95 needs more captured matches.

## Concerns
Old-seed comparisons are clean for shot injection (no event-list change); H2 changes events, so it was run only on the
seed-fixed base. Ungated H1 on the 23 uncaptured projectile-row logs: perturbed score ~flat (0.882 -> 0.884), own Skeletons
-0.006, own Tesla -0.013 -- perturbation may redraw a swing that just fired (b); T vs base on that set (0.882 -> 0.893) includes
the reseed, not separable.

## Paths (diag_night/skel/)
patches vs T: hero_summon_top.patch, proxy_target.patch, dot_crown.patch, snap_clamp.patch (not recommended), volley_trim.patch
(rejected), seed_on_inflight.patch; files fights_T/TH2/TP/TC/TALL/TS/TA.py; out/ (cmp*.txt, CEILING_strict_T.txt,
CEILING_strict_TALL.txt, fails_under_H1.txt, fails_under_TALL.txt), law_flip_out.txt, dossier35.txt, dossierP.txt; scripts
law_flip.py, firststep*.py, bridge.py, count_dropped*.py, test_h2.py. Pod B: /workspace/results/skel_{T35,TA35,TH2_35,TP35,
TC35,TS35,TALL35,dump*,proj35*}.
