# Night 10-16 parity diagnosis: own Log

Worker report (DONE_WITH_CONCERNS), saved by the lead from the worker's final message (subagents could not write this
file). Base asked for: the Tesla in-flight harness (fights_inflight.py). Captured strict cohort, pod A, K=8, royalesim 0.1.35.
Result: own Log 0.867 [0.770, 0.952] -> 0.960 [0.912, 0.993] with A + B + C (n 80); overall 0.908 -> 0.923. No SIM law for
the Log itself. Meets 0.95 on the point estimate, not on the lower bound (0.912).

## Summary

| arm | n | a0 | normalised [95% CI] | OVERALL normalised [95% CI] |
|---|---|---|---|---|
| F35_BASE (795b155) | 81 | 0.765 | 0.768 [0.669, 0.861] | 0.877 [0.848, 0.901] |
| J0 = fights_inflight.py | 81 | 0.864 | 0.867 [0.770, 0.952] | 0.908 [0.880, 0.931] |
| + A rolling-spell hit set | 81 | 0.914 | 0.920 [0.855, 0.978] | 0.912 [0.885, 0.935] |
| + A + B Hero Goblins plays | 81 | 0.938 | 0.948 [0.890, 0.990] | 0.922 [0.902, 0.940] (n 1002) |
| + A + B + C pending death spawn blocks strict | 80 | 0.950 | 0.960 [0.912, 0.993] | 0.923 [0.902, 0.941] (n 1000) |
| + H2 Rascal girls (not built here; = knight H2', landed) | 80 | ~0.975 | ~0.98 (untested) | |

Regression checks: patch A leaves 904/904 non-rolling-spell views byte-identical to J0; only own Log / opp BarbLog / opp Log
anchors change. opp Log (n 2) 1.0 -> 0.5 is a real failure: 221839@1142 our Tesla 324 -> 22 live = a level-12 Log (295) + 7
decay, the SIM's opponent Log kills it -> likely `spell_levels` reads levels for OUR spells only, so the opponent Log falls back
to a default level (b). opp BarbLog 0.891 -> 1.013. Patch B: a0 regresses nowhere; 4 other-card fights flip to agree; opp
GoblinMachine aK 0.953 -> 0.938 with a0 unchanged = event-index seed reshuffle (fixed in the lead's integration).

## 1. The 19 baseline failures on the in-flight harness

| fight | class | first divergence | fixed by |
|---|---|---|---|
| 133158@650 | H-score | 708 a Skeleton Army skeleton 8.5 tiles from the Log's lane dies SIM-only; the 13.45-tile reach circle credits it to the Log | A |
| 135037@2886 | H-score | 2910 enemy Knight (43 hp) dies 13 ticks before the Log lands; an Ice Spirit dies before the roll reaches it | in-flight |
| 162405@3352 | H-score | 3404 Rune Giant 532 vs 641 hp before the Log; both die at the pass (3420 vs 3418) but credit flips (221 <= 268 vs 330 > 268) | in-flight |
| 165317@1514 | H-score | 1517 Mini Pekka in the other lane; a 351 drop 8 ticks before landing credited by the >= d/2 rule | in-flight |
| 171357@1655 | H-setup | 1663: 7 Skeleton Balloon skeletons land after t0 (balloon died ~1651): on no board and in no play, the SIM never has them | C (strict blocker) |
| 171357@3889 | H-setup | 2 Rascal girls absent in the SIM (setup_child_by_parent) | knight H2' |
| 171357@4351 | H-score | 3 wrong credits: a flying balloon (Log is ground-only), a Goblin Machine dead before landing, a skeleton born behind the roll | A |
| 175459@3831 | other card | 3837 princess shot -109 live, SIM 14 ticks later | in-flight |
| 175459@4799 | H-score | Angry Barbarian in the other lane, killed by a tower | A |
| 214220@2808 | H-setup | 2 Rascal girls missing in the SIM; the live Log kills them at 2834 | knight H2' |
| 214535@1068 | H-score | a Hog Rider dies 13 ticks before the Log lands | in-flight |
| 214908@225, @3454 | H-deploy | the opponent's 4 Hero Goblins never deployed (role-child rule vs a 4,090-hp body with the same card id) | B / knight H1 (landed) |
| 214908@5773 | H-score | a Prince in the other lane, killed by a tower 5779 vs 5793 | in-flight |
| 215432@1319 | U (swarm path) | 1329-1331 a skeleton the live Log kills is 0.95 tiles off the roll in the SIM | open |
| 215752@1358 | other card | 1362/1365 our IW and Tesla first shots (-158, -118) live-only | in-flight |
| 220623@1983 | other card | 1987 a Witch skeleton killed live 6 ticks before the Log lands; its SIM pair dies under the roll 16 ticks later | open (knight H6 fixed it later) |
| 220623@4095 | H-score | a Witch skeleton in the other lane | A |
| 221202@3020 | other card | the opponent's Princess idles in the SIM while she walks into the roll live | in-flight |

Tower damage in the Log view agrees 19/19.

## 2. Is the Log itself right? (all measured)
- Trajectory (19 traces): the SIM's throw, landing at play tick + 9 and 200 mt/tick roll match the live projectile rows; the SIM
  lands on the same tick as live or 1 earlier, never later.
- Hit set (hitset.py): for bodies under the roll in both runs the hit agrees 0.986 on own strict fights (n 222), 0.969 on every
  Log fight (n 357); the 3 own-strict disagreements = hp that already differed, a body at a different point, a Dark Prince
  plausibly keeping a fresh setup shield (untested); none changes a death.
- Live hit geometry (149 exact Log drops, no SIM): every hit within the SIM half-width 1950 + body radius (max 1768); front gap at
  the frame before each hit median 748 mt vs the SIM box ~800.
- PARITY_SCOREBOARD #5 ("which units the Log hits") is CONTRADICTED as a Log law: those counts came from the attribution window,
  bodies missing / displaced in the SIM, and hp that differed before the Log.

## 3. Fixes
1. Patch A `patchA_rolling_hit_set.diff` (H-score): rolling spells only -- the Log is credited with an enemy GROUND body only when
   the table box rolls over it (within one tick before the frame gap; the live roll lands 0-1 tick late); a child body is judged
   by its proxy card; bodies born under the box are excluded (the live Log hit 0 of 3 Hero Goblins objects born there); deaths
   from any cause compared up to the earlier pass + 4 ticks; views without the new fields keep the old rule.
2. Patch B `patchB_unit_cap_top.diff` (H-deploy): superseded by knight H1 (own_unit rule, landed); keep one, not both.
3. Patch C `patchC_pending_death_spawn.diff` (H-setup): a fight whose t0 falls between a parent's death and its children's first
   sighting gets strict blocker `death_spawn_pending_at_start` (2 strict fights: 171357@1655, opp Fireball 175459@4259). It
   REMOVES fights rather than fixing the SIM -- not landed by the lead.
4. H2 Rascal girls: child_proxy returns __parent__ for second_summon (right for Ram Rider / Goblin Giant, wrong for Rascals, whose
   setup spawn makes only the boy) -> landed as knight H2'.
5. Still open (4 of 80): 171357@3889 and 214220@2808 (H2, now landed), 215432@1319 (skeleton path), 220623@1983 (another card's
   early kill).

## Paths
diag_night/log/: patches (patchA_rolling_hit_set.diff, patchB_unit_cap_top.diff, patchC_pending_death_spawn.diff), arm files
(fights_J0.py, fights_JA3.py, fights_JA3B.py, fights_JA3BC.py; single patches on 795b155: fights_patchA/B/C.py), analysis
(trace_log.py + traces/, hitset.py + hitset_sum.py, live_hits.py + hit_geom.py + miss_geom.py, compare.py, list_fail2.py,
try_patch.py, top_pollution.py, pending_spawn.py, probe_*.py). Pod A authoritative: /workspace/results/log_J0, log_JA3,
log_JA3B, log_JA3BC (other log_* dirs superseded). Runner /workspace/w_log/run2.sh.

## Round 2 (vs I6, captured strict, pod A; one change each; worker report saved by the lead)

| arm | own Log [CI] | OVERALL [CI] | fixed / broken | views changed |
|---|---|---|---|---|
| I6 (CAP_I6, sha 227a4b05) | 0.975 [0.936, 1.0] (n 81) | 0.929 [0.907, 0.946] | - | - |
| K1 opponent spell levels (patchK1_opp_spell_levels.diff) | 0.975 | 0.930 [0.909, 0.947] | 1 / 0 (opp Log 221839@1142) | 6 of 1000; every other row byte-identical |
| K2 pending death spawn: start the parent alive (patchK2_pending_spawn_parent_alive.diff) | **0.988 [0.957, 1.0] MEETS** | 0.930 [0.908, 0.948] | 1 / 0 (own Log 171357@1655) | 998 identical |

- K1: spell_levels() already reads both sides on new logs but needs >= 2 drops that exactly equal one level's damage; below that it fell
  back to the side's modal troop level. Fix: with < 2 exact drops pick the level with the most evidence (exact drops on our bodies +
  crown-tower drops within +-1 of that level's tower damage, only for cards carrying their own crown %; Poison keeps it on the area
  object, so excluded), used only if no other level ties. 221839@1142: the opponent Log hits our IW 911 -> 616 = 295 = level 12;
  before, the SIM cast it at 16 (429) and killed the Tesla. Effective changes (each from exact drops): 221839 opp Log 16 -> 12;
  214908 opp Arrows 16 -> 15 (tower -36 x3 = 178 x 20%); 200156 opp Fireball 15 -> 16 (tower -253 x2 = 1100 x 23%); 195328 own Log
  16 -> 15; 214535 own Log 16 -> 15. Seen, not changed (b): 175459 (classic, level 11 cap) opponent Rage set to 15 from two drops of
  260 -- likely coincidence; live Poison hits a Knight 158 / pulse and a tower 33, the SIM's level-16 Poison 147 -- possible SIM gap.
- K2: in cut(), when the start frame falls between a parent's last sighting and its death-spawn children's first sighting (same
  near-parent rule as deployments()), the fight starts on the parent's last frame, the parent alive with its live hp, its killing shot
  injected by the in-flight code; the SIM kills it and makes the children. 171357@1655 -> t0 1650: Skeleton Balloon at 64 hp with the
  princess shot in flight; the SIM drops 7 skeletons and the Log kills all 7 on the live ticks (1673-1683): 0/7 mismatches (was 7/7).
  175459@4259 -> 4247 agreed before and after. 6 fights get a new start; none changes strict status. Replaces patch C.
- Still failing own Log after K2: 215432@1319 = a Skeleton Army skeleton drifts to (10028, 21016) in the SIM (outside the roll),
  our Knight kills it at 1349 -- swarm path divergence, plausibly unobservable (each skeleton's target / move / collision state).
- Files: patchK1/K2 diffs (apply cleanly to I6 and to I7 7a4f3a0), fights_K1.py (1d1eed60), fights_K2.py (0ed92b64), opp_levels.py
  (+ .txt), lv_diff.py, tower_drops.py, try2.py, recut.py; pod A /workspace/results/log_K1, log_K2.
