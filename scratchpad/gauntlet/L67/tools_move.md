# L67 tools move -- progress log

Task: move HF download/convert/degrade/merge scripts from scratchpad/gauntlet/L67 to repo-root tools/,
no hard-coded paths; add ultralytics+polars to requirements. No git staging, no network, no engine.

## Log
- started; tools/ did not exist; this file did not exist (fresh start).

## Facts checked before writing (all (a) verified)
- `git check-ignore -v scratchpad/gauntlet/ext/hf` -> NOT ignored (exit 1; `scratchpad/gauntlet/ext` has 11 tracked files,
  e.g. `ext/crawl_hf_icebow/dedupe_report.json`). So the preferred default is NOT usable.
- Ignored alternatives: `data/hf/...` and `data/hf_crawl/icebow/battles.csv` -> ignored by `.gitignore:19 data/`
  (repo-root `data/` does not exist yet; the .gitignore comment says datasets live under `data/`).
- DECISION: download default `--dest data/hf` (files land at `data/hf/replays/part-*.parquet`); converter default
  `--hf data/hf/replays`, `--out data/hf_crawl/<deck>`. Both repo-root, gitignored. My own tests never write there
  (temp dirs only), per the no-writes-under-data rule.
- Manifest: 104 files, 52 under `replays/` (825,394,311 bytes), 52 under `actions/`; per-file keys bytes/path/rows/sha256.
- Venvs: icebow ultralytics 8.4.107, polars 1.43.0; hogeq ultralytics 8.4.107, polars 1.43.2 (pip show). Neither
  requirements.txt lists them. Only repo imports of polars are the scripts being moved.
- `pipeline.vocab` / `obs_contract` / `dataset` are repo-relative already (REPO = parents[1] of pipeline/*).

## Files written
- tools/__init__.py, tools/tests/__init__.py, tools/README.md
- tools/hf_download.py (stdlib port of _hf_dl.sh: --manifest/--dest/--prefix/--base-url/--retries/--timeout/--dry-run;
  downloads to <file>.part, checks size+sha256, renames; bad -> deleted, `DONE ok N bad M`, exit 1 if bad)
- tools/hf_manifest.json: `cp` + `cmp` -> byte-identical, sha256 ffcf5b2e...99fc both (a)
- tools/hf_to_crawl.py (from hf_to_crawl_deck.py): positional deck, --hf (default data/hf/replays), --out (default
  data/hf_crawl/<deck>), --dedupe-against. DECISIONS: default crawl missing -> note + skip; an EXPLICIT
  --dedupe-against that lacks the csvs -> clean SystemExit (user asked for it, silent skip would hide a typo); empty
  --hf folder -> clean SystemExit (old scripts silently wrote empty csvs); dedupe_report.json gains "dedupe_against".
  Still writes tags_a.json/tags_b.json like the sibling.
- tools/build_degraded.py: only REPO parents[3] -> parents[1] + docstring. tools/merge_aug.py: docstring only (no paths).
- TRAP FOUND (a): ultralytics requires `torch>=1.8.0` (importlib.metadata). A fresh `pip install -r requirements.txt`
  run BEFORE the CUDA torch install would pull a CPU-only torch from PyPI -- the exact thing the requirements comment
  warns about. Requirements comment must say: install CUDA torch first.

## Checks
- py_compile: all 6 new .py files OK (a). `--help` rc 0 for hf_download, hf_to_crawl, build_degraded, merge_aug (a).
- PARITY on real data (a): copied scratchpad/gauntlet/L67/hf/replays/part-000000.parquet (5,000 replays) to the session
  temp dir; ran OLD hf_to_crawl.py vs NEW `tools/hf_to_crawl.py icebow` (both dedupe vs icebow crawl2, 1,890 keys):
  41 kept each; battles.csv, plays_ext.csv, tags.json byte-IDENTICAL (cmp). OLD hf_to_crawl_deck.py hogeq vs NEW
  `tools/hf_to_crawl.py hogeq` (882 keys): 2 kept (both cannon->tesla alias); battles/plays_ext/tags/tags_a/tags_b
  byte-IDENTICAL. So the new icebow filter == the old icebow-only filter on 5,000 real replays, not just synthetic.
- Requirements: added `ultralytics>=8.4.107` and `polars>=1.43.0` (+ a 2-line "install torch BEFORE -r" note) to
  icebow/requirements.txt and hogeq/requirements.txt. hogeq venv satisfies both (ultralytics 8.4.107, polars 1.43.2) (a).
- UNITTEST (a): `icebow\.venv\Scripts\python.exe -m unittest tools.tests.test_tools` -> Ran 13 tests in 2.2 s, OK.
  Covers: dry-run (in-process with urlopen mocked to raise -> never called; and CLI subprocess) lists have/would-fetch,
  ignores actions/, creates nothing; resume skip when size+sha match (urlopen never called); corrupt local file
  refetched (file:// base URL, offline); bad sha -> `DONE ok 1 bad 1`, rc 1, bad file + .part removed; path traversal
  rejected; icebow yaml rule == old ICEBOW set, aliases {} and same accept/reject on 6 synthetic decks; hogeq alias
  cannon->tesla read from yaml; synthetic 3-replay parquet: 1 kept (4 play rows incl. ability), 1 unpositioned skip,
  1 non-deck ignored, dedupe skipped with a note when the default crawl is missing; --dedupe-against drops the
  duplicate; explicit-missing dedupe dir / empty --hf / unknown deck -> SystemExit; all 4 --help; imports clean.
- REAL dry run (a): `tools/hf_download.py --dry-run --dest scratchpad/gauntlet/L67/hf` -> `have 52 would-fetch 0`
  (the owner's existing 825 MB download is recognised as complete, sha256 verified). Default-dest dry run ->
  `would-fetch 52`, and repo-root `data/` still does not exist afterwards (dry run writes nothing).
- NOT tested (b): a real HuggingFace download (network forbidden in this task); build_degraded / merge_aug on real
  datasets (only --help/import; their bodies are byte-for-byte the old ones apart from REPO parents[3]->parents[1]).

## Deleting old copies (all new checks passed)
- Deleted (plain rm, not git rm) the 6 files: L67/_hf_dl.sh, hf_manifest.json, hf_to_crawl.py, hf_to_crawl_deck.py,
  build_degraded.py, merge_aug.py. git status now shows them ` D`, `icebow|hogeq/requirements.txt` ` M`, `tools/` `??`.
  Nothing staged. tools/__pycache__ is ignored (!!). grep for owner paths (benpe, C:/Users, /c/Users) in tools/: none (a).
- Re-ran the unittest suite after deletion: 13 tests OK (a) -- tests do not depend on the old files.

## Remaining references to the OLD paths (reported, NOT edited)
- icebow/Instructions.txt:211,223,236,317,318,575,614,615 (being rewritten by the other author)
- hogeq/Instructions.txt:211,223,236,317,318,575,614,615 (same text as icebow's; not touched per "no Instructions.txt")
- HANDOFF.md:2661,3298,3306,3332 ; GAUNTLET_LOG.md:1595 (historical)
- scratchpad/gauntlet/L67/run_icebow_v6aug.sh:11,14 (old run script; now points at deleted build_degraded.py/merge_aug.py)
- scratchpad/gauntlet/L67/instructions_inventory.md:31,39,50,51,52,85,86,134 ; e1_engine_rl_design.md:89,172 ;
  hero_ability_data.md:41 ; _sec95.md:5 ; _sec96.md:5 ; _sec97.md:24 ; _ins96.py:19 ; s1_v6aug/merge_aug.out:2,5 (historical)
- pipeline/decks/hogeq.yaml cites scratchpad/gauntlet/L67/hf_subs_placement.py -- that file was NOT moved and still exists.

## New commands for the guide (from the repo root)
  icebow\.venv\Scripts\python.exe tools\hf_download.py --dry-run
  icebow\.venv\Scripts\python.exe tools\hf_download.py                      (-> data\hf\replays\part-*.parquet)
  icebow\.venv\Scripts\python.exe tools\hf_to_crawl.py icebow               (-> data\hf_crawl\icebow)
  icebow\.venv\Scripts\python.exe tools\build_degraded.py icebow --corpus scratchpad\gauntlet\ext\corpus_v6\icebow --out scratchpad\gauntlet\L67\s1_dataset_v6_degraded_s0.npz --seed 0
  icebow\.venv\Scripts\python.exe tools\merge_aug.py --clean icebow\data\pipeline\s1_dataset_v6.npz --degraded scratchpad\gauntlet\L67\s1_dataset_v6_degraded_s0.npz --out icebow\data\pipeline\s1_dataset_v6aug.npz
  Owner's existing download: add `--dest scratchpad\gauntlet\L67\hf` (download) / `--hf scratchpad\gauntlet\L67\hf\replays` (convert).

STATUS: complete
