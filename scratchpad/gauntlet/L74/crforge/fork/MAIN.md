# crforge fork: clashbot-main (CF-MAIN, 2026-10-28)
Labels: **(a)** measured, **(b)** plausible but untested, **(c)** contradicted.

## STATUS (keep current)
- **Branch `clashbot-main` = `624eeb45183e1fe981252dd18f99225877595d2b`** (pod 30408, fork `/workspace/f635/crforge_fork`,
  worktree `/workspace/cfmain/crforge_fork`). No conflicts in the cherry-picks (the two lines touch disjoint files).
- **Default for SME: yes.** **Default for facade / training / re-drive: NO, blocked** by the HF gate (below): F1FIX makes
  the Rune Giant enchant, and its enchant reaches unmodelled paths that refuse (a fault = a crashed match).
- Gates of the m1 head: all done (table; summaries in `main/results/`). Libs on all four pods, sha-checked. `current` is NOT set on any pod (training blocked).
- Next step (owner / foreman decision, not taken here): either model the Rune Giant enchant cases F1FIX now reaches
  (a ticket "F1FIX-3": attack sequences that launch, the maker-left walk, Berserker step), or give training a lib without
  F1FIX (= `clashbot-cfclone` 3ebb4115, whose own HF run `/workspace/d1c/f20k_cfclone3` is CF-CLONE-3's).

## What is on the branch
| commit | from | what |
|---|---|---|
| upstream `e5462c82` + `cbdec89e e54769fe 1d338603 822d27f7 bec5811a` | clashbot-up-e5462c82 | 16.635 move + F635-5, F635-7, guard, F635c-11/12 |
| `aa664813` (= 62558795) | clashbot-cfclone | CF-CLONE: a clone carries the spawner state |
| `cb505923` (= bac75659) | clashbot-cfclone | CF-CLONE-2: deploying clones, Goblin Demolisher |
| `ddc5534d` (= c99784e4) | clashbot-f1fix | F1FIX-1: Rune Giant friend filter, hit_timer |
| `a677e080` (= 89b93932) | clashbot-f1fix | F1FIX-2: enchant on a damage-only attack sequence (Inferno Dragon) |
| `624eeb45` (= 3ebb4115) | clashbot-cfclone | CF-CLONE-3: a pulled unit (Fisherman hook) cloned |
Not merged (instrumentation, applied at build time only): clashbot-bp TickProbe 0001 + 0002 (the `tickprobe` lib);
0003-0005 MoveProbe / DmgProbe stay trace-only builds (`fork/bp/`).

## Gates
| gate | m0 `a677e080` (no CF-CLONE-3) | m1 `624eeb45` |
|---|---|---|
| core tests 16.402.22 | 2187 / 0 failures (29 skipped) | 2188 / 0 (29 skipped) |
| core tests 16.635.3 | 2187 / 0 (6 skipped) | 2188 / 0 (6 skipped) |
| determinism (Probe, 1 vs 4 threads, plain and tickprobe libs) | 16.402.22 `a0bd88c41f98b46d`, 16.635.3 `575c99887ba28802`, IDENTICAL | same hashes, IDENTICAL |
| SME dev (H2's command, hardened comparator sme11f, inputs v30, tickprobe lib) | 109 / 109, 0 regressions, 250,797 exact; plants 65,874, 0 missed; results.jsonl byte-identical to H2 (`15371187`) | same: 109 / 109, 0 regressions, 250,797 exact, plants 0 missed, byte-identical to H2 |
| FRESH1 (HF2's command) | 6 / 7, 15,509 / 15,719 exact; plants 10,904, 0 missed; byte-identical to HF2 (`e0965a7d`) | same: 6 / 7, 15,509 exact, plants 0 missed, byte-identical to HF2 |
| Clone sweep, Clone refusals (scene + match, both versions) | 0 (scene + match) | 0 (scene, match, cm = Clone after a Mirror, mc = Mirror of a Clone; 8 x ~19,400 scenes) |
| HF 20k fault sample (d1c/faults.sh, plain lib), gate <= 7 | **FAIL: 328 faults in the 17,000 replays of 68 / 80 shards** (base f20k_cfclone2 on the same 17,000: 7); 321 ran -> fault, 0 fault -> ran. The run hung at 68 / 80 (pod OOM killer: 30408 container 62 GB, oom_kill 28 -> 95 during it) and was stopped by PID | not run (the same F1FIX code; m0 is decisive) |

- **HF faults (a):** of the m0 faults' first messages, 315 are F1FIX's Rune Giant enchant reaching an unmodelled path:
  `giantbuffer_enchanting_buff on <unit>, whose attack sequence replaces its attack` (LittlePrince 117, AngryBarbarian_EV1
  80, AngryBarbarian 50, BowlerHero 18, Musketeer_EV1 10, EliteArcherHero 8, ThreeMusketeer 4, GoblinGiant_EV1 2),
  `walks back from an object whose maker has left` 23, `sets the Berserker's attack sequence step` 3. Before F1FIX-1 the
  Rune Giant found no friend, so these paths were never reached. Paired check on the first 100 replays, same pod, same
  time: old lib (lib_fix2) 100 ran, new lib 99 ran + 1 fault (034fd0b7, LittlePrince); same speed (395 s vs 390 s).
- **Clone sweep (a):** besides Clone refusals, the Rune Giant (GiantBuffer, GiantBuffer_hero) refuses 1 of 58 scenes per
  version and mode (T=160, `walks back from an object whose maker has left`): the same F1FIX reach, in a Clone scene.
- The SME dev set and FRESH1 do not reach these paths: results byte-identical to H2 / HF2.

## Libraries (sha-checked on every pod with `sha256sum -c SHA256SUMS`)
Path on every pod: `/workspace/crforge_main/<sha8>/{plain,tickprobe}/` = `lib/*.jar`, `BUILD.json`, `SHA256SUMS`.
`/workspace/crforge_main/current` -> the default head, set by `ship_main.sh` (not set yet). Jars are reproducible: the same
commit builds the same sha256 (CF-CLONE's control build).

m1 `624eeb45` jar sha256 (the four dependency jars are the same in both libs and as in rd_lib_bec5811a):
| jar | plain | tickprobe |
|---|---|---|
| core-1.0-SNAPSHOT.jar | `d1bba465afef98087293dc362c334bb49987b3895bd14cd6fd072d3bd78862be` | `de16981de9c7427775a5f4f3f7e4124b58dc2baa5536524ec31df79e0348dd0a` |
| env-1.0-SNAPSHOT.jar | `fdb9fe83ee6edd18e225019cc96d0383b54151157cc0d9611c33b82558ca3b10` | same |
| aircompressor-2.0.3.jar | `b86bb66f610079e0bf790d62e2ff68853eb0dc4748a6d68ae28bce92b68094aa` | same |
| jackson-annotations-2.22.jar | `21ddb598807d3a51a876704eb979d9296e1c6a6f47ab1826ff88c6d6a127a2d0` | same |
| jackson-core-2.22.2.jar | `ff167a6317be15895706c26668f45b898efe40ab8780970658210fe1393d52a6` | same |
| jackson-databind-2.22.2.jar | `d0da14c12b16b5d54719aa172d83b542ff4abeb8b0fb7db476fde8ceece760ca` | same |

| pod | m1 libs | tables |
|---|---|---|
| 30408 | `/workspace/crforge_main/624eeb45/` (built here) | `/workspace/f635/crforge_cache/tables/{16.402.22,16.635.3}` |
| 32657 | `/workspace/crforge_main/624eeb45/` | `/workspace/crforge_cache/tables/{16.402.22,16.635.3}` |
| 33920 | `/workspace/crforge_main/624eeb45/` | `/workspace/crforge_cache/tables/{16.402.22,16.635.3}` |
| 33308 | `/workspace/crforge_main/624eeb45/` | `/workspace/crforge_cache/tables/16.402.22` only |

## Which lib each pipeline uses
- **SME** (sme_live.py, runH.sh, SnapRun2 / BP_SNAP need TickProbe): `SME_LIB=/workspace/crforge_main/624eeb45/tickprobe/lib`.
- **facade / training** (rl_royale, D2-T, RX-X23, gap / gate): **stay on the current lib until the HF gate passes**
  (D2-T2 `/workspace/d2t2/lib_cfclone` on 33308, RX-X23 `/workspace/rx23/lib/lib` on 30408). When it passes:
  `CRFORGE_LIB=/workspace/crforge_main/<sha8>/plain/lib`, the facade (`crforge/facade/CfCore.java`) compiled by each
  pipeline into its own `CRFORGE_FACADE_BUILD` (never into crforge_main). The repo's CfCore.java (`c003fc74`) compiles
  against the m1 plain lib (a).
- **re-drive** (redrive/run.sh LIBDIR, d1c/faults.sh): same hold. When it passes: `cp -r
  /workspace/crforge_main/<sha8>/plain /workspace/redrive/rd_lib_<sha8>` (run.sh writes LIBDIR/facade), then
  `run.sh /workspace/redrive/rd_lib_<sha8> OUT`; faults.sh: `CRFORGE_LIB=/workspace/crforge_main/<sha8>/plain/lib`.

## Scripts (`fork/main/`, `fork/upstream_sync.sh`) and restart commands
- `pod/build_main.sh REF OUT [tp]` (30408): build REF in a throwaway worktree into OUT/lib + BUILD.json + SHA256SUMS.
- `pod/tt.sh VER LOG`, `pod/gates30408.sh TAG` (30408, in `/workspace/cfmain`): core tests both versions, both libs,
  determinism, HF 20k sample (`NO_HF=1` skips it). Restart: `cd /workspace/cfmain && nohup bash gates30408.sh TAG &`.
- `pod/sme_gate.sh TAG LIB` (32657, in `/workspace/pilot/f1fix`): H2 + HF2 commands, compared with H2 / HF2;
  output `/workspace/pilot/f1fix/runs/main_TAG.gate.txt`.
- `pod/clone_sweep.sh LIB OUT [MODES]` (33920, in `/workspace/cfmain`, with CloneProbe.java, sweep_sum.py,
  census_decks.tsv): `OUT/cp_clone_refusals.txt` must be empty.
- `ship_main.sh SHA8 [PORT...]` (laptop): copy a built head from 30408 to the other pods, sha-check, set `current`.
- `fork/upstream_sync.sh` now merges upstream onto clashbot-main (worktree per sync; then these gates).
- Run dirs: 30408 `/workspace/cfmain/g_m0`, `g_m1`, HF `/workspace/d1c/f20k_main_m0`; 32657
  `/workspace/pilot/f1fix/runs/main_m0_{dev,fresh1}`, `main_m1_*`; 33920 `/workspace/cfmain/cs_m0`, `cs_m1`.
- Open crforge gap reported by RX-X23 (2026-10-28, lib_fix2 = CF-CLONE-2, so it is on clashbot-main too; b, not
  re-run here): "Deflect_3000018 deflects proj_4000269 from the king tower KingTower_1_0 without a target, which is not
  modelled" (hold10 vs E4, seed block 741200). Not part of F1FIX-3. RX-X23's 3 intermittent SIGSEGVs are in libtorch
  oneDNN (`get_max_cpu_isa_mask`) inside the JPype process, not in crforge (b, by the stack frame named).
