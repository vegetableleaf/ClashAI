"""L62: build the ghost pool that EngineMatchEnv consumes ->  <deck>/data/ghost_pool/pool_env_v0.jsonl

    python scratchpad/gauntlet/L62/build_ghost_pool.py [--deck icebow|hogeq] [--out PATH]

L64 (2026-09-06): parameterised by deck.  `--deck` picks the card-base set (DECK_BASES) and the crawl
(`<deck>/data/royaleapi/crawl2`) and the output dir (`<deck>/data/ghost_pool`).  Default icebow -> output
byte-identical to the pre-L64 builder (verified with cmp at build time).
KEY NAMES ARE DELIBERATELY UNCHANGED: `icebow_side` / `icebow_deck` / `icebow_commands` mean "OUR DECK's
side" for whichever deck the pool was built for (hogeq included).  The rows carry no deck field; the deck
is recorded in `pool_env_v0_build.json` only.  engine_env.py also accepts `our_*` spellings.

OWNERSHIP NOTE (2026-09-05 13:2x): a second agent owns `icebow/data/ghost_pool/pool.jsonl` and a
different schema (see scratchpad/gauntlet/L62/ghost_pool.md §0).  This builder writes ONLY
`pool_env_v0.jsonl` + `pool_env_v0_build.json` and must never write pool.jsonl.

Derived from the crawl itself (icebow/data/royaleapi/crawl2/{battles,plays_ext}.csv) through
research/sandbox_tools/replay_drive.py (load_battle / deck_for_side / infer_deals), i.e. the same
path the certified replay driver uses.  Nothing here touches the engine.

One JSON object per line:
  tag, result ("win"/"loss" from the icebow side), icebow_side, ghost_side
  icebow_deck / ghost_deck : 8 x {slug, name, sim_key, card_id, form, cost, level}
                             in battles.csv deck-string order (EngineMatchEnv permutes them itself
                             onto the engine's dealt positions, exactly as replay_drive.drive does)
  icebow_commands / ghost_commands : [{tick, seconds, card, name, card_id, deck_index, x, y, ability}]
                             tick-ascending; `deck_index` indexes the list above (NOT the permuted
                             engine order -- `card`/`card_id` is the stable key, and that is what
                             EngineMatchEnv re-indexes after permuting)
  final_crowns [side0, side1], duration_ticks (last play), plays, deal_candidates {"0":n,"1":n}
  battle_type, battle_timestamp, player_tag, opponent_tag, rating, rank
Inclusion rules (all hard):
  * the icebow deck is on EXACTLY one side (mirrors excluded -- the ghost would be our own deck)
  * every non-ability play is positioned and its card is in that side's deck
  * infer_deals finds >= 1 consistent (opening hand, draw queue) for BOTH sides
  * the ghost has >= 1 positioned play
"""
import csv, json, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SANDBOX = ROOT / "research" / "ext" / "cr-native-sandbox"
sys.path.insert(0, str(SANDBOX))
sys.path.insert(0, str(ROOT / "research" / "sandbox_tools"))
sys.path.insert(0, str(ROOT / "icebow" / "src"))
import replay_drive as RD  # noqa: E402
from native_core.card_catalog import catalog as _catalog  # noqa: E402

CATALOG = _catalog()

LEVEL = 11
ICEBOW_BASES = frozenset({"x_bow", "skeletons", "tesla", "knight", "the_log", "tornado", "ice_wizard", "rocket"})
# hogeq: pipeline/decks/hogeq.yaml (hogeq/config/cards.yaml:36-47); corpus deck string
# "earthquake,firecracker-ev1,hog-rider,ice-spirit,mighty-miner,skeletons,tesla-ev1,the-log"
HOGEQ_BASES = frozenset({"hog_rider", "firecracker", "mighty_miner", "tesla", "the_log", "earthquake", "skeletons",
                         "ice_spirit"})
DECK_BASES = {"icebow": ICEBOW_BASES, "hogeq": HOGEQ_BASES}


def paths_for(deck: str, out=None):
    """(crawl dir, out jsonl, out meta) for a deck; `out` overrides the jsonl path (meta goes beside it)."""
    crawl = ROOT / deck / "data" / "royaleapi" / "crawl2"
    out = Path(out) if out else ROOT / deck / "data" / "ghost_pool" / "pool_env_v0.jsonl"
    return crawl, out, out.with_name(out.stem + "_build.json")


def key_base(slug):
    return slug.replace("-ev1", "").replace("-hero", "").replace("-", "_")


def main(deck: str = "icebow", out=None):
    OUR_BASES = DECK_BASES[deck]
    CRAWL, OUT, OUT_META = paths_for(deck, out)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with (CRAWL / "battles.csv").open(encoding="utf-8", newline="") as fh:
        battles = list(csv.DictReader(fh))
    with (CRAWL / "plays_ext.csv").open(encoding="utf-8", newline="") as fh:
        plays_all = list(csv.DictReader(fh))
    by_tag = {}
    for row in plays_all:
        by_tag.setdefault(row["replay_tag"], []).append(row)

    # sim key map (for reference only; the env does its own mapping through build_bc_v2)
    sim_of_name = {}
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "l61_bcv2_names", str(ROOT / "scratchpad" / "gauntlet" / "L61" / "build_bc_v2.py"))
        _m = importlib.util.module_from_spec(spec)
        sys.modules["l61_bcv2_names"] = _m
        spec.loader.exec_module(_m)
        from clashrl.config import Config
        from clashrl.cards import shared as shared_db
        _db = shared_db(Config.load(str(ROOT / "icebow" / "config" / "config.yaml")))
        sim_of_name = {"__db__": _db, "__fn__": _m.sim_key_for}
    except Exception as exc:                                   # reference field only; never fatal
        print("sim_key mapping unavailable:", exc)

    def sim_key(name):
        if "__fn__" not in sim_of_name:
            return None
        return sim_of_name["__fn__"](name, sim_of_name["__db__"])

    rows, refused = [], Counter()
    seen = set()
    for battle in battles:
        tag = battle["replay_tag"]
        if tag in seen:
            continue
        seen.add(tag)
        sides_with_icebow = [s for s in (0, 1)
                             if {key_base(t.strip()) for t in battle[RD.DECK_COL_OF_SIDE[s]].split(",")}
                             == OUR_BASES]
        if len(sides_with_icebow) != 1:
            refused["icebow_deck_not_on_exactly_one_side"] += 1     # key kept: "our deck" (see docstring)
            continue
        ice = sides_with_icebow[0]
        ghost = 1 - ice
        raw = by_tag.get(tag)
        if not raw:
            refused["no_plays_rows"] += 1
            continue
        try:
            decks = {s: RD.deck_for_side(battle, s) for s in (0, 1)}
        except (SystemExit, KeyError) as exc:
            refused[f"deck_unresolvable"] += 1
            continue
        # the engine's own deck validator (card_catalog.validate_deck) refuses a deck whose "-ev1" card
        # has no native evolution form in this client build -- filter those out here rather than at reset
        bad_form = False
        for s in (0, 1):
            for it in decks[s]:
                row = CATALOG.get(int(it["card_id"]), {})
                if it["form"] == "evolution" and not row.get("evolution_form"):
                    bad_form = True
                if it["form"] == "hero" and not row.get("hero_form"):
                    bad_form = True
        if bad_form:
            refused["no_native_evolution_form"] += 1
            continue
        by_slug = {s: {it["slug"]: (i, it) for i, it in enumerate(decks[s])} for s in (0, 1)}
        cmds = {0: [], 1: []}
        bad = None
        for r in raw:
            if r["tick"] in ("", "None") or r["attr_ability"] in ("", "None"):
                bad = "unpositioned_meta"; break
            s = RD.SIDE_OF[r["attr_s"]]
            ability = int(r["attr_ability"])
            if ability:
                cmds[s].append({"tick": int(r["tick"]), "seconds": float(r["tick"]) * 0.05,
                                "card": None, "name": None, "card_id": None, "deck_index": None,
                                "x": None, "y": None, "ability": 1})
                continue
            if r["x_units"] in ("", "None") or r["y_units"] in ("", "None"):
                bad = "play_not_positioned"; break
            slug = r["attr_card"]
            if slug not in by_slug[s]:
                bad = "play_card_outside_deck"; break
            di, it = by_slug[s][slug]
            cmds[s].append({"tick": int(r["tick"]), "seconds": round(float(r["tick"]) * 0.05, 2),
                            "card": slug, "name": it["name"], "card_id": int(it["card_id"]),
                            "deck_index": di, "x": int(r["x_units"]), "y": int(r["y_units"]),
                            "ability": 0})
        if bad:
            refused[bad] += 1
            continue
        for s in (0, 1):
            cmds[s].sort(key=lambda c: c["tick"])
        if not any(c["ability"] == 0 for c in cmds[ghost]):
            refused["ghost_has_no_positioned_play"] += 1
            continue
        deal_n = {}
        ok = True
        for s in (0, 1):
            seq = [c["card_id"] for c in cmds[s] if not c["ability"]]
            found = RD.infer_deals(seq, [int(it["card_id"]) for it in decks[s]])
            deal_n[str(s)] = len(found)
            if not found:
                ok = False
        if not ok:
            refused["no_consistent_deal"] += 1
            continue
        try:
            crowns = [int(battle["opponent_crowns"]), int(battle["team_crowns"])]   # engine side order
        except (ValueError, KeyError):
            crowns = None
        rows.append({
            "tag": tag,
            "result": "win" if (crowns and crowns[ice] > crowns[ghost]) else
                      ("loss" if (crowns and crowns[ice] < crowns[ghost]) else "draw"),
            "raw_result": battle.get("result"),
            "rating": battle.get("team_rating", battle.get("rating", "")),
            "icebow_side": ice, "ghost_side": ghost,
            "icebow_deck": [{"slug": it["slug"], "name": it["name"], "sim_key": sim_key(it["name"]),
                             "card_id": int(it["card_id"]), "form": it["form"], "cost": int(it["cost"]),
                             "level": LEVEL} for it in decks[ice]],
            "ghost_deck": [{"slug": it["slug"], "name": it["name"], "sim_key": sim_key(it["name"]),
                            "card_id": int(it["card_id"]), "form": it["form"], "cost": int(it["cost"]),
                            "level": LEVEL} for it in decks[ghost]],
            "icebow_commands": cmds[ice], "ghost_commands": cmds[ghost],
            "final_crowns": crowns,
            "duration_ticks": max(c["tick"] for c in cmds[0] + cmds[1]),
            "plays": len(cmds[0]) + len(cmds[1]),
            "deal_candidates": deal_n,
            "battle_type": battle.get("battle_type", ""),
            "battle_timestamp": battle.get("battle_time", battle.get("timestamp", "")),
            "player_tag": battle.get("player_tag", ""), "opponent_tag": battle.get("opponent_tag", ""),
        })
    rows.sort(key=lambda r: r["tag"])
    with OUT.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    meta = {"n": len(rows), "battles_csv_rows": len(battles), "distinct_tags_in_plays": len(by_tag),
            "refused_by_reason": dict(refused), "level_fill": LEVEL,
            "builder": "scratchpad/gauntlet/L62/build_ghost_pool.py", "deck": deck,
            "our_side_keys": "icebow_side/icebow_deck/icebow_commands = OUR deck's side (any deck)",
            "source": f"{deck}/data/royaleapi/crawl2 (snapshot at build time)",
            "built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": round(time.time() - t0, 1),
            "ghost_cmds": {"total": sum(len(r["ghost_commands"]) for r in rows)}}
    OUT_META.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(json.dumps(meta, indent=1))
    if rows:
        import statistics
        g = [sum(1 for c in r["ghost_commands"] if not c["ability"]) for r in rows]
        print("ghost positioned plays/match: median", statistics.median(g), "min", min(g), "max", max(g))
        print("icebow_side counts:", dict(Counter(r["icebow_side"] for r in rows)))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--deck", choices=sorted(DECK_BASES), default="icebow")
    ap.add_argument("--out", default=None, help="jsonl path override (default <deck>/data/ghost_pool/pool_env_v0.jsonl)")
    a = ap.parse_args()
    main(a.deck, a.out)
