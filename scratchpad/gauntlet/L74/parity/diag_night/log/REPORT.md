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
