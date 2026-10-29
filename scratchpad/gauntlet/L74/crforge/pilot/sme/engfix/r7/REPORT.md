# ENG-FIX4_1

Commands (Git Bash, from r7): `bash extract.sh`; `python.exe -I compare.py`; `bash score.sh`; `python.exe -I table.py`. Python is `C:/Users/benpe/ClashBot/icebow/.venv/Scripts/python.exe`. Exact flag sets, lists and tables are in extract.sh and timings.txt; exact SSH/nohup commands are in pod.sh. Extraction used four workers, one regeneration at a time. All pod runs used WORKERS=12, CPUs 28-53, one run at a time, library `/workspace/crforge_main/5e8089a4/tickprobe/lib`; B alone adds SME_BANNER_GIVEN=1.

OFF checks: all passed. Fresh2 and fresh4 changed only the two permitted NEAR_BIGGER2 matches; fresh6 byte equality passed. Full hashes/counts: off_checks.txt. ON field gate passed; changed-record details: changes.txt.

| Set | Records | OFF SHA256 | ON SHA256 | Changed |
|---|---:|---|---|---:|
| dev | 138 | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 | d91583504174f5d00381ebdf4d8b952371f35e82536e164ce05ab407025fe0b7 | 0 |
| fresh1 | 9 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 | 564fdb24d3dd4fbed739fee046dbfcec3659c1f4027034b3d7cdff3f6c146a23 | 0 |
| fresh2 | 40 | 4296f565bb48a5c6ecfc87394a9554a4248db39ac0bcfea9d45f8b60deca6fa6 | 4296f565bb48a5c6ecfc87394a9554a4248db39ac0bcfea9d45f8b60deca6fa6 | 0 |
| fresh3 | 17 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 | a450d5a3630c5d96250936b4b20863af3250c1895438c5e522fd584af587a749 | 0 |
| fresh4 | 78 | 8f695c580c42b6ed435e0135ae52973572b5054ca579ea88d2798ec98e291bdc | 8f695c580c42b6ed435e0135ae52973572b5054ca579ea88d2798ec98e291bdc | 0 |
| fresh5 | 15 | 8f4cb92d6d3c6f715235d6e9bf7b38374412b7da9caf08726f1656a2a288f049 | 6b81869d889e22424a308f31092ce51f497c73d04cff5699a6262d4b0dac8c75 | 1 |
| fresh6 | 15 | 20ac8e69384bec9534d7d6e14fb11ca0edfab3390122fa0baa04eb00d2b141e4 | 20ac8e69384bec9534d7d6e14fb11ca0edfab3390122fa0baa04eb00d2b141e4 | 0 |

All uploads matched local and remote SHA256; see upload_sha256.txt.

Extraction UTC: 2026-10-29T09:29:19Z to 2026-10-29T09:58:47Z. Per-regeneration starts: timings.txt.
Scoring UTC: 2026-10-29T09:59:53Z to 2026-10-29T12:05:53Z. Per-run starts and collection times: score_timings.txt.

| Table | Set | Rows | Identical | Fixed | Regressed | Improved | Same class |
|---|---|---:|---:|---:|---:|---:|---:|
| banner | dev | 138 | 138 | 0 | 0 | 0 | 138 |
| banner | fresh1 | 9 | 9 | 0 | 0 | 0 | 9 |
| banner | fresh2 | 40 | 40 | 0 | 0 | 0 | 40 |
| banner | fresh3 | 17 | 17 | 0 | 0 | 0 | 17 |
| banner | fresh4 | 78 | 78 | 0 | 0 | 0 | 78 |
| banner | fresh5 | 15 | 14 | 1 | 0 | 0 | 14 |
| banner | fresh6 | 15 | 15 | 0 | 0 | 0 | 15 |
| zapdead | dev | 0 | 0 | 0 | 0 | 0 | 0 |
| zapdead | fresh1 | 0 | 0 | 0 | 0 | 0 | 0 |
| zapdead | fresh2 | 0 | 0 | 0 | 0 | 0 | 0 |
| zapdead | fresh3 | 0 | 0 | 0 | 0 | 0 | 0 |
| zapdead | fresh4 | 0 | 0 | 0 | 0 | 0 | 0 |
| zapdead | fresh5 | 1 | 0 | 1 | 0 | 0 | 0 |
| zapdead | fresh6 | 0 | 0 | 0 | 0 | 0 | 0 |

Per-match columns and non-identical match lists: table_banner.txt/.json and table_zapdead.txt/.json.

Expectations: all held; plants.missed=[] on every result.

banner: fresh5 live_play_20261029_004719: A {'exact': 1210, 'div': 570}, first_div=2573 -> new {'exact': 1780}, first_div=None; fixed.
zapdead: fresh5 live_play_20261029_021310: A {'exact': 1660, 'div': 105}, first_div=1986 -> new {'exact': 1765}, first_div=None; fixed.

STATUS: DONE
