# Parity round 7: summary (closer, 2026-10-18)

Base: FIN12 = HEAD c8f5219 harness on rsfork_fin11. Upgraded (stamped) 0.9250 on 8858 fights from 265 matches; full 0.9188 on 16506 fights.
Every number below is cmp.py (diag_night/r5c/cmp.py) vs /workspace/results/FIN12. "up / down" = strict fights whose aK moved.

What happened: the four bucket workers finished. Of the 9 verifiers, 2 finished (H-VOLLEY: land; S-EK-HITTICK: needs_work,
only because its run was unfinished). The other 7 died at about 11:42 when the lead's session hit its usage cap. Their arm runs kept
going on the pods. The closer finished or re-ran every measurement itself: P1 and P3 /workspace/w_r7close, results/v7c_*.

## Verdicts

| Patch | Kind | Bucket | Upgraded | Full | Reproduced by | Verdict |
|---|---|---|---|---|---|---|
| H-VOLLEY | harness | r7d | +5 / -0, 0.9255 | +9 / -0, 0.9193 | verifier (exact) | LANDED (in the joint) |
| H-CUBE-DATE v2 | harness | r7d | +27 / -12, 0.9263 | +51 / -26, 0.9198 | the dead verifier's orphan run, compared by the closer (exact) | LANDED (in the joint) |
| joint VOLLEY + CUBE v2 | harness | r7d | +32 / -12, 0.9268 | +60 / -26, 0.9203 | the dead verifier's orphan run (exact); patched file byte-identical | LANDED e15b284 |
| H-SNAP-BACK | harness | r7a | +15 / -5, 0.9260 | +34 / -18, 0.9195 | the closer's own all-499 run (exact) | LANDED e15b284 |
| S-PULSE-TWICE | fork | r7c | +1 / -0, 0.9251 | +1 / -0 | the verifier's orphan run (exact) | LANDED e0d7a709 |
| S-EK-HITTICK | fork | r7c | +8 / -4, 0.9255 | +16 / -8, 0.9191 | the verifier's run, finished after it died (exact); its fork tests: targeted ok, plant red, full 1954 / 0 | LANDED 9ac10979 |
| S-HOLD-REACH | fork | r7b | +5 / -2, 0.9254 | +8 / -3, 0.9191 | the closer's run on the verifier-built wheel (exact); verifier cargo 1954 / 0, plant red | LANDED 427597d3 |
| H-FIXED-AIM v2 | harness | r7c | +5 / -0 | +9 / -0 | the verifier's orphan run (exact) | not landed: the same fights as H-VOLLEY (redundant, conflicts) |
| H-IW-PRESS-DATE | harness | r7b | +29 / -12, 0.9265 | +56 / -34, 0.9196 | worker only | not landed: the same press tick (B - 4) as H-CUBE-DATE v2 (redundant) |
| H-PREROLL (and + SNAP joint) | harness | r7a | +63 / -45, 0.9267 | +149 / -110 | worker only | not landed: worker says land after more data; X-Bow loses MEETS |
| H-TPL-ANYBODY | harness | r7d | +2 / -3 | +5 / -6 | worker only | not landed (land after more data) |
| H-NEGHP (rebased) | harness | r7d | 0 / 0, 0.9243 | 0 / 0 | worker only | not landed (needs a reader fix) |
| S-EVOWITCH-CLOCK | fork | r7d | 0 / 0 | +1 / -0 | worker only, no cargo test | not landed (land after more data) |

## How each break was explained

- **H-CUBE-DATE v2:** 12 upgraded downs. 8 are cascades or tolerance crossings after an earlier divergence that is present in both
  runs. 4 are noise-origin (base ceiling 0.429-0.75). r7b dossiered the same fights at K=0 under the same press tick, and the cube
  appears on the live tick in all of them.
- **H-SNAP-BACK:** 4 deterministic downs (144756@659, 201130@2534, 201130@2584, 234527@2464). In the closer's K=0 dossiers (P3
  w_r7close/dsB vs dsA), both runs already diverge at +4 to +18 ticks: Witch and Skeleton Army position and target splits. 010615@2921
  is noise (base ceiling 0.571).
- **S-EK-HITTICK:** 4 upgraded downs, all ceiling 1.0, each already diverging on base. The worker's dossiers found an MK target
  error, a +116 hp split, a Blowdart target error, and an Evo Knight hit 1 tick off. The fork tests pass.
- **S-HOLD-REACH:** 185911@2980 (arm ceiling 0.571, downstream of a +197 Tesla hp split) and 044347@229 (base ceiling 0.429): noise.

## Landed state

- Harness: HEAD e15b284 (fights.py + test_fights.py). Parity tests 93 pass plus the 5 known bundle-only failures; pyflakes clean;
  the tag grep on both patches is empty.
- Fork clashbot36 (worktree C:/Users/benpe/rsfork36): a697d1f9 + e0d7a709 + 9ac10979 + 427597d3.
  - The am was clean (3-way).
  - Tree 7ff40f45 is the same tree the closer built and tested.
  - cargo test --profile gate: 1960 / 0 / 3 ignored.
  - Bundle: parity1016/clashbot36_fin14.bundle.
  - Wheel: P3 /workspace/rsfork_fin14c.

## Bucket findings worth keeping (from the workers; details in the journal results r7_closer/journal_results.txt)

- **r7a, own Skeletons:**
  - The set-up walker error is the route, not facing or offset (H-PREROLL takes first-step exactness from 24% to 68%).
  - The swarm contact law is exact (98.7%).
  - A phase-3d reader spec (route, goal cell, segment, facing, offset) is in the r7a report.
- **r7b, Tesla / Tesla evo / IW hero:**
  - Mega Knight jump / landing is behind 16 fights.
  - UD v2 (now landed in fin13 / fin14) fixes 9 of 12 hide-damage fights.
  - Retarget onto a just-deployed IW: 6 fights, untested lead.
- **r7c, Knight / Knight evo / Rocket / Tornado:**
  - EKRET (the Evo Knight reduction returning through a windup) is the biggest remaining Knight evo error, with a census.
  - The Rocket and Tornado flight / pull models match live.
  - Tornado is data-limited (about 650 upgraded matches).
- **r7d, opponent tier-B cards:**
  - Equidistant target picks and Bats paths are contradicted as causes.
  - Mirror +1 level is a lead.
  - A deploying MK retargeting is a lead.
  - Hog, Witch, Bats, Skeleton Army and Goblin Gang are error-limited.

## FIN13 (P3 /workspace/results/FIN13, FIN13_stamped)

Inputs: HEAD e15b284 harness, run on rsfork_fin14c (clashbot36 427597d3: UD v2 + PULSE + HITTICK + HOLD-REACH). Exports
attacks13s / buffs13: 499 reused + 139 new captures, births for 405 logs, shields for 110. 638 logs, K=8, window 240, 0 crashes.

- **Upgraded (stamped):** 0.926 [0.920, 0.932] on 13049 fights from 403 matches. The ceiling is 0.992 and normalised 0.933. For
  comparison, FIN12 was 0.925 on 265 matches.
- **Full:** 0.922 [0.917, 0.927] on 20705 fights from 630 matches. FIN12 was 0.919.
- **Same 499 logs as FIN12** (the closer's cmp.py of FIN13 vs FIN12; this mixes the round-7 patches and UD v2):
  - upgraded 0.9250 -> 0.9302, +75 / -21
  - full 0.9188 -> 0.9227, +141 / -56
  - own Tesla 0.914 -> 0.936, Tesla evo 0.903 -> 0.935, Knight evo 0.894 -> 0.903, IW hero 0.936 -> 0.939, Bats 0.768 -> 0.812
- **The 139 new matches score lower than the old ones.** The whole cohort is 0.926, the old matches alone 0.930.
- **coverage.py:** valid (403 stamped matches); overall not met (lower 0.920 vs 0.975).
  - Tier B: 0.278 of plays meet. FIN12 was 0.217. Own Tornado now MEETS at 0.976 [0.953, 0.995].
  - Tier C: 0.261 (FIN12 0.200). All-plays coverage: 0.244 (FIN12 0.184).
- **Own cards, upgraded:**
  - MEET: Log 0.971 [0.961, 0.980], X-Bow 0.968 [0.956, 0.979], Tornado 0.976 [0.953, 0.995].
  - Not yet: IW hero 0.940, Rocket 0.940, Knight 0.939, Tesla 0.930, Knight evo 0.911, Tesla evo 0.911, Skeletons 0.874.
