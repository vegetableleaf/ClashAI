# ENG-FIX4_3 r9 report

Completed UTC: 2026-10-29T14:17:44.547754+00:00

Commands: Git Bash `bash extract.sh off`; laptop `icebow/.venv/Scripts/python.exe -I off_check.py`; Git Bash `bash extract.sh on`; laptop Python `-I compare.py`; Git Bash `bash score.sh`; laptop Python `-I report.py` and `-I verify.py`. Scripts are adapted copies of r8. See extract.sh and pod.sh for exact flags, lists, tables, frames and paths. Four extraction workers, one regen at a time. Pod 32657: WORKERS=12, CPUs 28-53, sequential OFF then ON, SME_LIB=/workspace/crforge_main/5e8089a4/tickprobe/lib, no extra simulation flags; runH.sh defaults retained. No other-worker wait or assign_guard required.

OFF is rebuilt for all seven sets using r8 ON flags plus SME_ZAP_DEAD=1. ON adds only SME_ZD_BLDG=1. fresh2-6 retain only rng_free lines; dev/fresh1 retain all. OFF drift checks compare parsed objects and line text against r8 ON; dev 182050 is additionally checked against its r8 OFF form. Allowed ON fields: r6 fields plus tower_zap and zap_dead.

## Inputs

| Set | OFF rows | ON rows | Changed | OFF SHA256 | ON SHA256 |
|---|---:|---:|---:|---|---|
| dev | 138 | 138 | 0 | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 |
| fresh1 | 9 | 9 | 0 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 |
| fresh2 | 40 | 40 | 0 | 7fe6d9dc45306adae1d008ec4bfae32beea6af03e8bf3a73bf382fa0cf02ee24 | 7fe6d9dc45306adae1d008ec4bfae32beea6af03e8bf3a73bf382fa0cf02ee24 |
| fresh3 | 17 | 17 | 0 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 |
| fresh4 | 78 | 78 | 1 | ceee8bbe33980b2e63979b346cdfc37d8f61b8a2b84c6dab805d9e762dc46f02 | 9ca0171a68442173889c9bd0129bef36fcb304dd17c396d56cce5287111ee3f1 |
| fresh5 | 15 | 15 | 0 | 6b81869d889e22424a308f31092ce51f497c73d04cff5699a6262d4b0dac8c75 | 6b81869d889e22424a308f31092ce51f497c73d04cff5699a6262d4b0dac8c75 |
| fresh6 | 15 | 15 | 0 | 1beeb24f1a7698a1c247b696fc0d5a6ea51cffc3bc94848c8b49890ed89c3c0a | 1beeb24f1a7698a1c247b696fc0d5a6ea51cffc3bc94848c8b49890ed89c3c0a |

OFF drift (off_checks.txt / off_checks.json):
- dev: 138 records; changed versus r8 ON: ['live_play_20261026_182050']
- fresh1: 9 records; changed versus r8 ON: []
- fresh2: 40 records; changed versus r8 ON: []
- fresh3: 17 records; changed versus r8 ON: []
- fresh4: 78 records; changed versus r8 ON: []
- fresh5: 15 records; changed versus r8 ON: ['live_play_20261029_021310']
- fresh6: 15 records; changed versus r8 ON: []

Paired rows: 1; classes: {'fixed': 1}.

| Set / match | OFF counts | OFF first div | ON counts | ON first div | Class | Plants missed |
|---|---|---|---|---|---|---|
| fresh4 / live_play_20261028_155749 | {'exact': 2055, 'div': 89} | 4266 | {'exact': 2144} | None | fixed | [] |

Full paired columns: table.txt / table.json. Every differing play and non-play field: changes.txt. Upload checks: upload_sha256.txt. Completed run logs and results: EF9_*.

## Findings

All specified expectations held; no unexpected changed records; plants missed = [] for every OFF and ON result.
Regressed records: 0. Added flags: 0. Exact-count delta: 89.

## Timings

extracted dev off seconds=390
extracted fresh1 off seconds=34
extracted fresh2 off seconds=305
extracted fresh3 off seconds=102
extracted fresh4 off seconds=557
extracted fresh5 off seconds=138
extracted fresh6 off seconds=168
extracted dev on seconds=750
extracted fresh1 on seconds=114
extracted fresh2 on seconds=670
extracted fresh3 on seconds=217
extracted fresh4 on seconds=1665
extracted fresh5 on seconds=173
extracted fresh6 on seconds=193

- EF9_fresh4_off.log: observed launch-to-collection 132.8s (includes polling/transfer); done EF9_fresh4_off
- EF9_fresh4_on.log: observed launch-to-collection 128.7s (includes polling/transfer); done EF9_fresh4_on
