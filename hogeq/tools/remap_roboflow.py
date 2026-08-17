"""Remap a Roboflow COCO export's classes onto this project's detector taxonomy.

    python tools/remap_roboflow.py <export_dir> [--report] [--out batchN.json]

Every source uses its own naming: `ally_`/`enemy_` prefixes, `E`/`O` prefixes with CamelCase
abbreviations, Title Case with spaces. Ours is team-agnostic snake_case -- team comes from
TeamTracker at run time, not from the class -- so stripping the team prefix is correct AND
doubles the data per class.

RULE: anything that does not map with confidence is DROPPED, never guessed. A wrong class is far
worse than a missing one: it teaches the detector that one card looks like another, and the error
is invisible until it misfires in a match.
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

#: Team / ownership prefixes to strip. Ours carries no team in the class name.
_PREFIX = re.compile(r"^(ally|enemy|own|friendly)[_\- ]", re.I)

#: Datasets older than Nov 2025 predate the Three Musketeers rework, so their art is stale.
STALE_BEFORE_NOV_2025 = {"three_musketeers", "3_musketeers", "musketeers"}

#: Verified abbreviation expansions. Deliberately explicit: fuzzy matching would happily file
#: `EMiniPeka` under `pekka` and `EBigPekka` under `mini_pekka`, and nothing downstream would say so.
ALIAS = {
    # --- IDENTIFIED BY THE USER from example crops (2026-08-17). Every one of these was a
    # name no card carries, so none of them could have been resolved from the string alone.
    "larry": "skeletons",              # the 1-elixir Skeletons -- 1,618 boxes, the largest unknown
    "ev_larry": "skeletons_evo",
    "brawler": "goblin_cage",          # the Goblin Brawler the Goblin Cage spawns
    "ex": "executioner", "e_x": "executioner",
    "doctor": "goblinstein",           # Goblinstein's two halves collapse onto the one card
    "monster": "goblinstein",
    "fire_wizard": "wizard",
    "hero_musk": "musketeer_hero", "hero_musk_turret": "musketeer_hero",
    "spirit_emp": "spirit_empress", "sprit_emp_walk": "spirit_empress",
    "spirit_emp_walk": "spirit_empress",
    # --- resolved against our taxonomy (checked, not guessed) ---
    "barb": "barbarians", "eminion": "minions", "ominion": "minions",
    "ecan": "cannon", "ocan": "cannon", "can": "cannon", "wall_break": "wall_breakers",
    "elexirgolem": "elixir_golem", "ofireball": "fireball", "elite_barbarian": "elite_barbarians",
    "cursed_hog": "mother_witch_hog",            # the hog a Mother Witch curses
    "rascalboy": "rascals", "rascalgirl": "rascals", "archer_rascal": "rascals",
    "big_rascal": "rascals", "rascal_boy": "rascals", "rascal_girl": "rascals",
    "golem_mini": "golemite", "mini_golem": "golemite",   # the Golem's split, our `golemite`
    "healer": "battle_healer",
    # --- plurals / naming differences against our taxonomy ---
    "archer": "archers", "arrow": "arrows", "barbarian": "barbarians", "bat": "bats",
    "goblin": "goblins", "guard": "guards", "skeleton": "skeletons",
    "spear_goblin": "spear_goblins", "zappy": "zappies", "minion": "minions",
    "royal_hog": "royal_hogs", "royal_recruit": "royal_recruits", "wall_breaker": "wall_breakers",
    "log": "the_log", "hog": "hog_rider", "xbow": "x_bow", "pump": "elixir_collector",
    "elixirpump": "elixir_collector", "tomb": "tombstone",     # --- CamelCase abbreviations (inkgamesarrow) ---
    "b_ram": "battle_ram", "baby_drag": "baby_dragon", "big_pekka": "pekka",
    "mini_peka": "mini_pekka", "bombertower": "bomb_tower", "cannon_cart": "cannon_cart",
    "dart_goblin": "dart_goblin", "electro_drag": "electro_dragon", "electro_g": "electro_giant",
    "elite_barb": "elite_barbarians", "elixer_golem": "elixir_golem", "firecrack": "firecracker",
    "firespirit": "fire_spirit", "fire_spirit": "fire_spirit", "giant_skeleton": "giant_skeleton",
    "goblindem": "goblin_demolisher", "goblin_dem": "goblin_demolisher",
    "golem_mite": "golemite", "heal_spirit": "heal_spirit", "inferno_drag": "inferno_dragon",
    "lumber_jack": "lumberjack", "magic_archer": "magic_archer", "mega_m": "mega_minion",
    "megam": "mega_minion", "mighty_miner": "mighty_miner", "morter": "mortar",
    "mother_witch": "mother_witch", "musk": "musketeer", "musk_new": "musketeer",
    "night_witch": "night_witch", "phenix": "phoenix", "ram_rider": "ram_rider",
    "ramrider": "ram_rider", "royal_ghost": "royal_ghost", "royal_knight": "golden_knight",
    "royal_r": "royal_recruits", "royale_g": "royal_giant", "royal_g": "royal_giant",
    "royale_giant": "royal_giant", "skel_barrel": "skeleton_barrel",
    "skeleton_barrel": "skeleton_barrel", "skel_drag": "skeleton_dragons",
    "snow_ball": "giant_snowball", "snowball": "giant_snowball", "giant_bomb": "giant_snowball",
    "valk": "valkyrie", "beserker": "berserker",
    "goblinbarrel": "goblin_barrel", "goblindrill": "goblin_drill", "infernodragon":
        "inferno_dragon", "motherwitch": "mother_witch", "mightyminer": "mighty_miner",
    "skeletonking": "skeleton_king", "royalghost": "royal_ghost", "wallbreaker": "wall_breakers",
    "bombtower": "bomb_tower", "battleram": "battle_ram", 
    "goldenknight": "golden_knight", "electrogiant": "electro_giant", "elixirgolem":
        "elixir_golem", "tesla_hidden": "tesla", "cursedhog": "mother_witch_hog",
    "hungry_dragon": "baby_dragon",     "bush": "bush_goblin",
    "goblin_machine": "goblin_machine",
    # --- evolution forms: `EV<x>` -> <x>_evo ---
    "ev_archer": "archers_evo", "ev_firecrack": "firecracker_evo", "ev_furnace": "furnace_evo",
    "ev_mega_knight": "mega_knight_evo", "ev_royal_g": "royal_giant_evo", "ev_tesla": "tesla_evo",
    "ev_witch": "witch_evo", "ev_electro_drag": "electro_dragon_evo",
    "ev_inferno_drag": "inferno_dragon_evo", "ev_wizard": "wizard_evo",
    "barbarian_evo": "barbarians_evo", "skeleton_evo": "skeletons_evo",
    "knight_evo": "knight_evo",
}

#: Not units, or not in our taxonomy at all -- dropped silently rather than reported as unknown.
IGNORE = {
    "yes", "no", "cards", "towerdown", "tower_down", "cards_hp_bar_towers",
    "king_tower", "princess_tower", "dag_tower", "pan_tower", "cannoneer_tower",
    "enemy_dag_tower", "enemy_pan_tower", "enemy_princess_tower", "own_dag_tower",
    "own_king_tower", "own_pan_tower", "own_princess_tower", "enemy_king_tower",
    "little_prince_side",
    }


def camel_split(s: str) -> str:
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    return re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)


def normalise(raw: str) -> str:
    s = raw.strip()
    # E<Name> / O<Name> team prefixes used by inkgamesarrow -- only when a capitalised word follows
    m = re.match(r"^([EO])([A-Z][A-Za-z].*)$", s)
    if m:
        s = m.group(2)
    s = camel_split(s)
    s = _PREFIX.sub("", s)
    s = s.lower().replace("-", "_").replace(" ", "_").replace(".", "")
    s = re.sub(r"[^a-z0-9_]", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    s = re.sub(r"^(e|o)_", "", s)               # leftover single-letter team prefix
    return s


def resolve(raw: str, known: set) -> tuple[str | None, str]:
    """-> (our_class or None, reason)."""
    n = normalise(raw)
    if not n or n in IGNORE:
        return None, "ignored"
    if n in ALIAS:
        n = ALIAS[n]
    if n.endswith("_evo") and n[:-4] in ALIAS:
        n = ALIAS[n[:-4]] + "_evo"
    return (n, "ok") if n in known else (None, "unmatched")


def _emit(src: Path, cats: dict, known: set, out: Path, root: Path, copy_images: bool) -> None:
    """Write a Label Studio task list, and optionally stage the frames.

    detect-import matches images by BASENAME against data/detect/images/**, so an export whose
    frames are not in the dataset matches nothing at all -- it reports "0 annotations" and looks
    like a parsing failure. Roboflow filenames already carry a per-image hash, so collisions with
    the existing queue are not a practical concern.

    Coordinates are PERCENTAGES of the image, which is what Label Studio regions use and what
    _ls_rect_to_yolo expects; COCO gives absolute pixels, so every box is converted.
    """
    import json as _json
    import shutil
    dest = root / "data" / "detect" / "images" / ("rf_" + src.name[:40])
    if copy_images:
        dest.mkdir(parents=True, exist_ok=True)
    tasks, staged = [], 0
    for j in sorted(src.rglob("_annotations.coco.json")):
        c = _json.load(open(j, encoding="utf-8"))
        by_img = {}
        for an in c["annotations"]:
            by_img.setdefault(an["image_id"], []).append(an)
        for info in c["images"]:
            anns = by_img.get(info["id"]) or []
            regions = []
            W, H = float(info["width"]), float(info["height"])
            for an in anns:
                cls, why = resolve(cats.get(an["category_id"], "?"), known)
                if why != "ok":
                    continue
                x, y, w, h = [float(v) for v in an["bbox"]]
                regions.append({"original_width": int(W), "original_height": int(H),
                                "image_rotation": 0, "type": "rectanglelabels",
                                "from_name": "label", "to_name": "image",
                                "value": {"x": 100.0 * x / W, "y": 100.0 * y / H,
                                          "width": 100.0 * w / W, "height": 100.0 * h / H,
                                          "rotation": 0, "rectanglelabels": [cls]}})
            if not regions:
                continue                       # a frame with nothing we recognise teaches nothing
            tasks.append({"data": {"image": info["file_name"]},
                          "annotations": [{"result": regions}]})
            if copy_images:
                srcf = j.parent / info["file_name"]
                if srcf.exists() and not (dest / info["file_name"]).exists():
                    shutil.copy2(srcf, dest / info["file_name"])
                    staged += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json.dumps(tasks), encoding="utf-8")
    print("   wrote %s: %d task(s), %d box(es)%s"
          % (out.name, len(tasks), sum(len(t["annotations"][0]["result"]) for t in tasks),
             (", staged %d image(s) -> %s" % (staged, dest.name)) if copy_images else ""))


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("export_dir")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", default=None, help="write a Label Studio batch JSON here")
    ap.add_argument("--copy-images", action="store_true",
                    help="copy the export's frames into the dataset's images/ so detect-import "
                         "can match them by basename")
    a = ap.parse_args(argv)

    known = {l.strip() for l in (_ROOT / "data" / "detect" / "classes.txt")
             .read_text(encoding="utf-8").splitlines() if l.strip()}
    src = Path(a.export_dir)
    cats, counts = {}, collections.Counter()
    for j in src.rglob("_annotations.coco.json"):
        c = json.load(open(j, encoding="utf-8"))
        for x in c["categories"]:
            cats[x["id"]] = x["name"]
        for an in c["annotations"]:
            counts[cats.get(an["category_id"], "?")] += 1

    ok, unmatched, ignored = {}, {}, {}
    for raw, n in counts.items():
        cls, why = resolve(raw, known)
        (ok if why == "ok" else ignored if why == "ignored" else unmatched)[raw] = (cls, n)
    tot = sum(counts.values())
    kept = sum(n for _, n in ok.values())
    print("%s: %d source classes, %d boxes" % (src.name, len(counts), tot))
    print("   mapped   %3d classes  %6d boxes (%.1f%%)" % (len(ok), kept, 100 * kept / max(1, tot)))
    print("   ignored  %3d classes  %6d boxes" % (len(ignored), sum(n for _, n in ignored.values())))
    print("   UNMATCHED %2d classes  %6d boxes" % (len(unmatched),
                                                   sum(n for _, n in unmatched.values())))
    if a.out:
        _emit(src, cats, known, Path(a.out), _ROOT, a.copy_images)
    if a.report and unmatched:
        print("\n   unmatched (dropped unless mapped):")
        for raw, (_, n) in sorted(unmatched.items(), key=lambda kv: -kv[1][1]):
            print("      %-26s -> %-24s %5d boxes" % (raw, normalise(raw), n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
