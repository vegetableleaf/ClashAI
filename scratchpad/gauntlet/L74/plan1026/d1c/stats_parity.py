"""D1-C (plan1026 D1 check "parsed stats = device table pull: 100%"): crforge's parsed unit / building / projectile /
area / buff / spell rows against the same rows parsed independently from the device's own table files.

    python -I stats_parity.py --crforge TABLES_DIR --fingerprint U/fingerprint.json --update U [--pack P] [--cache C]
        --work DECODED_DIR --out OUT.json

Inputs (a, each checked here):
  * the device's table files: the game's update/ folder (pull_device_update.sh, read-only adb) over the installed APK
    splits' csv_logic / csv_client (pull_pack_tables.sh, read-only `adb exec-out unzip -p`); each raw file's SHA-1
    against the device's own fingerprint.json (the content version crforge's tables name in build.properties);
  * the independent parse: RoyaleSim's tools/extract_cards.load_tables (another project's loader: CSV + TOML overlays,
    [KIND.Name] routing, EXT inheritance), on those decoded files, without its 16.402 column rewrite (filters_format
    off), so each value is the file's own;
  * crforge's parsed tables (tables/<version>/<table>.json, rows -> columns).
Per field: a (table, row, column) either engine sets; match = equal after the type normalisation in `norm` (a TOML
float vs crforge's float32 compared to 1e-6 relative; an absent value = None; a one-element list = its element).
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import math
import sys
import tomllib
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SIM = ROOT / "research/ext/Royale/RoyaleSim"
TABLES = ("characters", "buildings", "projectiles", "area_effect_objects", "character_buffs", "spells_characters",
          "spells_buildings", "spells_other", "spells_evolved", "spells_hero_form")
# the card screen's stat labels ([STATS.*] sections): crforge keeps them, the loader skips those sections; no battle value
UI_ONLY = {"StatsTags"}


def effective(fp: Path, update: Path, pack: Path | None, cache: Path | None, work: Path) -> dict:
    """The fingerprint's table files, each from the device's update/ folder, else the APK pack pull, else (16.402.22:
    the device no longer holds that client) crforge's own asset cache by SHA-1; each raw file's SHA-1 checked against
    the device's fingerprint, decoded (apktables.decoder) into ``work``."""
    sys.path.insert(0, str(ROOT / "scratchpad/gauntlet/L74/apktables"))
    import decoder
    f = json.loads(fp.read_text())
    want = {e["file"]: e["sha"] for e in f["files"]
            if e["file"].startswith(("csv_logic/", "csv_client/")) or e["file"] == "data_manifest.toml"}
    res, bad = Counter(), []
    for rel, s in want.items():
        cands = [("device_update", update / rel), ("device_apk", pack / rel if pack else None),
                 ("crforge_cache", cache / s if cache else None)]
        src, p = next(((n, q) for n, q in cands if q is not None and q.is_file()), (None, None))
        if p is None:
            res["absent"] += 1
            bad.append([rel, "absent"])
            continue
        res[src] += 1
        raw = p.read_bytes()
        if hashlib.sha1(raw).hexdigest() == s:
            res["sha1_match"] += 1
        else:
            bad.append([rel, src])
        (work / rel).parent.mkdir(parents=True, exist_ok=True)
        (work / rel).write_bytes(decoder.decode(raw)[0])
    return dict(version=f.get("version"), content_sha=f.get("sha"), table_files=len(want), **res, sha1_bad=bad)


def loader(files: Path):
    spec = importlib.util.spec_from_file_location("extract_cards", SIM / "tools/extract_cards.py")
    e = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SIM / "tools"))
    sys.modules["extract_cards"] = e
    spec.loader.exec_module(e)
    # The loader leaves the evolution / hero-form sections and the characters/hero_form files out on purpose (its
    # card roster); the game loads them (data_manifest.toml), so they are routed here too, in the same way.
    e.SECTION_TABLE.update(SPELL_EVOLVED="spells_evolved", SPELL_HERO="spells_hero_form")
    e.SKIP_SECTIONS = e.SKIP_SECTIONS - {"SPELL_EVOLVED", "SPELL_HERO"}
    route = e.route_sections

    def route_known(t, p, doc, label):
        # an [EXT.*] of a kind with no compared table (FILTER), and a manifest file's other kinds (game modes), are
        # left out: no compared row is in them
        ext = {n: x for n, x in (doc.get("EXT") or {}).items()
               if not (isinstance(x, dict) and isinstance(x.get("Base"), str)
                       and x["Base"].split(".")[0] not in e.SECTION_TABLE)}
        doc = {k: (ext if k == "EXT" else b) for k, b in doc.items()
               if k == "EXT" or k in e.SECTION_TABLE or k in e.SKIP_SECTIONS}
        return route(t, p, doc, label)
    e.route_sections = route_known
    base = e.VINTAGES["160402017"]
    # data_manifest.toml's other files (boosts, elixir drop, game modes ...), routed after the folders as the client
    # loads the manifest after the registered files
    man = tomllib.loads((files.parent / "data_manifest.toml").read_text(encoding="utf-8"))
    extra = [files.parent / x["Path"] for x in man.values() if isinstance(x, dict) and "Path" in x
             and x["Path"].startswith("csv_logic/")
             and not x["Path"].startswith(("csv_logic/characters/", "csv_logic/events/"))]

    class V(type(base)):
        def glob(self, sub, pattern):
            return [p for p in extra if p.is_file()] if sub == "<manifest>" else super().glob(sub, pattern)
    v = dataclasses.replace(base, key="d1c", raw=files, update=None, additions=False, filters_format=False,
                            sources={**base.sources, "spells_hero_form": "spells_hero_form.csv"},
                            character_dirs=base.character_dirs + ("characters/hero_form", "<manifest>"))
    return e.load_tables(V(**{f.name: getattr(v, f.name) for f in dataclasses.fields(v)}))


def norm(v):
    if v is None or v == "" or v is False or v == [] or (isinstance(v, (int, float)) and v == 0):
        return None                           # crforge writes an empty cell as its type's default ("", false, [], 0)
    if isinstance(v, str):                    # a float column the loader keeps as text ("1")
        try:
            return norm(float(v))
        except ValueError:
            return v
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items() if x is not None}
    if isinstance(v, (list, tuple)):
        v = [norm(x) for x in v]
        return v[0] if len(v) == 1 else v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def same(a, b) -> bool:
    a, b = norm(a), norm(b)
    if isinstance(a, float) or isinstance(b, float):
        try:
            return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-9)
        except (TypeError, ValueError):
            return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def sim_value(tb, name: str, col: str):
    """The loader's value of a column: its array (continuation lines) where it keeps one, else the cell."""
    r = tb.get(name)
    if r is None:
        return None
    arr = getattr(tb, "arrays", {}).get(name, {}).get(col)
    return arr if arr is not None else dict.get(r, col)


def compare(t, cf: Path, plant: dict | None = None) -> dict:
    """``plant`` {(table, row, column): value or None}: crforge values changed / dropped before comparing (self-check)."""
    out = {}
    for k in TABLES:
        rows = json.loads((cf / f"{k}.json").read_text())["rows"]
        for (pt, pr, pc), pv in (plant or {}).items():
            if pt == k:
                rows[pr]["columns"].pop(pc, None) if pv is None else rows[pr]["columns"].__setitem__(pc, pv)
        tb = t.get(k)
        sim_names = set(getattr(tb, "records", {}) or {}) if tb is not None else set()
        c, mism, only = Counter(), [], []
        for name, row in rows.items():
            tb = t.get(k)
            if name not in sim_names:
                # the loader files a [CHARACTER.X] with IsBuilding under buildings; crforge keeps the section's table
                other = {"characters": "buildings", "buildings": "characters"}.get(k)
                if other and t[other].get(name) is not None:
                    tb = t[other]
                    c["rows_in_other_unit_table"] += 1
                else:
                    only.append(name)
                    continue
            r = tb.get(name)
            # a lower-case key is the loader's own note (base_ops), not a file column
            cols = set(row["columns"]) | {col for col, v in dict(r).items() if v is not None and not col[:1].islower()}
            for col in sorted(cols):
                a, b = row["columns"].get(col), sim_value(tb, name, col)
                if col in UI_ONLY:
                    c["ui_only_not_compared"] += 1
                    continue
                if norm(a) is None and norm(b) is None:
                    continue
                c["fields"] += 1
                if same(a, b):
                    c["match"] += 1
                else:
                    mism.append([name, col, a, b])
        other = {"characters": "buildings", "buildings": "characters"}.get(k)
        oth = json.loads((cf / f"{other}.json").read_text())["rows"] if other else {}
        out[k] = dict(c, rows_crforge=len(rows), rows_device=len(sim_names),
                      match_rate=round(c["match"] / max(c["fields"], 1), 6), mismatches=mism,
                      crforge_only_rows=only, device_only_rows=sorted(sim_names - set(rows) - set(oth)))
    return out


PLANT = {("characters", "Knight", "Hitpoints"): 691, ("characters", "Knight", "Range"): None,
         ("characters", "Berserker", "OnStartingAction"): {"ClassType": "ActionX"},
         ("buildings", "DaggerDuchess", "AttackSequence"): [0, 1, 2], ("projectiles", "TowerKnifeThrowerProjectile",
         "Speed"): 1, ("spells_other", "Rocket", "ManaCost"): 5, ("character_buffs", "ZapFreeze", "SpeedMultiplier"): 7}


def selfcheck(t, cf: Path, base: dict) -> dict:
    """Planted divergences: each planted crforge value must come out as exactly one new mismatch, at its key."""
    got = compare(t, cf, PLANT)
    new = {(k, m[0], m[1]) for k, v in got.items() for m in v["mismatches"]} - \
          {(k, m[0], m[1]) for k, v in base.items() for m in v["mismatches"]}
    return dict(planted=len(PLANT), caught=len(new & set(PLANT)), extra=sorted(map(list, new - set(PLANT))),
                ok=new == set(PLANT))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crforge", type=Path, required=True, help="crforge tables/<version> dir")
    ap.add_argument("--fingerprint", type=Path, required=True, help="the device's update/fingerprint.json")
    ap.add_argument("--update", type=Path, required=True, help="the device's update/ folder pull")
    ap.add_argument("--pack", type=Path, help="pull_pack_tables.sh output's APK dir")
    ap.add_argument("--cache", type=Path, help="crforge asset cache (SHA-1 named), for files the device lacks")
    ap.add_argument("--work", type=Path, required=True, help="decoded effective files go here")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    res = dict(crforge_build=(a.crforge / "build.properties").read_text().split())
    res["files"] = effective(a.fingerprint, a.update, a.pack, a.cache, a.work)
    t = loader(a.work / "csv_logic")
    res["tables"] = compare(t, a.crforge)
    res["selfcheck"] = selfcheck(t, a.crforge, res["tables"])
    tot = Counter()
    for v in res["tables"].values():
        tot.update({k: v.get(k, 0) for k in ("fields", "match")})
    res["overall"] = dict(fields=tot["fields"], match=tot["match"], match_rate=round(tot["match"] / max(tot["fields"], 1), 6))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(dict(files=res["files"], overall=res["overall"], selfcheck=res["selfcheck"],
                          tables={k: {x: v[x] for x in v if x not in ("crforge_only_rows", "device_only_rows")}
                                  for k, v in res["tables"].items()}), indent=1, default=str))
    return 0 if res["selfcheck"]["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
