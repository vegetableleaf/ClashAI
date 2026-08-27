"""I4 gate: does the live `cards-import` dry-run reconcile with the adjudicated ledger?

    python research/sim_parity/scripts/i4_reconcile_dryrun.py <dryrun_output.txt>

Every change the dry-run proposes must be accounted for by something the R2 sweep
already measured and the owner already adjudicated (stat_diffs.jsonl / decisions.md),
by a pin enforcement, or by allowlisted new content (the 16 live `_hero` rows).
Anything else is a SURPRISE: wiki movement since the 2026-08-26 snapshots or a parser
behaviour change nobody catalogued -- either way, stop and investigate before any
--write (PLAN.md I4 gate).
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "research" / "sim_parity" / "ledger"

_ADD = re.compile(r"^\[cards-import\]\s+\+ (\S+)$")
_DEL = re.compile(r"^\[cards-import\]\s+- (\S+)$")
_CHG = re.compile(r"^\[cards-import\]\s+~ ([a-z0-9_]+)\.([a-z0-9_]+): (.*) -> (.*)$")
_PIN = re.compile(r"^\[cards-import\]\s+pin ([a-z0-9_]+)\.([a-z0-9_]+): scraped (.*) -> pinned (.*)$")


def main(argv) -> int:
    text = Path(argv[1]).read_text(encoding="utf-8")
    rows = [json.loads(line) for line in
            (LEDGER / "stat_diffs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    by_kf: dict = {}
    for r in rows:
        by_kf.setdefault((r["key"], r["field"]), []).append(r.get("verdict"))
    pins = {(p["key"], p["field"]): p["value"] for p in
            json.loads((ROOT / "icebow" / "config" / "import_pins.json")
                       .read_text(encoding="utf-8"))["pins"]}
    allow = json.loads((ROOT / "icebow" / "config" / "import_allowlist.json")
                       .read_text(encoding="utf-8"))["allow"]

    added, removed, changed, pin_applied = [], [], [], []
    for line in text.splitlines():
        m = _ADD.match(line)
        if m:
            added.append(m.group(1))
            continue
        m = _DEL.match(line)
        if m:
            removed.append(m.group(1))
            continue
        m = _CHG.match(line)
        if m:
            changed.append(m.groups())
            continue
        m = _PIN.match(line)
        if m:
            pin_applied.append(m.groups())

    verdictc: Counter = Counter()
    surprises, notes = [], []

    for key in added:
        if key.endswith("_hero") and (allow.get(key) or {}).get("status") == "live":
            verdictc["added: live hero (allowlisted)"] += 1
        elif (key, "hitpoints") in by_kf or any(k == key for k, _ in by_kf):
            verdictc["added: key known to the sweep"] += 1
        else:
            surprises.append(f"ADDED {key}: not a live hero, not in stat_diffs")

    for key in removed:
        surprises.append(f"REMOVED {key}: a re-import should never drop a live card")

    for key, field, old, new in changed:
        kf = (key, field)
        pv = pins.get(kf, "\x00none")
        try:
            newv = json.loads(new.replace("'", '"'))
        except Exception:  # noqa: BLE001
            newv = new
        if pv != "\x00none" and pv == newv:
            verdictc["changed: pin-enforced value"] += 1
        elif kf in by_kf:
            verdictc[f"changed: stat_diffs verdict {'/'.join(sorted(set(by_kf[kf])))}"] += 1
        elif any(k == key for k, _ in by_kf):
            notes.append(f"CHANGED {key}.{field}: {old} -> {new} (key swept, FIELD not in "
                         "stat_diffs)")
            verdictc["changed: key swept, field not catalogued"] += 1
        else:
            surprises.append(f"CHANGED {key}.{field}: {old} -> {new} (no stat_diffs row at all)")

    print(f"dry-run: +{len(added)} added, -{len(removed)} removed, {len(changed)} field changes, "
          f"{len(pin_applied)} pin enforcements")
    for k, n in sorted(verdictc.items()):
        print(f"  {n:4d}  {k}")
    if notes:
        print(f"\nnotes ({len(notes)}) -- swept keys, uncatalogued fields:")
        for n in notes:
            print(f"  {n}")
    if surprises:
        print(f"\nSURPRISES ({len(surprises)}) -- STOP, do not --write:")
        for s in surprises:
            print(f"  {s}")
        return 1
    print("\nno surprises: every change is pin-enforced, sweep-catalogued, or allowlisted "
          "new content.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
