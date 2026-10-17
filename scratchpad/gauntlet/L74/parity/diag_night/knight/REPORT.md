# Night 10-16 parity diagnosis: own Knight / Knight evo + cross-card (opponent-anchored) failures

Worker report (DONE_WITH_CONCERNS), saved by the lead from the worker's final message (the worker could not write this
file). Setup: pod B, royalesim 0.1.35, fights.py 795b155, PARITY_BUFFS/ATTACKS exports, 27 captured matches, strict, K=8.
The worker's unpatched rerun = F35_BASE/_cap (993 fights, 158 unperturbed fails); laptop and pod replays agree on all 121
dossier fights. Scope: every failing fight except own Log / Tesla / Skeletons / Tornado = 102 fights.

## 1. Fixes measured (captured strict cohort, before -> after)

| fix | cause | overall normalised | fights fixed / broken | own Knight | regressions |
|---|---|---|---|---|---|
| H1 hero ability object | (a) the Hero Goblins ability object (3720/4090 hp) shares the goblins' card id; deployments()' max_hp "role-child" rule dropped every opp Hero Goblins play (20 plays on 10-16 logs, 12 captured; 44 strict fights had one in the window, 20 failed = 45% vs 16% overall) | 0.877 -> 0.886 | 6 / 0 (+11 new Hero Goblins fights, 9 agree) | 0.897 -> 0.909 | own Tornado 0.831 -> 0.822, opp Knight 0.952 -> 0.950 (an agreeing fight left strict via play_refused:NO_HERO); own Tesla 0.781 -> 0.780 (ceiling reseed only, see §4) |
| H2 child not made | (a) a Rascals boy set up mid-fight makes no girls; Spear Goblins left after their Goblin Giant died are not made. The patch only FLAGS these fights out of strict: an exclusion, not a fix | 0.877 -> 0.881 | 10 leave strict (5 fail, 5 agree) | 0.897 -> 0.907 | own Tesla evo 0.832 -> 0.822 |
| H3 snap point | a body in a SIM-impassable cell was moved to the cell CENTRE; patch: the nearest passable point | 0.877 -> 0.879 | 4 / 0 | unchanged | opp SkeletonArmy 0.820 -> 0.759 (133158@3830 agrees unperturbed, its perturbed agreement fell .875 -> .5); one agreeing IW fight left strict via NO_HERO |
| all three | | 0.877 [0.848, 0.901] -> 0.891 [0.872, 0.907]; raw 0.836 -> 0.848; fails 158 -> 145 | 10 / 0 | 0.897 -> 0.921 (raw 0.854 -> 0.875, n 67) | as above; also own IW hero 0.940 -> 0.974, own Log 0.768 -> 0.810, own Skeletons 0.817 -> 0.852 |

## 2. Own Knight / Knight evo: the 13 failing fights

| fight | class | first divergence, evidence |
|---|---|---|
| 214908@2959 | H1, fixed | Hero Goblins play at 3023 missing in the SIM; live goblins + hero object hit the Knight (a) |
| 214908@3324 | H1 partly; still fails | live Blowdart Goblin + 2 Musketeers hit the Knight from 3366, SIM Musketeer only; also a tower hit lost at t0 (b) |
| 171357@4572 | H2, excluded | 2 Rascal Girls never set up; live they deal 200/hit from t0+12 (a) |
| 215432@1279 | H3, fixed | failed only unperturbed (perturbed agreement already 1.0) |
| 175459@3198 | U (snap diagnosis CONTRADICTED) | tower acquires the Mini PEKKA at 3200 SIM / 3204 live inside a 4-tick frame gap; its arrow lands 2 ticks before the Mini PEKKA's 755 hit, so the SIM Mini PEKKA (92 hp) dies first; H3 cuts the snap error 380 -> 85 mt, fight still fails (c) |
| 170610@1948 (evo) | H, lost shot | a princess arrow in flight at t0 lands live at 1952 (E-Wiz 233 -> 75); the SIM's next arrow comes 16 ticks later; the SIM evo Knight detours to the live E-Wiz, reaches the tower 6 ticks late: tower dmg 697 vs 1020 (a, traced) |
| 214220@1332 | S candidate | Dark Prince at the river bank: SIM starts a river hop at t0+2 (101 mt/tick toward the seeded Tesla target); live walks 60/tick over the bridge to our Knight, kills it at 1522. n=1 (b). Hop = jump16402.rs / movement.JUMP_WATER_HOP (0.1.35). Test: Prince / Dark Prince hop starts live vs SIM on all ext logs |
| 165317@3238 | unresolved | live Golem pauses 4-6 ticks at 3242 with nothing in reach, SIM does not; Knight path 0.84 tiles off; at 3394 two opp Skeletons stay on the Knight live but switch to our fresh Skeletons in the SIM (a chain, cause of the pause unknown) |
| 221839@1528 | unresolved | charging Dark Prince, Knight path split at t0+152; SIM Prince engages the Knight (b) |
| 214908@4081, 221520@1253, 221839@3015 | U | perturbed replays reproduce live (0.25-0.5): hero Musketeer cast tick inside the frame gap; Minion Horde target split; Prince seeded already charged |
| 135037@4523 (evo) | H, n=1 | early log format without confirmations: evo Knight first seen 15 ticks into its deploy, SIM runs 14 ticks behind (a); the only late sighting outside Miners / Goblin Drills |

## 3. Cross-card ranking: the 95 in-scope fights still failing after all three fixes

| # | mechanism | fights | label, proposed fix |
|---|---|---|---|
| 1 | projectile in flight at t0 not set up (SIM setup has no projectiles) | 40 main; 48 with the signature (a body a t0 projectile targets loses >= 50 hp live but not in the SIM within 12 ticks) | H (a). Cohort: fights with 0 in-flight shots fail 10.9% (n 549), 1 shot 20.8% (322), 2 shots 24.7% (97), 3+ 28% (25) = ~50 excess failures; causal share (b). Fix: append cloned projectile records to the save's `projectiles` list, probed per source card like `form_record`. NOT BUILT |
| 2 | perturbed replays reproduce live | 26 | U: attack phase / cast / deploy tick inside the frame gap |
| 3 | same attackers, hit timing differs | 8 | unresolved |
| 4 | tower damage only | 6 | unresolved |
| 5 | body vanishes with no hp split | 5 | death spawns / reader |
| 6 | target choice, deploy point never paired, attacker missing, path split, spell hit set | <= 2 each | - |

## 4. Concerns
- Ceiling seed (b): the perturbation seed included the anchor's EVENT INDEX, so any harness change that adds an event
  reseeds every later fight in that match (own Tesla 214908@704 0.75 -> 0.625 with an identical unperturbed result).
  -> lead fixed it 10-16 night: seed on (match, t0, anchor tick, side, name).
- NO_HERO refusals (a): H1 and H3 each exposed one hero play the SIM refuses; both fights were agreeing and left strict.
- H2 hides rather than fixes; the real fix spawns the second-summon bodies by cloning them from a probe play.
- Own Knight estimate: 0.921 measured with the three fixes; in-flight projectile seeding might add 1-2 fights
  (+0.015-0.03) -> ~0.94-0.95 (b). The rest is U / unresolved.

## Files (this directory)
patches/ (H1_hero_object_top.patch, H2_by_parent_child_not_made.patch, H3_snap_nearest_point.patch, fights_all3.py),
cmp_h1/h2/h3/all3.txt, table_base.txt, cls_base.txt, all3/cls_all3.txt, all3/lostshot_keys.txt, scripts (div.py, tl.py,
path.py, hist.py, classify2.py, lostshot.py, scan_top.py, inflight.py, compare.py). Pod B: /workspace/results/knight_{base,h1,h2,h3,all3}.
Per-tick dumps with phase-3 targets stayed in the session scratchpad (not the repo).
