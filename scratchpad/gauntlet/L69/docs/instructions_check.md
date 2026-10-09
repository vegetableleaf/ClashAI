# Instructions.txt check (2026-10-01)

Guide: `icebow/Instructions.txt` (780 lines); `hogeq/Instructions.txt` is a byte-identical copy (`cmp` = identical).
All python checks ran with `CUDA_VISIBLE_DEVICES=-1`. Raw outputs: `scratchpad/gauntlet/L69/docs/help/`.
Nothing was trained, no engine match, no live play, no adb call.

## Commands -> --help / cheapest check (venv the guide names)

| Guide stage | Command | Check | Result |
|---|---|---|---|
| 2 | `icebow\.venv ... -m unittest pipeline.tests.test_obs_contract` | run | Ran 23, OK (ut_obs_contract.txt) |
| 2 | `icebow\.venv ... -m unittest tools.tests.test_tools` | run | Ran 14, OK (ut_tools.txt) |
| 2 | `icebow\.venv ... -m unittest pipeline.tests.test_model_gen pipeline.tests.test_dataset_gen` | run | Ran 16, OK, 204 s (ut_gen.txt) |
| 3/5/7 | sandbox `-m native_core.worker` / `-m native_core.client` | --help | OK: start/status/stop, --stop-vm, --transport {direct,adb}, --avd-name; client has ping |
| 4 | `tools\hf_download.py --dry-run --dest scratchpad\gauntlet\L67\hf` | run (no network) | "DONE (dry run) have 52 would-fetch 0" (hf_download_dryrun_L67.txt); default dest: have 0 would-fetch 52 |
| 4/6B | `tools\hf_to_crawl.py` (deck, --hf, --tags-file, --chunk, --out) | --help | OK (hf_to_crawl.txt) |
| 6/6B | sandbox venv `research\sandbox_tools\replay_batch.py` | --help | OK; --level default 11 (source :85) |
| 6B | PowerShell `foreach ($c in Get-ChildItem ... -Directory -Filter chunk_*)` + relative exe | run with `python -c print(argv)` on 2 owner chunks | args expand to full chunk path + \tags.json |
| 6B | `pilot_select.py` | not run (would rewrite pilot_tags.json); input path hard-coded to scratchpad/gauntlet/L67/hf/replays = tracked | source read |
| 8 | `-m pipeline.dataset_gen` | --help | OK (dataset_gen.txt) |
| 9 | `-m pipeline.train_gen` | --help | OK; defaults epochs 20, grid floor -> guide passes --epochs 4 --grid lattice |
| 9 | `gen_v2/_train_every_epoch.py` | --help | no argparse help; prints usage (needs --out-dir) -- referenced only, not a step |
| 9 | `gen_v2/select_gen_v2.py` (Royale venv) | --help | OK -- referenced only |
| 10 | `-m pipeline.eval_gen` | --help | OK |
| 11 | Royale venv `import royalesim, royalegym, torch, yaml` | run | "royale imports ok 2.11.0+cu128" |
| 11 | `research/ext/Royale/.venv/Scripts/maturin.exe` | exists | yes; rustc 1.98.1 on this box |
| 11 | Royale-venv test `pytest pipeline/tests/test_royale_forms.py` | run, STOPPED by me at 12/14 passed (slow engine tests, CPU contended, not a guide step) | 12 dots, 0 failures before stop |
| 12 | Royale venv `-m pipeline.search_s0` | --help | OK: --gen --opp-gen --s1 --opps --arms --forms-mode {base,deck} --device --workers --threads |
| 13 | Royale venv `run_screen.py` | --help | OK: --only-tags-from --tau --forms-mode --pair --split --noise-off --opp-elixir --action-delay --extrapolate |
| 14 | icebow venv `live_play.py` | --help | OK (live_play.txt): --ckpt --tau --max-seconds --dry-run --overlay --no-record --device --menu-guard --invite-wait --no-ability --matches --friend --nav-dry-run |
| 15 | `git show afa2db3:icebow/Instructions.txt` | git cat-file -t | blob (the old S1 guide; content = HEAD copy, CRLF only) |
| 11 | RoyaleSim commit 369fe33 | git cat-file -t | commit |

## Paths named in the guide

| `tools/hf_download.py` | exists | tracked |
| `tools/hf_manifest.json` | exists | tracked |
| `tools/hf_to_crawl.py` | exists | tracked |
| `tools/tests/test_tools.py` | exists | tracked |
| `scratchpad/gauntlet/L67/hf/replays/part-000000.parquet` | exists | tracked |
| `scratchpad/gauntlet/L67/hf/replays/part-000051.parquet` | exists | tracked |
| `research/sandbox_tools/replay_batch.py` | exists | tracked |
| `scratchpad/gauntlet/L68/generalist/pilot_select.py` | exists | tracked |
| `pipeline/dataset_gen.py` | exists | tracked |
| `pipeline/train_gen.py` | exists | tracked |
| `pipeline/eval_gen.py` | exists | tracked |
| `pipeline/search_s0.py` | exists | tracked |
| `pipeline/live_gen.py` | exists | tracked |
| `pipeline/tests/test_obs_contract.py` | exists | tracked |
| `pipeline/tests/test_model_gen.py` | exists | tracked |
| `pipeline/tests/test_dataset_gen.py` | exists | tracked |
| `pipeline/decks/icebow.yaml` | exists | tracked |
| `pipeline/decks/hogeq.yaml` | exists | tracked |
| `pipeline/rl_royale.yaml` | exists | tracked |
| `scratchpad/gauntlet/L69/gen_v2/train_gen_v2.sh` | exists | tracked |
| `scratchpad/gauntlet/L69/gen_v2/select.sh` | exists | tracked |
| `scratchpad/gauntlet/L69/gen_v2/select_gen_v2.py` | exists | tracked |
| `scratchpad/gauntlet/L68/generalist/screen_gen/run_screen.py` | exists | tracked |
| `scratchpad/gauntlet/L68/generalist/lat26/screens/train_C.jsonl` | exists | tracked |
| `scratchpad/gauntlet/L68/live_reader/live_play.py` | exists | tracked |
| `scratchpad/gauntlet/L68/live_reader/friend_nav.py` | exists | tracked |
| `scratchpad/gauntlet/L68/live_reader/overlay_replay.py` | exists | tracked |
| `scratchpad/gauntlet/L69/nav/templates/manifest.json` | exists | tracked |
| `scratchpad/gauntlet/L69/nav/templates/_build.py` | exists | tracked |
| `scratchpad/gauntlet/L69/reward_plan.md` | exists | tracked |
| `HANDOFF.md` | exists | tracked |
| `scratchpad/gauntlet/L68/selfplay/loadable_decks.json` | exists | tracked |
| `icebow/requirements.txt` | exists | tracked |
| `hogeq/Instructions.txt` | exists | tracked |
| `icebow/data/ghost_pool/pool_env_v1.jsonl` | exists | untracked (gitignored) |
| `icebow/data/pipeline/gen_v1_s0/gen_s0.pt` | exists | untracked (gitignored) |
| `icebow/data/pipeline/gen_dataset_v2.npz` | exists | untracked (gitignored) |
| `scratchpad/gauntlet/L68/live_reader/live_sampler` | exists | untracked |
| `research/ext/Royale/RoyaleSim/tools/extract_{arena,cards,globals}.py`, `data/derived/cards-15.535.json`, `README.md` | exist | tracked in RoyaleSim |
| `research/ext/cr-native-sandbox/{runtime.env.example.ps1, scripts/bootstrap.ps1, doctor.ps1, smoke.ps1, native_core/worker.py, client.py}` | exist | tracked in cr-native-sandbox |
| `C:\Program Files\Netease\MuMuPlayer\nx_device\15.0\shell\adb.exe` | exists (owner box) | hard-coded in live_play.py:38 |

Paths the guide CREATES (do not exist yet by design): `data\hf_crawl\{icebow,hogeq,multi}`, `data\corpus_v6\{icebow,hogeq}`,
`data\corpus_multi`, `icebow\data\pipeline\gen_dataset_mine.npz`, `icebow\data\pipeline\gen_mine_s0\`, `data\reactive\...`
(all under gitignored `data/` rules).

## Facts and their sources

- gen_v1 recipe: HANDOFF.md:166; corpora of gen_dataset_v1/v2 = corpus_v6 icebow + hogeq + corpus_gen_pilot s0-s3 (gen_dataset_v2.json meta "corpora").
- 14,661 replays -> 3,745,692 rows, 4,283 decks, 553 s: scratchpad/gauntlet/L68/generalist/build_v1.out.
- ~1 h/epoch, 836-950 rows/s, GPU peak 3.7 GB: HANDOFF.md:166.
- gen_v1_s0 all-deck val card .603 / tile .216 / gate_bal .710: gen_v1_s0_eval_full.json val_all.
- Wait-label fix 3153fa4, v2 stats: HANDOFF.md:188; gen_v2 not trained: icebow/data/pipeline/gen_v2_s0 absent; chained after R1 (e5e25e8).
- Pilot slice 17,853 replays, 36% evo Elite Barbarians, 11,415 ok, 3.1 GB, ~2.4 h on 4 VM slots: HANDOFF.md:193, pilot_drive.md, convert.log.
- Local drive speed 8.5-15 s/replay: HANDOFF.md:4523 (and 11.4 s: :2524). Icebow HF 766 kept / 603 converted: HANDOFF.md:3984.
- HF parquets tracked in git since 9e574f9; manifest sha256 match (dry-run above).
- RoyaleSim install: RoyaleSim README "Install"; maturin 11 min + cards.json trap: HANDOFF.md:168; Royale venv packages: pip list (maturin, msgspec, numpy, PyYAML, royale*, torch 2.11.0+cu128).
- RoyaleSim 369fe33 + forms (no Hero Ice Wizard): HANDOFF.md:186-187.
- Reactive play 48 matches 687.9 s, gen_v1 12/24 vs gen: scratchpad/gauntlet/L69/rebase_1001_evo/reactive_genv1/summary.json.
- Ghost screen 0.926, 299 matches 732.8 s: rebase_1001_evo/train_tau0.27.out + HANDOFF.md:187; 191/299 tags from crawl2 (pool_env_v1.jsonl "source").
- search_s0 hashes --s1 unconditionally: pipeline/search_s0.py:717 (`sha256(REPO / a.s1)`), default s1_icebow_v6aug_s1.pt (:124).
- Live: reader needs root (/proc/PID/mem), sampler at <device path, local reader config> not pushed by any script (live_play.py:142-146, :342); build 160402012 x86_64: HANDOFF.md:167; ranked ladder path confirmed: HANDOFF.md:182; CPU starvation: HANDOFF.md:169 (LIVE LAG ROOT CAUSE).
- run.py play --student loads S1Model only: icebow/src/clashrl/student_live.py:44-52.
