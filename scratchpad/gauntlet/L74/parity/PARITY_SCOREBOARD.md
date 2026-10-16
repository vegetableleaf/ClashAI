# S2 fight parity scoreboard: first measurement (2026-10-16)

**Status: method built and prototyped. All numbers below come from a laptop prototype and are not the final scoreboard.**
The prototype ran on royalesim **0.1.35**: the PyPI `cp310-abi3-win_amd64` wheel, unpacked outside the repo. Its data
files have the same SHA256 as the pod's `L74/rt35/build_manifest.json`. It covered **16 frame-logged matches**
(every 3rd 10-15 15:00-18:59 log), giving **846 fights**: 548 "core" and 193 "strict". The full run (94 frame-logged
matches) is the pod command at the end. Archived outputs: `output/fights_proto_rt35win/` (gitignored).

## Method (`fights.py`)
- **Fights.** There is one fight per live deployment: own taps, opponent first sightings and own spells. A fight starts
  at the last frame before that deployment, or earlier if a body is still deploying, and lasts 240 ticks (12 s).
- **Rebuilding the board from the frame.** Towers are set to their live hp, and the king is woken if the frame shows it
  awake. Every live body is spawned at its exact point with its live hp. Levels come from each body's `max_hp`, read
  against `unit_hitpoints`: exact table matches, so nothing is assumed. Evo and hero bodies get their form's engine
  record swapped in. A child body becomes the card whose own unit it is (a Witch's Skeleton becomes a Skeletons body),
  and a Ram Rider's rider comes from its parent. A body that was standing still and shooting a tower that lost hp in
  the last second is locked onto that tower.
- **Replay.** Each in-window play is a real deploy at the tick its first body appears (mid frame-gap), at the own tap
  point (the confirmation's unrounded `intended`) or at the opponent's first-seen centroid. Own spells are cast at tap
  + this match's tap-to-spawn delay. Own Hero IW presses are replayed too.
- **Scoring.** Bodies are paired by point at the start, and new bodies by card, side, form, max_hp and nearest point.
  Per fight, three things are checked:
  - **Outcome:** the focus bodies end alive or dead the same, the first death is the same, and each tower's damage is
    within max(150, 15%).
  - **Death-time error.**
  - **The upstream 1/4-tile metric:** the share of paired body-frames within 250 millitiles.
- **Ranking.** Impact = fights per match × (1 − outcome agreement + mean tower-hp error / 1000). Scoreboards are written
  as `strict` (no blocker at all), `core` (hidden opponent spells and buttons allowed) and `all`.
- **Upstream method reused.** The scoring follows upstream `examples/replay_parity.rs` (unit-ticks within 250 native,
  alive/missing/extra, first-divergence cause). Upstream replays whole recorded battles that have full information.
  Ours restarts from the live board every fight, because a whole-match replay diverges within seconds
  (`TRIAGE.md`, `own_timing/EARLY_END.md`).

Headline (prototype):

| set | fights | outcome agree | 1/4-tile |
|---|---|---|---|
| strict | 193 | 0.715 | 0.821 |
| core | 548 | 0.620 | 0.798 |
| all | 846 | 0.514 | 0.737 |

## Harness artefacts found and removed (each looked like a large SIM error first; before-numbers are from earlier prototype iterations)
1. **Twin Hero IW row.** The reader shows the Hero IW twice: one row on the same point keeps 911 hp all its life.
   Before dropping it, own IW had 1/4-tile 0.27 and 52 live-only deaths. After: 0.92 and 7.
2. **Rounded tap.** The `play` event rounds xy to 4 decimals, so a tap on a tile edge (0.65625×32 = 21.0) moved
   one tile: Tesla was put 1 tile toward the river, 1/4-tile 0.42. Using the unrounded `intended` brings it to 1.00.
3. **Lost target lock.** A setup spawn has no target. An X-Bow that live was shooting the tower switched to an Electro
   Giant, took reflect damage and died, an error of 1960 tower hp (`151727@640`). With the inferred lock the tower hp
   matches exactly: 1960 vs 1960, X-Bow 1658 = 1658.
4. Own spells in flight at the start, bodies still deploying, and plays at the start tick: all now handled or flagged.

## Validated: no material mismatch
| mechanic | evidence |
|---|---|
| X-Bow lock, DPS and decay | strict: 1/4-tile 0.996, survival 0.99, n = 105 body-fights; decay and 98 per hit match frame by frame (`170420@172`) |
| X-Bow and Tesla deploy time | SIM − live: X-Bow 0 ticks (n = 58), Tesla −2 ticks, i.e. one frame (n = 45) |
| Log, Rocket and Tornado timing | first hit SIM − live: Log +2 ticks (n = 227 bodies), Rocket 0 (14), Tornado 0 (59) (`spellhit.txt`, core fights of every 10-15 15:00-18:59 frame log) |
| Tesla | 1/4-tile 1.00, survival 0.976 |
| Fresh Royal Hogs, Ram Rider path and tower hits | hogs 1/4-tile 0.925 (core, n = 64); Ram Rider exact (`170420@172`) |

## Top 5 mismatches (prototype, ranked by decision impact × size; causes are hypotheses)
| # | mismatch | evidence (prototype) | hypothesised law | changed in 0.1.35? |
|---|---|---|---|---|
| 1 | **Death-spawn placement** (Elixir Golem split, Skeleton Balloon drop, Witch spawns) | Elixir Golem pieces: **first-frame error median 424 millitiles, 1/4-tile 0.321** (n = 32) vs parent 0 and 0.861 (n = 8); Balloon skeletons 315 / 0.501 (n = 28), survival 0.714; Witch skeletons 109 / 0.638 (`children_core.txt`; worst `154121@4487`) | `spawner.DEATH_SPAWN_RING` (client_fixed_ring_listed, fitted on 15.535), `DEATH_SPAWN_PUSHBACK` = client_ring_slide, `DEATH_SPAWN_LAYOUT` = facing_ring_rounded (reads the parent's facing) | **No.** None of r73's eleven flips is a death-spawn law (`LIVE_SPAWN_AREA_BIRTH` is only about Poison pulses). |
| 2 | **Witch / Dark Witch movement and survival** | newly deployed Witch: 1/4-tile 0.553, dies SIM-only 14 vs live-only 4 (strict, n = 138); Dark Witch 0.32, 6 vs 2 (n = 29) | ranged hold and retarget next to its own spawn ring: `spawner.SPAWN_POINT` (client_rounded_facing_degree), the contact push from fresh spawns | No |
| 3 | **Skeleton Army formation and kill count** (cheap swarm vs IW, Log and Tesla) | strict, fresh SA: 1/4-tile 0.597 (n = 165); core: late-stagger members first error 352, 1/4-tile 0.256 (n = 36) vs early 35 / 0.623 (n = 199); dies SIM-only 52 vs live-only 14 | `formation.LAYOUT` / `DEPLOY_STAGGER` (client16402) for the 15-member layout; the deploy point is the first-seen centroid, an approximation | Related: `formation.MEMBER_WATER_POINT` (members laid on the river stay there) is new in 0.1.35 and is already in these numbers |
| 4 | **Mega Knight carried into a fight** | setup MK: 1/4-tile 0.659 (n = 15) vs fresh 0.889 (n = 14); 2 live-only deaths; SIM death +1.5 s; `182623@3144`: MK's hit on our Knight lands about 0.3 s later in the SIM, then the Knight ends 1.3 tiles off | **untested**: MK attack/jump state is not public (a setup artefact is likely); a jump-trigger / landing law otherwise | No |
| 5 | **Which units the Log hits** (highest-impact anchor: own Log, outcome agree 0.609 strict n = 23, 0.519 core n = 54) | timing matches (+2 ticks), but of the bodies the Log hits, 18 are hit live only and 23 SIM only (15%) | `spells.ROLLING_HIT_SHAPE` (client15535_max_y_edge_open, MEDIUM, fitted on 15.535), `knockback.ROLLING_CONTACT_RADIUS` 475 (MEDIUM, 4 pushes) | Partly: 0.1.35 flipped `spells.ROLLING_HIT_SWEEP` → current_box and added `spells.ROLLING_SPARES_LEAPERS`; this residual is **after** those flips |

These five are not conclusions. Each needs its fixed fixture and a paired before/after on the full pod cohort (one law at
a time; FORK.md rules).

## What blocks exactness
- **Opponent hero and champion buttons are not logged.** 535 of 846 fights have one on the board (Hero Knight,
  Skeleton King, Mighty Miner, Boss Bandit and others). This is the largest exclusion.
- **Opponent spells.** Only projectile spells are seen, and only at decision ticks (about every 0.65 s): 166 fights
  are flagged. Zap, Lightning, Earthquake, Poison, Freeze and Rage are invisible. In naive comparisons this
  contamination dominates: own X-Bow has 24 live-only deaths in core vs 0 in strict; own IW 40 vs 7.
- **Hidden per-unit state at the fight start:** target (only tower locks are inferred), attack phase and cooldown,
  Prince charge, facing (death-spawn layout reads it), Tesla hide state, Witch and Tombstone spawn timers, hero button
  charge, and evo counters.
- **Opponent tap point.** For formations, the first-seen centroid stands in for the tap.
- **Frames are about 10 Hz,** so timings are quantised to ±1 tick.
- **Levels of cards never seen as a body** (opponent spells) fall back to the side's modal level.
- **Geometry census.** 599 of 18,630 live ground-troop samples (3.2%; Skeleton Army 226) lie in cells the SIM marks
  impassable. 69 setup bodies were snapped to the nearest passable cell. This is a census only, not yet a finding.

## Full run on 0.1.35 (pod)
From the laptop, copy the frame logs to the pod's checkout (they are untracked):
```bash
tar czf /tmp/frames1015.tgz -C scratchpad/gauntlet/L68/live_reader $(cd scratchpad/gauntlet/L68/live_reader && ls live_play_2026101[5-9]_*.jsonl)
# copy /tmp/frames1015.tgz to the pod and untar into /workspace/cb_rt35/scratchpad/gauntlet/L68/live_reader/
```
On the pod (the cb_rt35 checkout with this commit, `/workspace/venv35` from `L74/rt35/setup_rt35.sh`):
```bash
cd /workspace/cb_rt35 && nohup bash scratchpad/gauntlet/L74/parity/run_fights_pod.sh > /dev/null 2>&1 < /dev/null &
# -> /workspace/results/FIGHTS35/{SCOREBOARD_strict.txt,SCOREBOARD_core.txt,scoreboard_*.json,matches/,run.log,DONE}
```
- **Expected duration:** the laptop measured about 11 core-seconds per match (846 fights in 87 s on 2 workers).
  94 matches on 14 workers is about **2 min**, plus about 1 min for the runtime check. Under 5 min on a ~15-CPU pod
  even if Linux is 2× slower. This is a short job.
- **Prototype rerun locally:** `PARITY_SIM_PATH=<unpacked 0.1.35 wheel> python fights.py run --out <dir> --files 'live_play_20261015_1[5-8]*.jsonl' --stride 3 --workers 2`
- **Rescore without the SIM:** `python fights.py score --out <dir> [--clean strict|core|all]`
