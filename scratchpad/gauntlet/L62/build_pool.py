#!/usr/bin/env python
"""L62 -- build the ghost pool from a SNAPSHOT of the crawl2 corpus.

Offline only (no engine, no emulator).  Mirrors research/sandbox_tools/replay_drive.py's acceptance
tests exactly: deck slugs must resolve to catalog cards, the requested evo/hero forms must exist,
every played card must be in that side's deck, every non-ability play must be positioned, and
infer_deals() must find at least one (opening hand, draw queue) assignment for BOTH sides.

Run:  research/ext/cr-native-sandbox/.venv/Scripts/python.exe scratchpad/gauntlet/L62/build_pool.py
"""
from __future__ import annotations
import csv, json, re, sys, collections
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SANDBOX = REPO / "research" / "ext" / "cr-native-sandbox"
L62 = REPO / "scratchpad" / "gauntlet" / "L62"
SNAP = L62 / "snap"
OUT = REPO / "icebow" / "data" / "ghost_pool"
sys.path.insert(0, str(SANDBOX))
sys.path.insert(0, str(REPO / "research" / "sandbox_tools"))

from native_core.card_catalog import catalog, card_cost, validate_deck  # noqa: E402
import replay_drive as RD  # noqa: E402

LEVEL = 11  # constant fill: the crawl records no card levels (see ghost_pool.md schema caveat)

SIM_KEYS = set(json.loads((L62 / "sim_card_keys.json").read_text()))
# Engine-measured outcome of L61's 211-tag batch drive (scratchpad/gauntlet/ext/batch_v2), attached
# per-tag as "engine_verified" (null for tags the engine has never driven).
_EV = L62 / "engine_verify.json"
ENGINE = json.loads(_EV.read_text()) if _EV.exists() else {}
_ALIAS_INV = {"AngryBarbarians": "elite_barbarians", "Archer": "archers", "Assassin": "bandit",
    "BarbLog": "barbarian_barrel", "MovingCannon": "cannon_cart", "BlowdartGoblin": "dart_goblin",
    "AxeMan": "executioner", "FireSpirits": "fire_spirit", "DartBarrell": "flying_machine",
    "FirespiritHut": "furnace", "Snowball": "giant_snowball", "SkeletonWarriors": "guards",
    "Heal": "heal_spirit", "IceGolemite": "ice_golem", "IceSpirits": "ice_spirit",
    "RageBarbarian": "lumberjack", "EliteArcher": "magic_archer", "WitchMother": "mother_witch",
    "DarkWitch": "night_witch", "Ghost": "royal_ghost", "GiantBuffer": "rune_giant",
    "SkeletonBalloon": "skeleton_barrel", "ZapMachine": "sparky", "MergeMaiden": "spirit_empress",
    "Log": "the_log", "DarkMagic": "void", "MiniSparkys": "zappies", "Xbow": "x_bow",
    "Wallbreakers": "wall_breakers", "Elixir Collector": "elixir_collector", "Pekka": "pekka",
    "MiniPekka": "mini_pekka", "GlobalLightning": "lightning", "GlobalClone": "clone"}


def sim_key_for(name):
    k = _ALIAS_INV.get(name) or re.sub(r"(?<!^)(?=[A-Z])", "_", name.replace(" ", "")).lower()
    return k if k in SIM_KEYS else None


def load_snapshot():
    with (SNAP / "battles.csv").open(encoding="utf-8", newline="") as h:
        battles = list(csv.DictReader(h))
    plays = collections.defaultdict(list)
    n = 0
    with (SNAP / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        for row in csv.DictReader(h):
            plays[row["replay_tag"]].append(row)
            n += 1
    return battles, plays, n


def deck_for(battle, side):
    """replay_drive.deck_for_side, but raising ValueError instead of SystemExit."""
    deck = []
    raw = battle[RD.DECK_COL_OF_SIDE[side]].strip()
    tokens = [t.strip() for t in raw.split(",") if t.strip()]
    if len(tokens) != 8:
        raise ValueError("deck_not_8_tokens:%d" % len(tokens))
    for token in tokens:
        slug, form = RD.split_slug(token)
        try:
            card_id = RD.card_for_slug(slug)
        except KeyError:
            raise ValueError("unknown_slug:" + slug)
        name = catalog()[card_id]["internal_name"]
        deck.append({"slug": slug, "name": name, "sim_key": sim_key_for(name),
                     "card_id": card_id, "form": form, "cost": card_cost(card_id), "level": LEVEL})
    if len({d["card_id"] for d in deck}) != 8:
        raise ValueError("deck_has_duplicate_card_ids")
    try:  # exactly what build_replay() -> replay_spells() -> validate_deck() will do
        validate_deck([{"card_id": d["card_id"], "level": d["level"], "form": d["form"]} for d in deck])
    except Exception as exc:
        m = re.search(r"no native (\w+) form: (\d+)", str(exc))
        if m:
            cid = int(m.group(2))
            slug = next(d["slug"] for d in deck if d["card_id"] == cid)
            raise ValueError("no_native_%s_form:%s" % (m.group(1), slug))
        raise ValueError("validate_deck:%s" % exc)
    return deck


def convert(battle, rows):
    tag = battle["replay_tag"]
    if not rows:
        raise ValueError("no_plays_rows")
    # The live crawl appended a handful of replays TWICE, byte-identical.  Drop exact duplicate rows
    # (measured: 7 tags, every duplicate row identical field-for-field) before the count check.
    seen_rows, deduped = set(), []
    for row in rows:
        key = tuple(sorted(row.items()))
        if key in seen_rows:
            continue
        seen_rows.add(key)
        deduped.append(row)
    rows = deduped
    if battle["plays"] not in ("", "None") and int(battle["plays"]) != len(rows):
        raise ValueError("play_count_mismatch:%s!=%d" % (battle["plays"], len(rows)))
    plays = []
    for row in rows:
        for key in ("tick", "play_index", "attr_ability"):
            if row[key] in ("", "None"):
                raise ValueError("play_missing_" + key)
        p = {"play_index": int(row["play_index"]), "tick": int(row["tick"]),
             "seconds": float(row["seconds"]) if row["seconds"] not in ("", "None") else None,
             "ability": int(row["attr_ability"]), "slug": row["attr_card"]}
        if row["attr_s"] not in RD.SIDE_OF:
            raise ValueError("unknown_side:" + str(row["attr_s"]))
        p["side"] = RD.SIDE_OF[row["attr_s"]]
        if p["ability"]:
            p["x"] = p["y"] = None
        else:
            if row["x_units"] in ("", "None") or row["y_units"] in ("", "None"):
                raise ValueError("play_not_positioned")
            p["x"] = int(row["x_units"])
            p["y"] = int(row["y_units"])
        plays.append(p)
    plays.sort(key=lambda p: (p["tick"], p["play_index"]))

    decks = {s: deck_for(battle, s) for s in (0, 1)}
    deals = {}
    cmds = {0: [], 1: []}
    for side in (0, 1):
        by_slug = {d["slug"]: d for d in decks[side]}
        idx_of = {d["slug"]: i for i, d in enumerate(decks[side])}
        sp = [p for p in plays if p["side"] == side]
        unknown = sorted({p["slug"] for p in sp if not p["ability"] and p["slug"] not in by_slug})
        if unknown:
            raise ValueError("play_outside_deck:" + ",".join(unknown))
        seq = [by_slug[p["slug"]]["card_id"] for p in sp if not p["ability"]]
        if not seq:
            raise ValueError("side%d_no_positioned_plays" % side)
        found = RD.infer_deals(seq, [d["card_id"] for d in decks[side]])
        if not found:
            raise ValueError("side%d_no_consistent_deal" % side)
        deals[side] = len(found)
        for p in sp:
            d = by_slug.get(p["slug"])
            cmds[side].append({"tick": p["tick"], "seconds": p["seconds"],
                               "card": p["slug"], "name": d["name"] if d else None,
                               "sim_key": d["sim_key"] if d else None,
                               "deck_index": idx_of.get(p["slug"]),
                               "x": p["x"], "y": p["y"], "ability": p["ability"]})

    ice, ghost = 1, 0  # RoyaleAPI "blue"/team = the crawl's seed (icebow) player = engine side 1
    mirror = ({(d["slug"], d["form"]) for d in decks[ice]} == {(d["slug"], d["form"]) for d in decks[ghost]})
    return {
        "tag": tag,
        "rating": int(battle["rating"]) if battle["rating"] not in ("", "None") else "",
        "rank": int(battle["rank"]) if battle["rank"] not in ("", "None") else "",
        "result": battle["result"], "icebow_side": ice, "ghost_side": ghost,
        "icebow_deck": decks[ice], "ghost_deck": decks[ghost],
        "ghost_commands": cmds[ghost], "icebow_commands": cmds[ice],
        "final_crowns": [int(battle["opponent_crowns"]), int(battle["team_crowns"])],
        "duration_ticks": plays[-1]["tick"], "plays": len(plays),
        "battle_type": battle["battle_type"],
        "battle_timestamp": int(battle["battle_timestamp"]) if battle["battle_timestamp"] not in ("", "None") else "",
        "player_tag": battle["player_tag"], "opponent_tag": battle["opponent_tags"],
        "deal_candidates": {"0": deals[0], "1": deals[1]},
        "mirror": bool(mirror),
        "engine_verified": ENGINE.get(tag),
    }


def main():
    battles, plays, n_play_rows = load_snapshot()
    OUT.mkdir(parents=True, exist_ok=True)
    seen, pool, refused = set(), [], []
    for battle in battles:
        tag = battle["replay_tag"]
        if tag in seen:
            refused.append({"tag": tag, "reason": "duplicate_battles_row"})
            continue
        seen.add(tag)
        try:
            pool.append(convert(battle, plays.get(tag, [])))
        except ValueError as exc:
            refused.append({"tag": tag, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            refused.append({"tag": tag, "reason": "%s:%s" % (type(exc).__name__, exc)})
    pool.sort(key=lambda r: r["tag"])
    with (OUT / "pool.jsonl").open("w", encoding="utf-8", newline="\n") as h:
        for rec in pool:
            h.write(json.dumps(rec, separators=(",", ":")) + "\n")
    meta = {"snapshot_taken": "2026-09-05 13:03 local (17:03 UTC)",
            "battles_csv_data_rows": len(battles), "plays_ext_csv_data_rows": n_play_rows,
            "distinct_tags_in_plays": len(plays), "converted": len(pool), "refused": len(refused),
            "level_fill": LEVEL,
            "refused_by_reason": dict(collections.Counter(r["reason"].split(":")[0] for r in refused))}
    (OUT / "pool_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (L62 / "refused.json").write_text(json.dumps(refused, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
