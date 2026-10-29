# ENG-FIX4_2 r8 report

Completed UTC: 2026-10-29T12:33:45.070317+00:00

Commands: Git Bash `bash extract.sh`; laptop `icebow/.venv/Scripts/python.exe -I compare.py`; `bash wait_r7.sh`; `bash score.sh`; laptop Python `-I report.py`. See scripts for exact flags, lists, tables and frames. Extraction: four workers, one regen at a time. Pod: WORKERS=12, CPUs 28-53, sequential OFF then ON, lib 5e8089a4, no extra simulation flag.

OFF files copied from r7; hash prefixes, counts, and byte equality verified. Equality compares parsed objects and line text. Allowed fields: r6 plus tower_zap. See changes.txt for every differing play and non-play field.

## Inputs

| Set | OFF rows | ON rows | Changed | OFF SHA256 | ON SHA256 |
|---|---:|---:|---:|---|---|
| dev | 138 | 138 | 1 | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 | 539b8b406adf43ebe878abbed25675bf0c4093fb90d58e73528d47961447baf1 |
| fresh1 | 9 | 9 | 0 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 |
| fresh2 | 40 | 40 | 1 | 4296f565bb48a5c6ecfc87394a9554a4248db39ac0bcfea9d45f8b60deca6fa6 | 7fe6d9dc45306adae1d008ec4bfae32beea6af03e8bf3a73bf382fa0cf02ee24 |
| fresh3 | 17 | 17 | 0 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 |
| fresh4 | 78 | 78 | 4 | 8f695c580c42b6ed435e0135ae52973572b5054ca579ea88d2798ec98e291bdc | ceee8bbe33980b2e63979b346cdfc37d8f61b8a2b84c6dab805d9e762dc46f02 |
| fresh5 | 15 | 15 | 0 | 8f4cb92d6d3c6f715235d6e9bf7b38374412b7da9caf08726f1656a2a288f049 | 8f4cb92d6d3c6f715235d6e9bf7b38374412b7da9caf08726f1656a2a288f049 |
| fresh6 | 15 | 15 | 1 | 20ac8e69384bec9534d7d6e14fb11ca0edfab3390122fa0baa04eb00d2b141e4 | 1beeb24f1a7698a1c247b696fc0d5a6ea51cffc3bc94848c8b49890ed89c3c0a |

Rows: 7; classes: {'same_class': 2, 'improved': 1, 'fixed': 4}.

Full paired results: table.txt / table.json. Upload checks: upload_sha256.txt. Wait evidence: wait_r7.log. Run logs and results: EF8_*.

## Findings

dev: unexpected changed=['live_play_20261026_182050'], expected but unchanged=[]
Additional dev change: IceWizard ability at tick 3463 changes source cast_seen to charge_drop and removes dated=own_elixir. OFF and ON both score 1766 exact with no divergence; classification same_class.
Regressed records: 0. Added flags: 0.

Scoring/flag/plant expectation failures: 0.
Exact-count delta summed across changed records: 2633.
All specified scoring and flag expectations held; plants missed = [] for every OFF and ON result.

## Timings

Extraction file timestamps and elapsed seconds: extraction_timings.json. The required r7 wait ran from 10:49:22 UTC to 12:11:09 UTC (see wait_r7.log).
- EF8_dev_off.log: observed launch-to-collection 130.7s (includes polling/transfer); done EF8_dev_off
- EF8_dev_on.log: observed launch-to-collection 134.4s (includes polling/transfer); done EF8_dev_on
- EF8_fresh2_off.log: observed launch-to-collection 144.0s (includes polling/transfer); done EF8_fresh2_off
- EF8_fresh2_on.log: observed launch-to-collection 139.8s (includes polling/transfer); done EF8_fresh2_on
- EF8_fresh4_off.log: observed launch-to-collection 143.1s (includes polling/transfer); done EF8_fresh4_off
- EF8_fresh4_on.log: observed launch-to-collection 145.0s (includes polling/transfer); done EF8_fresh4_on
- EF8_fresh6_off.log: observed launch-to-collection 129.8s (includes polling/transfer); done EF8_fresh6_off
- EF8_fresh6_on.log: observed launch-to-collection 143.1s (includes polling/transfer); done EF8_fresh6_on
