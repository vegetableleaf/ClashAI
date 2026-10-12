# APKTABLES v2

Offline, private device/APK table extraction and SIM data comparison. Python 3.11+,
the standard library, and local Git only. No Java, network, simulator execution,
installation, or live-script changes. Leave generated files under `out/`;
the local `.gitignore` excludes every decoded table, parser snapshot and report.

```powershell
python scratchpad/gauntlet/L74/apktables/check_build.py share/clashroyale_160402012_kit/apk --label 160402012
python scratchpad/gauntlet/L74/apktables/check_build.py share/clashroyale_160402012_kit/apk --device-update scratchpad/gauntlet/L74/apktables/out/device_update_20261012/update --old-table research/ext/Royale/RoyaleSim/data/derived/cards-15.535.json --out scratchpad/gauntlet/L74/apktables/out/device_builds --label device-20261012
python scratchpad/gauntlet/L74/apktables/verify.py
python scratchpad/gauntlet/L74/apktables/verify_device.py
```

`--device-update` takes the already-pulled `update/` directory. Each present
CSV/TOML file replaces its APK counterpart completely; absent files fall back
to the APK. A corrupt present update fails the audit and preserves the previous
baseline. New update tables are included. `extraction.json` records compressed
and decoded hashes, each file's source, replaced APK evidence, update metadata
hashes and the effective fingerprint. Every APK fallback is listed in the report.
Only CSV/TOML under `csv_*` is decoded; graphics/audio are counted but not copied.

The 2026-10-12 pull has 693 files, including 73 table files. Its effective set
has 424 tables: 73 device files and 351 APK fallbacks. **The pull has no
rarities.csv**: its effective multiplier ladder is explicitly an APK fallback.
The previous APK-only X-Bow comparison was stale; this device set has damage 24.

`per_level.json` and `REPORT.md` include owner levels (Knight/X-Bow/Rocket/
Tornado/Tesla 16, Ice Wizard and its hero form 14, Skeletons/Log 15) and a
separate row at level 15 for each top-60 opponent. Scaling is
`floor(base_stat * PowerLevelMultiplier / 100)` using the stat-bearing object's
Rarity and unified level offset, never a hardcoded growth factor or unlock
rarity. X-Bow's object is Common despite its Epic card rarity: L11 is
`floor(24 * 256 / 100) = 61`. Related units use their own rarity. HP excludes
shields, and damage is per primary hit; damage-over-time fields remain labelled
DPS, since a runtime tick schedule is outside this table audit. Null is not zero.

The pull helper is a separate, explicitly invoked read-only convenience:

```bash
bash scratchpad/gauntlet/L74/apktables/pull_device_update.sh
# Optional override if the device stores it elsewhere:
bash scratchpad/gauntlet/L74/apktables/pull_device_update.sh /data/user/0/com.supercell.clashroyale/update
```

It calls the existing L68 adb wrapper with `MSYS_NO_PATHCONV=1`, converts the
local destination for Windows adb, and writes a fresh ignored `out/` directory.
It defaults to `/data/data/com.supercell.clashroyale/update`; access must already
be available. It never enables root, remounts, changes permissions, or starts the
game. Running `check_build.py` never invokes adb or contacts the device/network.

Each invocation creates an immutable timestamped run in `out/builds/`.
`out/builds/latest.json` points to its report and baseline snapshot. On the
first run there is no previous build; subsequent runs print exact normalized
card changes and added/removed/changed table hashes. A repeated identical
APK set should show no changes. Failed extraction/normalization preserves the
previous baseline and writes `ERROR.json`. Level violations return exit 2;
ordinary failures return 1; a report with disclosed normalization limitations
returns 0. A report is not a statement of complete mechanic support.

Options include `--previous path/to/snapshot.json`, repeated `--old-table`,
`--selected-table`, `--census`, `--pro2`, `--live-options`, `--sim-repo`, and
`--parser-ref`. Custom `--out` directories must remain under this tool's `out/`.
Use separate output roots for independent build series. No baseline is deleted.

The default selected reference is the 0.1.33 source table
`data/derived/cards-160402017-20261006.json` at local commit
`cacb7005f0e441797c533e91ab4f44820f9919d4`. This is the table named by
`pipeline.royale_heroiw.selected_card_data`; the installed pod wheel is not
verified by reading its source counterpart. To compare the actual wheel export,
run this separately in the already-provisioned pod environment and pass the
resulting local JSON via `--selected-table`:

```python
import json
from pathlib import Path
from pipeline.royale_heroiw import selected_card_data
Path("selected-card-data.json").write_text(json.dumps(selected_card_data()), encoding="utf-8")
```

Extraction inventories every APK split and reads `assets/csv_*/*.csv` and TOML
overlays recursively. Supported encodings: plain UTF-8, LZMA-alone/XZ,
Supercell's nine-byte LZMA header, and the explicit SC version-1 MD5/zlib wrapper.
Unsupported wrappers, truncated/oversized streams, differing duplicate assets,
and unsafe ZIP paths are reported; nothing is guessed or silently overwritten.
The supplied build's assets use the nine-byte LZMA format.

The pinned SIM source parser is copied into the ignored run directory and used
read-only against the effective decoded tables. It handles TOML inheritance,
CSV continuation arrays, projectile damage and spawn joins, and object-rarity
level ladders. Its release-specific mechanic refusals are retained. Hero basic
and deploy stats are read independently of ability interpreters; unsupported
evolution mechanics can likewise retain basic stats when their joins resolve.
This compares data under a shared parser interpretation; it does not independently
prove that the simulator interprets the game's mechanics correctly.

Every requested stat is compared exactly, retaining null versus missing versus
zero. Distances are millitiles, times milliseconds (except explicit seconds
fields), speeds raw table units. HP/damage use the stated object-level base;
the level-scaling arrays and card rarity caps are compared separately. Spell
damage includes projectile chains and damage-over-time fields. Linked deploy/
death effects and explicit summoned units are included. Null spell deploy times
have no explicit card override; no engine/global default is invented. The full
normalized cards, table hashes and source parser hashes accompany the report.

Opponent ranking combines original `L70/pool_forms/loadable_decks.json` weights
with both deck sides of crawl-ready PRO2 `output/battles.csv`. It counts presence
in decks, not plays. It collapses forms for the top 60 base cards and also
compares their observed census forms. This is the available top-deck census
subset, not the complete population or exclusively opponents of icebow.
Potential cross-source overlap is not deduplicated; counts remain separated
in the report. PRO2 forms are unknown. The reweighted ladder/LIVECAL pools are
not added a second time. Config checks cover explicit `card_levels` overrides
only; unspecified live defaults are not executed or inferred.

Artifacts in each run:

- `tables/`: decoded private CSV/TOML assets.
- `extraction.json`: APK/device hashes, per-file provenance, fallbacks, codecs, failures and conflicts.
- `cards.json`, `normalization.json`, `normalization.log`: joined card evidence and limitations.
- `REPORT.md`, `report.json`, `per_level.json`: complete icebow/top-60 and observed-form comparisons, exact values, count basis, configured caps and requested level stats.
- `snapshot.json`, `changes.json`: baseline and next-build comparison.

`tests/` contains only small synthetic fixtures, including future-build and
failure-preserves-baseline integration checks, device precedence and level math.
`verify_device.py` verifies the last `out/device_builds/` run against its current
local inputs, raw rarity ladder and both SIM references. No APK or raw game table belongs
in tracked files or test fixtures.
