# L64 cleanup loop -- scratchpad de-clutter before S0 -> S1

Owner ruling: "before you move from S0 to S1, make sure to clear out any stale data/files so things don't get too cluttered."
Guardrails honoured: nothing under any `*/data/` touched or listed; nothing outside `scratchpad/` deleted; no `git add -A`; no commit/push; backup zip verified before any delete.

## 1. Inventory (before)

`du -sh scratchpad` = **1.1G**. Files: 5,071 total; 1,797 git-tracked; `git status --porcelain -- scratchpad`: 6 tracked-modified, 1,644 untracked entries (dirs collapse to one entry). `git status --porcelain | grep -c data/` = 0.

Top-level (sorted):
- gauntlet 812M | bb 92M | sweep 31M | adv 25M | ab2 18M | ab 18M | distill_corpus_big.npz 13M | dc_shard1..5.npz ~2.3M each | 25 x root `*.pt` (1.9M each) | distill_corpus.npz + distill_corpus_WRONGDECK.npz 1.7M each | rs_ceil.json 1.3M | ceiling/ 113K (10 files) | __pycache__/
- root files: 465 (150 json, 136 txt, 45 md, 39 log, 25 py, 25 pt, 24 sh, 11 out, 8 npz, 2 yaml)

gauntlet/*: ext 501M | L45 51M | L46 43M | L58 35M | L52 33M | L2 33M | L62 32M | L63 19M | L3 8.0M | L51 6.2M | L59 5.7M | L21 4.3M | L40 3.8M | L53 3.1M | L48 2.9M | L16 2.5M | L47 2.1M | L43/L31 2.0M | 17 dirs at ~1.9M (one .pt each: L7-L11, L24, L25, L32-L39, L42) | remainder < 600K each | L2_smoke_yolo26.log 120K, L2_screen.ps1, L2_smoke_yolo26.log.err (0 B)

gauntlet/ext/* (63 entries): corpus_v3 245M (KEEP, S1 corpus; holds tags_hogeq.json + tags_icebow.json -- the only tags_*.json in scratchpad) | engine_view 120M | batch_v2 74M (KEEP) | dump 33M | batch 9.4M | replay_00LYPLJLC80L_run1.json 8.9M | re 5.1M | replay_08CPVRRR8PYC_run1.json 2.9M | replay_00LYPLJLC80L_full_view.html 2.6M | replay_08CPVRRR8PYC_view.html 804K | ~50 small .log/.err/.ps1/.json/.md files (< 160K each)

Checkpoints (`*.pt`) in scratchpad: 101 files. 25 at root, 15 sweep/, 13 adv/, 9 ab/, 9 ab2/, 9 L62/smoke*, 2 L40, 2 L21, 1 each in 17 L-dirs. ALL KEPT per rule (never delete weights) -- so ab/ab2/adv/sweep are cleaned at file level, not directory level.

## 2. Reference sets consulted (what must survive)

- HANDOFF.md (2,671 lines) last 400 lines, refs: L61/build_bc_v2.py, L61/crawl_icebow_wave4.log, L62/HANDOFF_prespllit_backup.md, L63/* (many), ext/corpus_v3/tags_{icebow,hogeq}.json. (`ext/engine_view/live_selftest_full.json` and `live_artifact_{check,headless}.json` are cited at HANDOFF lines 2073/2152 -- outside the 400-line window, but they are the 5cs.50 numbers, so KEPT anyway.)
- GAUNTLET_LOG.md (1,341 lines) last 150 lines, refs: L62/HANDOFF_prespllit_backup.md, L62/engine_view.py, L63/proposal.html, L63/{lit_game_ai,...}.md.
- Tracked code (icebow/, hogeq/, pipeline/, research/*.py, research/sandbox_tools/) refs: L46/hand_slot_calib.py, L59/reward_ref.py + **L59/reward_ref.npy** (test_geometry_wiring.py), **L12/stage_timer.json** (latency_stage_timer.py usage line), L20 (docstring, dir), **scratchpad/fix4.py** (train_sim_ppo.py comment; the file does not exist at root -- nothing to keep), L61/build_bc_v2.py, L58/impl_geometry.md, L63/s0/*.md, ext/batch_v2/replay_*.json (pipeline/tests/test_obs_contract.py primary), ext/replay_*.json (same test's FALLBACK, only used when batch_v2 is empty -- batch_v2 has 213 files incl. replay_00LYPLJLC80L.json and replay_08CPVRRR8PYC.json), ext/batch (replay_batch.py default OUTPUT dir, not read), **ext/usable_replays.json** (replay_batch.py tag list; HANDOFF 836).
- Runtime check of the L62k visualizer: `scratchpad/gauntlet/L62/live_view.py` has `OUT_DIR = EXT / "engine_view"` -- engine_view/ is its OUTPUT directory; it imports from L61/ and L62/ and reads recordings from the path given on the CLI. `icebow/tools/live_view.py` does not exist. Nothing reads engine_view/ at runtime.

## 3. Classification

KEEP (never touched):
- `ext/corpus_v3/` 245M (S1 corpus + the two tags_*.json), `ext/batch_v2/` 74M, `ext/re/` 5.1M (bridge_v2 asm annotations + `libnative_core_probe.v2.so`, the deployed bridge binary per HANDOFF 5cs -- UNSURE whether it exists elsewhere, so KEEP), `ext/usable_replays.json`, `ext/cr_sandbox_internals.md`, all `ext/*.ps1` (tiny scripts), `ext/engine_view/*.json|*.py|*.log` (7.6M: live_payload json = the published artifact payload, selftest/artifact/rule_sweep results cited in 5cs.50).
- `gauntlet/L62/`, `L63/`, `L64/` whole. In `L1..L61`: every `*.md`, `*.py`, `*.pt`, plus `*.sh`, `*.ps1`, `*.yaml`, `*.npy` (instruments/config; 26 small files), `L12/stage_timer.json`, `L61/crawl_icebow_wave4.log`, `L17/wiki_Hidden_card_stats` (odd extensionless wiki dump, unsure -> keep). `gauntlet/L2_screen.ps1`.
- Root: all 25 `*.pt`, all 25 `*.py` (incl. `_an.py`-style probes -- instruments), `cfg_distill.yaml`, `cfg_search.yaml`, `run_controls.sh`, all 37 `report_L47b..L62l.md` (loop reports = records; 6 tracked; not in the lead's `_*.md` delete pattern).
- All 101 `*.pt` checkpoints in scratchpad stay in place (listed in the manifest as KEEP), which means `ab/ ab2/ adv/ sweep/` survive as directories holding only their .pt files.

DELETE (old-pipeline artifacts, loop bulk L1-L61, regenerable renders):
- Root: `_*.sh|.out|.txt|.md`; every root `*.json`, `*.txt`, `*.log`, `*.out`, `*.npz` (rs_*.json rollout-search results, log_*/hlog_* run logs, dc_shard*.npz, distill_corpus*.npz, reward_ledger etc. -- none referenced by the tails or code); `__pycache__/`; `ceiling/` (10 json/log files from the L4x ceiling probe).
- `ab/ ab2/ adv/ sweep/ bb/`: every non-.pt file (bb = 92M of L2-era frame PNG/audio).
- `gauntlet/L1..L61`: files with ext json, jsonl, txt, log, pyc, png, jpg, csv, err, out, npz, mp4, progress (except the two referenced files above).
- `gauntlet/L2_smoke_yolo26.log` + `.log.err`.
- `ext/engine_view/*.mp4|*.png` (renders; regenerable from batch_v2 recordings + L62/engine_view.py), `ext/dump/` binaries + logs (elf/bin/txt/log/json/out/err: libg memory dumps regenerable via dump_libg.sh on the guest; its .py/.sh scripts KEPT), `ext/batch/` (v1, superseded), `ext/replay_*_run1.json`, `replay_08CPVRRR8PYC_run2.json`, `ext/replay_*view.html` (regenerable via replay_view.py), `ext/*.log|*.err|_t_*.txt` (service/probe logs).

## 4. Manifest + backup (before any delete)

- Manifest: `scratchpad/gauntlet/L64/cleanup_manifest.csv` (builder `build_manifest.py`, same dir). 5,075 files: **DELETE 3,297 (549,278,290 B)**, KEEP 1,778 (578,043,190 B, of which corpus_v3 + batch_v2 = ~319 MB and 101 checkpoints = ~195 MB). 1,435 of the DELETE files are git-tracked (`git ls-files`), 1,862 untracked. Zero `.md/.py/.sh/.yaml/.c/.pt` files in the DELETE set outside the root `_*` pattern (checked).
- DELETE by extension: json 2,217 | txt 439 | log 203 | png 200 | pyc 40 | elf 36 | err 29 | sh 23 (all root `_*.sh`) | jsonl 20 | bin 19 | out 18 | csv 14 | npz 13 | md 8 (all root `_*.md`) | mp4 7 | html 2 | progress 2 | wav 1.
- DELETE bytes by area: ext 177 MB (engine_view renders 112 MB, dump 33 MB, batch v1 9.4 MB, loose replay json/html 15 MB) | bb 96 MB | L45 53 MB | L46 44 MB | L58 36 MB | L2 34 MB | L52 32 MB | distill_corpus_big.npz 13 MB | L3 8 MB | dc_shard*.npz 12 MB | rest < 6 MB each.
- Backup: `C:\Users\benpe\ClashBot_archive\scratch_2026-09-06.zip` -- **360,391,790 B**, **3,297 entries == 3,297 DELETE rows**, all 3,297 entry sizes equal the manifest bytes, `testzip()` clean. Spot checks (seed 64): L52/simbatch_hidden/replay_00LYPLCUGYJ2.json 12,864 = 12,864 = 12,864; ext/batch/replay_092PPVY0Q0CR.json 56,003 x3; L52/simrec_corner/replay_00LYPLJLC80L.json 1,784,310 x3. Script: `backup_zip.py`.

## 5. Deletion (step 4) and after-inventory (step 5)

Script `do_delete.py`: re-checked every DELETE path is present in the verified zip before touching anything (refuses otherwise), `git rm -q --cached --pathspec-from-file=_rm_pathspec.txt` for the 1,435 tracked paths (rc 0; the pathspec file is kept in L64/ as the record), `os.remove` on all 3,297 (0 errors), then pruned 47 now-empty directories (`__pycache__`, `ceiling`, `bb/frames`, `ext/batch`, `L1`, `L12`, `L14`, `L18`, `L52/simbatch_*`, ...). Nothing outside the manifest was removed. Helper files `_tracked.txt`, `_delete_paths.txt`, `_rm_pathspec.txt` in L64/ were not in the manifest so they stay (tiny).

| metric | before | after |
|---|---|---|
| `du -sh scratchpad` | 1.1G | **557M** |
| files under scratchpad | 5,071 (5,075 incl. the 4 L64 files created here) | **1,789** |
| bytes in DELETE set | 549,278,290 | 0 |
| `git status --porcelain` total | ~1,650 | 1,605 (of which **1,435 are staged `D` deletions** waiting for the lead's commit; 168 `??` in scratchpad; 2 `??` outside) |
| tracked-modified in scratchpad | 6 | 0 (all six were in the DELETE set) |
| `git status --porcelain \| grep -c data/` | 0 | **0** |
| `*.pt` in scratchpad | 101 | 101 |

Kept-set sanity after delete: corpus_v3 7 entries (245M), batch_v2 213 files (74M), ext/re 5.1M incl. `bridge_v2/libnative_core_probe.v2.so`, ext/engine_view 7.4M (json/py/log only), ext/dump 28K (scripts + .c sources), L59/reward_ref.npy, L61/crawl_icebow_wave4.log, ext/usable_replays.json all present. Remaining: gauntlet 425M | sweep 29M | adv 25M | ab2 17M | ab 17M | 25 root .pt. Note `gauntlet/L12/stage_timer.json` (cited in `latency_stage_timer.py`) never existed -- the citation is an example output path; L12 held only two `stage_timer_smoke_*.json` (bulk, deleted, in the zip).

Outside scratchpad (LISTED ONLY, not touched):
- `icebow/HANDOFF.md` -- untracked, **0 bytes**, created Sep 5 09:45; an empty stray (probably a mis-pathed Write). Safe for the lead to delete.
- `pipeline/dataset.py`, `pipeline/tests/test_dataset.py` -- untracked, new S0/S1 code; not cleanup material, the lead should stage them by name.
- `research/CR_ENGINE_EXTRACTION_REVIEW.md` from the session-start git status no longer exists (already handled by someone).
- `research/ext/`, `*/data/`, `.venv`: not inspected.

## 6. Proposed .gitignore lines (NOT applied)

Current `.gitignore` already has `__pycache__/`, `*.pt` (so no checkpoint in scratchpad is tracked: 0 of 101), `research/ext/`. It does not cover scratch bulk, which is why 1,435 L1-L61 result files were committed over time and 1,644 untracked entries accumulated. Proposed additions:

```
# scratchpad: instruments (*.md, *.py, *.sh, *.ps1, *.yaml) stay trackable; bulk results do not
scratchpad/gauntlet/ext/          # corpora (corpus_v3 245M, batch_v2 74M), recordings, renders, RE dumps -- too large for git, regenerable
!scratchpad/gauntlet/ext/*.md     # cr_sandbox_internals.md and future notes
!scratchpad/gauntlet/ext/*.ps1
!scratchpad/gauntlet/ext/usable_replays.json   # the 8K tag list replay_batch.py reads
scratchpad/*.json
scratchpad/*.txt
scratchpad/*.log
scratchpad/*.out
scratchpad/*.npz
scratchpad/_*                     # loose _*.sh/.out/.txt/.md scratch
scratchpad/gauntlet/L*/**/*.json  # loop bulk; note L63/proposal.html and *.md/*.py remain trackable
scratchpad/gauntlet/L*/**/*.jsonl
scratchpad/gauntlet/L*/**/*.png
scratchpad/gauntlet/L*/**/*.mp4
scratchpad/gauntlet/L*/**/*.npz
scratchpad/gauntlet/L*/**/*.log
scratchpad/gauntlet/L*/**/*.txt
scratchpad/gauntlet/L*/**/*.csv
scratchpad/gauntlet/L*/**/*.err
scratchpad/gauntlet/L*/**/*.out
scratchpad/ab/ scratchpad/ab2/ scratchpad/adv/ scratchpad/sweep/ scratchpad/bb/   # one line each; hold only .pt now
```
Caveat: 23 tracked `*.json` remain under L62/L63 (kept dirs); an ignore rule does not untrack them, and `ext/corpus_v3/tags_*.json` is a real input for S1 -- if the lead wants tags tracked, add `!scratchpad/gauntlet/ext/corpus_v3/tags_*.json` (2 files) explicitly. Since the ext/ tags and batch_v2 recordings are read by `pipeline/tests/test_obs_contract.py`, ignoring ext/ means a fresh clone will skip/fail that test -- that is already the case today (ext/ was never committed), so nothing changes.

## 7. Summary

1. Bytes freed: **549,278,290 (524 MB)**; `du` 1.1G -> 557M.
2. Files deleted: **3,297** (1,435 tracked via `git rm --cached`, staged as `D` for the lead's commit; 1,862 untracked); 47 empty dirs pruned.
3. Files kept: 1,778 -- corpus_v3, batch_v2, tags_*.json, L62/L63/L64 whole, every md/py/sh/ps1/yaml/npy in L1-L61, all 101 `.pt`, 37 root `report_L*.md`, 25 root `.py`, ext/re (bridge binary + asm), ext/engine_view json results, ext/usable_replays.json.
4. Backup: `C:\Users\benpe\ClashBot_archive\scratch_2026-09-06.zip`, 360,391,790 B, 3,297 entries, all sizes verified, testzip clean. Restore any path with `zipfile` by its manifest path.
5. Manifest: `scratchpad/gauntlet/L64/cleanup_manifest.csv` (path,bytes,class,action,reason; 5,075 rows).
6. `git status | grep data/` = 0 before and after; nothing under `*/data/`, `research/`, `.venv`, `.git` touched; no commit, no push, no `git add -A`.
7. Unsure -> kept: `ext/re/` (is `libnative_core_probe.v2.so` also in research/ext? not checked -- research/ off-limits), `ext/engine_view/live_payload_*.json` (7.3 MB artifact payloads), `sweep/cfg_*.yaml` (5 x 194K config copies), `L17/wiki_Hidden_card_stats`, root `report_L*.md` (31 untracked -- the lead may want to track or ignore them).
8. Judgement calls the lead should know: `ext/replay_*_run1.json` (v1 recordings) deleted because batch_v2 holds `replay_00LYPLJLC80L.json`/`replay_08CPVRRR8PYC.json` and the test's fallback to `ext/replay_*.json` only fires when batch_v2 is empty; engine_view renders (mp4/png, 112 MB) deleted as regenerable from `L62/engine_view.py` + batch_v2 -- HANDOFF 5cs.43 line 1660 still points the owner at `00LYPLJLC80L_s1_full_readout_tick1591.png`, which is now only in the zip.
9. Outside scratchpad, listed only: `icebow/HANDOFF.md` is an empty 0-byte stray; `pipeline/dataset.py` + its test are new untracked S1 code.
10. Proposed .gitignore additions in section 6 -- not applied.

STATUS: complete
