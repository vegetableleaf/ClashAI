# fin16: fin15 + the client-dated 2026-10-19 card table (A1, plan1026 Pillar 1 Stage 0, 2026-10-27)

Labels: **(a) measured** (with n), **(b) plausible but untested**, **(c) contradicted**. Pod 32657 (157.157.221.29, CPU only:
the GPU belonged to worker S2 the whole time, 97 % busy). Everything below ran under `/workspace/f16/` on that pod.
This is the last RoyaleSim law round (PLAN.md Pillar 1). No law beyond the 10-19 table went in.

## 0. Deliverable

- **Wheel `fin16`**: `royalesim-0.1.36-cp310-abi3-manylinux_2_34_x86_64.whl`, sha256
  **b5c3510155f7a8c8aeb6b03664f4f5e302d9a109c9b51d3e850fb2552dc5c7c5** (5,134,381 bytes).
  - Fork commit compiled in: **3f5676076fa7293de5355fa7c76275ddfbf4322c**, clean (tree 7280b75d). `Battle.provenance()` on the
    pod prints exactly that, and `card_table_source()` = embedded.
  - Branch `fin16` = fin15 305aaafc + `patches/0001` + `patches/0002` (git am). 0001 produces commit **b2809aa1** (W23's
    patch1019 head), byte for byte: same hash, tree 82b677fb. 0002 = W19's arm (be0766c on the old W19 pod), re-applied as 3f567607.
  - Fork worktree: `C:/Users/benpe/rsfork_fin16` (branch fin16; same repository as rsfork36 / rsfork_w8; clashbot36 not moved).
  - Copies: the laptop's `/tmp/claude/parity1016/fin16/` holds the wheel and `clashbot36_fin16.bundle`, a full-history bundle of
    fin16 (sha256 8a265d8d...). Pod 32657 holds `/workspace/f16/wheels16/` and `/workspace/in/fin16/`.
- **Runtime id `fin16-linux`** (opt-in). It uses venv `/workspace/venvf16` and the manifest `build_manifest_fin16.json`
  (30 files, frozen on pod 32657).
  - `pipeline/royale_runtime.py`: fin16-linux is a known id. Its MANIFEST is this folder's manifest, and its RUNTIME is the
    venv's purelib. It joins the version-pinned ids in `activate()`.
  - `pipeline/royale_heroiw.py`: fin16-linux enables the Hero IW adapter. Under fin16-linux only, `CARD_TABLE =
    client160402017_20261019`, and `selected_card_data()` returns the embedded 10-19 JSON.
  - Every other id is unchanged (a). Each of the 11 old ids (unset, 20261006, 20261006-linux, 20261012, 20261012-linux,
    20261016-linux, fork36-linux, fin13-linux, fin15-linux, fork, unpinned-linux) was probed. With HEAD's selector files and
    with the edited ones, all 11 give the same id, manifest, heroiw flag, engine_options and CARD_TABLE. The probe is
    test_royale_runtime_rt35.py's PROBE plus CARD_TABLE.
  - HEAD refuses fin16-linux as an unknown id.
  - This is not W23's `patch1019/pipeline_card_table_after_wheel.diff`. That diff moved EVERY id to the 10-19 table, and the
    fin15 wheel refuses the 10-19 name.
- **Install on a training pod**:

```bash
# laptop -> pod: the wheel + a code tree at this commit (pipeline/ + parity/fin16/)
scp /tmp/claude/parity1016/fin16/royalesim-*.whl <pod>:/workspace/in/fin16/
FIN16_SHA=b5c3510155f7a8c8aeb6b03664f4f5e302d9a109c9b51d3e850fb2552dc5c7c5 FIN16_PIN=3f5676076fa7293de5355fa7c76275ddfbf4322c \
  CB=/workspace/<code tree> bash $CB/scratchpad/gauntlet/L74/parity/fin16/setup_fin16.sh   # -> /workspace/stepd/fin16/FIN16_OK
# train / eval: /workspace/venvf16/bin/python + ROYALE_RUNTIME=fin16-linux where a launcher says venvf15 + fin15-linux
```

  - `setup_fin16.sh` hard-links venvf15 into venvf16 and replaces only royalesim (`--link-mode=copy`). It then re-checks venvf15
    under fin15-linux. On pod 32657 that check passed ("venvf15 intact", pins 305aaafc).
  - The trap from FIN15.md applies here too: a wheel reads its build checkout's data whenever that checkout exists. So
    `build16.sh` moves the checkout (`src_fin16` -> `src_fin16_gate`) before installing, and setup refuses to run if
    `src_fin16` exists.

## 1. Verification (all (a), pod 32657)

| check | result |
|---|---|
| cargo gate (`--profile gate --no-fail-fast`) | **1967 passed / 0 failed / 3 ignored**, 363 suites (fin15: 1966 / 0 / 3; +1 = `the_2026_10_19_arm_loads_the_updated_skeleton_ring`) |
| plant `card_table_unread` -> `--test card_table` | red, as it should be: 2 passed / **4 failed**, rc 101 |
| 10-19 arm loads | `Battle(..., cards.CARD_TABLE=client160402017_20261019).card_table()` = `cards-160402017-20261019.1` |
| `setup_fin16.sh` (FREEZE=1) | FIN16_OK: `activate()` pins 3f567607 clean with the embedded table; Hero IW on; CARD_TABLE 10-19; `selected_card_data()` = the 10-19 JSON (and != the 10-06 one); elixir unit 10000; 600-tick icebow battle ran; venvf15 intact |
| pyflakes (venvf16, pod) on `royale_runtime.py`, `royale_heroiw.py`, `smoke_fin16.py`, `freeze_fin16.py` | clean (rc 0) |
| **real `python -m pipeline.rl_royale --smoke`** (ROYALE_RUNTIME=fin16-linux, venvf16, `stepd/cfg/brT10_s107.yaml` = the last config trained on this pod, on fin15) | **SMOKE PASS**: u0000 round trip identical, u0000 W/L/D 4/4/0, u0001 3/5/0, resume check all True, frozen memory encoder bit-identical (`results/smoke_rl.txt`) |

**Smoke deviation.** The smoke had to run on the CPU, because S2 was using the GPU. That needed two changes:
- `learner_device=cpu` on the command line;
- `cpu_ckpts.py`, run in a throw-away `cp -a` copy of `/workspace/cb_arm` (`/workspace/f16/cb_smoke`). It re-saved the config's
  checkpoints with CPU tensors; they were saved on CUDA.

No repo code changed for this. The selector files in cb_arm match HEAD apart from line endings, and the smoke ran with this
commit's two pipeline files laid over them.

## 2. A/B: fin15 vs fin16 on the same harness (J1, stamped strict, K = 0)

**Set-up.**
- **Arms:**
  - A15 = the fin15 wheel 88f3fdcb with `PARITY_TABLE_1019=0`;
  - A16 = the fin16 wheel with `PARITY_TABLE_1019=1`. fights.py `table_for()` then gives a capture stamped from 20261019_0600
    the 10-19 table and every earlier one the 10-06 table.
- **Shared by both arms:** the code tree (HEAD's parity harness, cb22's file list plus parity/w19, metrics, fin16), the chunk
  dirs (`w19/split_export.py`, 8 per cohort), W = 3, window 240.
- `PARITY_FORM_SYM` was unset, so no symmetric-ring emulation ran. `PARITY_FORM_SYM_FROM` keeps its default, 20261019_0600.
- **Exports:**
  - c22 = W19's `attacks22_{0..3}` / `buffs22_{0..3}` (laptop scratch `w19/ex22`).
  - c13 = **re-exported** with `export_list.py`, because W19's attacks13s / buffs13 are gone from the laptop and from every
    pod. It used the same readers over the 638 caplogs13 names. The re-export has births for 405 logs and shields for 110, and
    attacks13.json is 378 MB. All three match the original export.
- **Runner:** `ab_run.sh` (w19/base_run.sh with B=/workspace/f16).
- Paired diffs: `w19/cmpci.py`. Identity: `ident.py`.

| cohort | A15 fin15 | A16 fin16 | paired diff (fights strict in both) [match-bootstrap 95% CI] | up / down |
|---|---|---|---|---|
| **c13** (638 logs, 10-16 .. 10-18 13:15; all pre-patch) | 0.9279 [0.9221, 0.9338], 14,252 fights / 404 matches | 0.9279 [0.9221, 0.9338], 14,252 / 404 | **+0.00000 [0, 0]** | 0 / 0 |
| **c22** (786 logs, 10-18 13:19 .. 10-21 16:13) | 0.9171 [0.9129, 0.9215], 29,617 / 748 | **0.9266 [0.9227, 0.9308]**, 29,638 / 748 | **+0.00949 [+0.00792, +0.01109]** | **339 / 58** (+21 fights gradable only in A16) |
| union | 0.9207 [0.9172, 0.9240], 43,869 / 1,152 | **0.9271 [0.9238, 0.9304]**, 43,890 / 1,152 | **+0.00641 [+0.00531, +0.00753]** | 339 / 58 |

- **A15 reproduces W19's baselines (a).**
  - c13 BASE0: 14,252 / 404, 0.928. Identical.
  - c22 BASE0: 29,615 / 748, 0.917. A15 has 2 more fights and the same score, so the harness or exports moved slightly since
    10-22. Both arms here share those inputs.
- **c13 identity (a): 638 of 638 match results are identical after normalising; 0 of 36,152 fight records differ.**
  - Raw bytes match for only 6 / 638 matches, and they cannot match by construction. Each record carries
    `summary.stamp.path` and `fights[*].stamp.path` (the SIM dir: rsfork_fin15 vs rsfork_fin16) and `summary.seconds` (wall
    time). The 6 raw matches are skipped matches with no stamp.
  - `ident.py` removes exactly those three fields and compares canonical JSON. Every other byte is equal.
- **c22 pre-patch control (a):** the 273 c22 matches before 20261019_0600 are identical after normalising (0 of 15,384 fights
  differ). The 476 post-patch matches differ, as the 10-19 table should make them. 37 post-patch matches are equal byte for
  byte: they were skipped.
- **Where the c22 gain is (a), raw agreement A15 -> A16:**

  | card | before -> after | n |
  |---|---|---|
  | own Skeletons | 0.838 -> **0.886** | 2,566 |
  | opp Skeletons | 0.859 -> **0.943** | 404 |
  | opp Royal Hogs | 0.714 -> 0.766 | 77 |
  | opp Hog Rider | 0.897 -> 0.903 | 533 |
  | own Knight | 0.938 -> 0.944 | 2,068 |
  | own Tesla | 0.919 -> 0.927 | 1,712 |
  | own X-Bow | 0.952 -> 0.955 | 2,324 |
  | opp Blowdart Goblin | 0.920 -> 0.942 | 325 |
  | opp Wall Breakers | 0.887 -> 0.928 | 97 |
  | opp Barbarians | 0.659 -> 0.707 | 41 |

  Full table: `results/cmp_c22.txt`.
- **Cards with n >= 30 that lose** (a; each is 1-2 fights):

  | card | before -> after | n |
  |---|---|---|
  | own Tornado | 0.944 -> 0.942 | 467 |
  | opp Log | 0.983 -> 0.980 | 342 |
  | opp MegaKnight | 0.960 -> 0.956 | 252 |
  | opp Tesla | 0.950 -> 0.944 | 180 |
  | opp Musketeer | 0.978 -> 0.967 | 90 |
  | opp Assassin | 0.776 -> 0.765 | 98 |
  | opp RageBarbarian | 0.888 -> 0.876 | 89 |
  | opp Rage | 0.864 -> 0.852 | 81 |
  | opp RamRider | 0.930 -> 0.912 | 57 |
  | opp Firecracker evo | 0.984 -> 0.969 | 64 |

  The 58 down fights are not dossiered: (b) cascade noise from units that now stand somewhere else; untested.
- **Size against W19's levers (a).** The table gains +0.949 pp on c22. That is more than the formation oracle (ORF, +0.507 pp,
  own Skeletons only) and 9x the R2 symmetric-ring probe (+0.108 pp). (b), not separated: the rest comes from opponent
  Skeletons using the same radius, from the clamp-zone taps the oracle could not set up, and from the update's other 12 values.
- **Still short of the goal.** J1 union 0.927, lower CI 0.924, against the owner's 0.975 lower-CI bar. PLAN.md decision (b)
  stands: Pillar 1 moves to crforge, and fin16 is the fallback and the training engine meanwhile.

## 3. Files in this folder

| file | what |
|---|---|
| FIN16.md | this report |
| patches/0001, 0002 | the two fork commits on fin15 305aaafc (W19, commit 406ffd1) |
| build16.sh | pod build: bundle -> wheel (sha), runtime dirs rsfork_fin15 / rsfork_fin16 (pip --target), cargo gate, plant |
| setup16.sh, ab_run.sh, export_list.py | A/B inputs (chunk dirs), the J1 runner, the c13 re-export |
| ident.py | normalised identity of two J1 runs' match results, before / from the patch stamp |
| setup_fin16.sh, freeze_fin16.py, smoke_fin16.py, build_manifest_fin16.json | the training-pod install (section 0) |
| cpu_ckpts.py | re-saves a config's checkpoints with CPU tensors, in a throw-away tree copy only (the CPU smoke) |
| fin16_chain.sh | W19's earlier chain for the old W19 pod (33591, gone; no result of it landed); superseded by build16.sh + ab_run.sh |
| results/ | CEILING_strict per arm x cohort, cmp_{c13,c22,union}.txt, ident_{c13,c22}.txt, build16.log, cargo results, plant16.log, setup_fin16.log, smoke_rl.txt |

## 4. Not done / open

- K = 8 (perturbed ceiling) was not run on fin16. Every number above is K = 0. W19 measured K0 = K8 on raw agreement to 0.001.
- `fights.py` still defaults to `PARITY_TABLE_1019=0` (it is outside this ticket's write set). A fin16 J1 run must set it to 1.
- `activate()`'s `card_table` stamp hashes the wheel's default embedded table, not the selected arm. Its
  cards_json_fnv1a64 is 803ec02c on both fin15 and fin16. fin15 and fin16 stamps still differ (pins, manifest sha, runtime_id),
  so `require_same` keeps them apart (a, read from the stamps). The stamp field itself is misleading (b; pre-existing).
- No pipeline unit tests were added; `pipeline/tests/` is outside the write set. The 11-id probe above stands in.
