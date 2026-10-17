# Night 10-16 parity diagnosis: own Tesla / Tesla evo

Worker report (DONE_WITH_CONCERNS), saved by the lead from the worker's final message (subagents could not write this
file). Captured strict cohort, royalesim 0.1.35, K=8. Concerns: the fix makes two small opponent cards worse (n <= 5
each); the first look at all 17 failing fights used single laptop replays, the K=8 cohort score ran on pod A.

## Summary

| fix | class | Tesla fights explained | own Tesla normalised [CI] | Tesla evo | overall normalised [CI] |
|---|---|---|---|---|---|
| baseline (F35_BASE/_cap) | - | - | 0.781 [0.651, 0.903], raw 0.764 | 0.832 (n 18) | 0.877 [0.848, 0.901] |
| H1 projectiles in flight at t0 injected | H (a) | first divergence in 11 of 17; fixes 3 | 0.835 [0.695, 0.960], raw 0.818 | 0.832 | **0.908 [0.880, 0.931]**, raw 0.836 -> 0.867 |
| S1 Goblin Machine rocket missing in the SIM | S (a) | 4 (2 base, 2 evo) | est. ~0.87 | est. ~0.92 | - |
| S2 shots at an already-hidden Tesla still land in the SIM | S (a) | 1 | est. ~0.89 with S1 | - | - |
| Rune Giant (GiantBuffer) enchant bonus | U | 1 | | | |
| Electro Giant reflect not triggered by the Tesla | S (b) | 1 | | | |
| divergence in another body (path / target cascade) | unresolved | 6 | | | |
| Tesla deploy / first target ~1 tick later live | (a) all cards, cause (b) | 1 | | | |

## 1. Per-fight table (17 failing strict fights: 13 base, 4 evo; death ticks live / SIM, SIM after H1 where changed)

| fight | form | live / SIM | class | first divergence |
|---|---|---|---|---|
| 162405@745 | base | 803 / 825 -> 819 | H1 + U (rune) | t0+2 own Knight hp 163 live vs 314 SIM: a Blowdart dart (151) in flight at t0 absent in the SIM; after H1 the hits on the Tesla match (773/777/789/801) except 777: live 452 = Goblin Machine punch 232 + Rune Giant bonus 220 (86 x 2.56), SIM 232 |
| 162405@2321 | base | 2507 / 2523 | S1 | 2479 live Tesla -303 (119 x 2.56): Goblin Machine rocket fired 2467 from 2.8 tiles; no rocket in the SIM |
| 215752@490 | base | 717 / alive | S1 | live -445 at 646 from a rocket fired at 627 from 5.2 tiles; otherwise identical hits |
| 214908@3240 | base | 3472 / 3414 | S2 | Tesla hides ~3338; live the dart fired before the hide lands (3346, -226), the next one (fired ~3353 at the hidden Tesla) does no damage and the Blowdart switches to the Knight by 3360; SIM: 4 darts land on the hidden Tesla (3360/3376/3392/3408) |
| 200156@2312 | base | 2458 / 2470 | S (b) reflect | 2364 Tesla shot hits the Electro Giant; live the Tesla takes -282 and loses its target until 2370 (reflect stun); centre distance 3266 mt vs reflect radius 2000; the SIM never reflects |
| 175459@655 | base | 784 / 811 | lag (b) | SIM Tesla acquires at 677 (Bat 4, nearest); live at 679 when Bat 3 is nearer; an extra live Bat adds +80 at 752 |
| 175459@2289 | base | 2386 / 2407 | other body (b) | 2305-2312 opp Lumberjack ~107 mt/tick SIM vs ~72 live (ratio 0.67 = an IW slow, none seeded); SIM Tesla targets the Lumberjack, live the Elite Barbarian |
| 175459@4057 | base | 4195 / 4180 | unresolved | Lumberjack target differs at 4081; Elite Barbarian hp at 4117 |
| 214908@5371 | base | 5478 / 5511 | other body | 5390 opp Knight 390 mt further in the SIM -> Tesla targets the Musketeer (SIM) vs Knight (live); live Prince charge hits the Tesla 628 at 5425, SIM Prince never targets it |
| 220124@3502 | base | 3640 / 3671 | unresolved | Barbarians hp differs 158 at 3580; live has an extra 133 hit at 3609 from a Tombstone skeleton (SIM sets these up as Skeletons proxies) |
| 214535@3422 | base | alive / 3626 -> alive | H1 fixed | X-Bow bolt on the Hog Rider in flight at t0 |
| 220124@1608 | base | 1748 / 1682 -> 1746 | H1 fixed | princess arrow + Ice Wizard shot in flight |
| 221520@3001 | base | 3201 / 3221 -> 3199 | H1 fixed | princess arrow + Minion Horde shot in flight |
| 215752@1888 | evo | 2092 / alive | S1 | live -444 at 1964 from a rocket fired at 1948 from 4.0 tiles |
| 170937@2523 | evo | 2715 / alive | S1 | live -445 at 2715 from a rocket fired at 2697 from 5.9 tiles |
| 135037@4681 | evo | 4794 / 4826 | other body | own Knight hp 961 live vs 998 SIM at 4689 -> evo Archers move to the Tesla at 4740 live, to the Knight in the SIM |
| 214535@2868 | evo | alive / 3080 | other body + H1 gap | X-Bow bolt on the Tombstone (119 -> 21) not injectable (setup_shot_skipped:target); from 2874 the Baby Dragon targets the X-Bow live, the Tesla in the SIM |

Three more agree unperturbed but not on some perturbed replays (171824@741, 214908@704, 215432@1049): ceilings < 1 = noise (U).

## 2. Checked on the Tesla itself, all (a)
- Lifetime drain identical frame by frame with no attacker (e.g. 1182 -> 866 over 2343-2477).
- Damage per hit identical when the same hit lands (Blowdart 151, Goblin Machine punch 232, Elite Barbarian 255/389, Knight 202).
- No failing fight's first divergence involves our Tornado / Log or the evo Tesla pulse.
- Deploy end and first target acquisition are 0 or +2 ticks LATER live than SIM in 73/73 Tesla plays, never earlier; the same
  0/+2 pattern for every card (Skeletons mean +0.81, Knight +0.77, X-Bow +0.73) -> not Tesla-specific; harness play-tick
  choice vs SIM law untested (b).

## 3. Fixes
**H1 in-flight projectiles (harness)**: ext logs only; each troop / building / tower projectile in the t0 frame aimed at a
t0-board body or tower is injected with the shooter's real projectile record (new `Engine.shot_template`) at its live
position and target. No double counting (a): of 1,200 projectile tracks the damage lands in the frame gap after the last
row in 1,052, in 132 the target also lost hp in the gap before (another attacker not excluded), only 1 shows the drop
before the last row. Cohort: 35 fail -> agree, 3 agree -> fail (fixed own Log +8, Skeletons +4, Tesla +3, Knight +2, ...;
newly failing opp Elixir Golem, Skeleton Dragons, Balloon hero, one each; the EGolem fight's first divergence (t0+6) exists
before and after). Normalised drops: own Knight 0.897 -> 0.895 (raw rose 0.854 -> 0.859, ceiling rose more), opp Minion
Horde 0.602 -> 0.596, opp Elixir Golem 1.0 -> 0.8 (n 5), opp Electro Wizard 0.438 -> 0.389 (n 3), opp Barbarians evo
1.05 -> 1.0 (n 1). Strict counts: 564 injected, 23 skipped (target not set up), 20 skipped (no template). 37 tests in
test_fights / test_ceiling / test_ext pass; pyflakes clean. Old logs untouched by construction (not tested).

**S1 Goblin Machine rocket**: no code in crates/royalesim/src at v0.1.35 or v0.1.36; card table GoblinMachine.action_graph
`mechanic: false`; GoblinMachineRocketProjectile row exists (119 dmg, radius 1500, speed 350, crown 50%) but nothing fires
it. Live law (a), 27 captured logs: 24 rockets in 3 matches (6 at a Tesla); fired at a POINT (no target body) aimed at an
enemy body 2.8-7.1 tiles away (median 5.0); >= 100 ticks between rockets of one Goblin Machine; flight 10-20 ticks; first
rocket 74-374 ticks after the Goblin Machine appears. SIM fixture probe_gm.py: a Goblin Machine 5 tiles from a Tesla only
punches (232). Live fixture 162405@2321 (rocket fired 2467, -303 on the Tesla at 2479). Would fix 4 (b, strong).

**S2 shots at an already-hidden Tesla**: combat.rs v0.1.35 projectile landing `ignores_hide: shot_passes_hide(calib)`
(~line 2419, fn ~2958) assumes "a hidden building is no one's target", but hide.HELD_THROUGH_HIDE = client16402_kept keeps
units targeting a hidden Tesla, so every shot passes the hide. Live (a): 214908@3240 the dart fired at the hidden Tesla
does nothing; princess arrows at a hidden Tesla (38 rows in 214535@973, 26 in 221202@218) do zero damage; a shot fired
while it was up lands. Rule: a shot passes the hide only if its target was up when it was fired. Would fix 1.

**U Rune Giant enchant**: the reader would need per body the rune enchant and attacks left to the bonus hit.

**H follow-up (not built)**: inject target-less projectiles (Executioner axe, Bowler boulder) as fixed-aim shots (e.g. the
179 hp the X-Bow loses at t0+2 in 162405@2321).

## 4. Estimate
Own Tesla now a0 45/55 (0.818), normalised 0.835; with S1 + S2 48/55 (0.873) ~0.89 normalised (b, ceiling 0.982 assumed);
evo 14/18 now, 16/18 with S1 (~0.92, n 18). Still failing after those: 7 base (rune 1, reflect 1, 1-tick lag 1, other-body
4) + 2 evo -> own Tesla stays short of the >= 0.95 lower-CI goal.

## Paths
Patch `H1_inflight_shots.patch` (git apply --check passes vs HEAD) + `fights_inflight.py`; scripts trace.py, analyze.py,
who.py, inflight.py, gm_rocket.py, probe_gm.py, hidden_dmg.py, shots_at.py, tesla_stats.py, deploy_lag.py, flips.py,
proj_land.py, run_tests.py. Pod A: /workspace/results/tesla_inflight(2), working copy /workspace/w_tesla. Per-fight pickles /
traces with phase-3 values moved out of the repo to the session scratchpad tesla_local/.
