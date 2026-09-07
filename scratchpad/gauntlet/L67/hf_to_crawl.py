"""L67c: FirstLight IL_Replay parquet -> a crawl2-shaped directory for replay_batch.py (--crawl <dir>).

Keeps every replay where at least one side plays the EXACT icebow deck (base keys: tornado, tesla, ice-wizard, x-bow,
rocket, knight, the-log, skeletons; forms free). Writes battles.csv + plays_ext.csv with the crawl2 columns replay_drive
reads (team = "blue" = data_s "t", opponent = "red" = "o"; raw RoyaleAPI x/y; attr_i = data_i so the loader's own
180-degree rotation applies), a tags json (fully positioned, no duplicate rows), and dedupe_report.json.

Dedupe against our own crawl (icebow/data/royaleapi/crawl2): key = (team deck base keys, opponent deck base keys,
n plays, first 12 (tick, card) of the timeline). Tags are anonymised on the HF side so this is the only handle.

usage: python scratchpad/gauntlet/L67/hf_to_crawl.py --hf scratchpad/gauntlet/L67/hf/replays --out scratchpad/gauntlet/ext/crawl_hf_icebow
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

import polars as pl

REPO = Path(__file__).resolve().parents[3]
OURS = REPO / "icebow" / "data" / "royaleapi" / "crawl2"
ICEBOW = frozenset({"tornado", "tesla", "ice-wizard", "x-bow", "rocket", "knight", "the-log", "skeletons"})
SIDE_S = {"team": "blue", "opponent": "red"}
BATTLE_COLS = ("replay_tag,deck,player_tag,player_name,clan_tag,rating,rank,wins_7d,battle_time,battle_timestamp,battle_type,"
               "result,team_tags,opponent_tags,team_crowns,opponent_crowns,team_deck,opponent_deck,team_elixir_total,"
               "team_elixir_troop,team_elixir_building,team_elixir_spell,team_elixir_leaked,oppo_elixir_total,"
               "oppo_elixir_troop,oppo_elixir_building,oppo_elixir_spell,oppo_elixir_leaked,plays").split(",")
PLAY_COLS = "replay_tag,play_index,tick,seconds,x_units,y_units,tile_x,tile_y,attr_ability,attr_card,attr_s,attr_t,attr_i".split(",")


def base(k: str) -> str:
    return re.sub(r"-ev\d+$", "", k)


def our_keys() -> set[tuple]:
    """Dedupe keys of every battle already in our crawl."""
    plays: dict[str, list[tuple[int, str]]] = {}
    with (OURS / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h):
            if r["attr_ability"] in ("1", "True"):
                continue
            plays.setdefault(r["replay_tag"], []).append((int(r["tick"]), r["attr_card"]))
    keys = set()
    with (OURS / "battles.csv").open(encoding="utf-8", newline="") as h:
        for b in csv.DictReader(h):
            seq = sorted(plays.get(b["replay_tag"], []))
            keys.add((tuple(sorted(base(c) for c in b["team_deck"].split(","))),
                      tuple(sorted(base(c) for c in b["opponent_deck"].split(","))), len(seq), tuple(seq[:12])))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hf", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    ours = our_keys()
    stats = Counter()
    battles: list[dict] = []
    plays_rows: list[dict] = []
    tags: list[str] = []
    modes = Counter()
    for part in sorted(a.hf.glob("part-*.parquet")):
        df = pl.read_parquet(part, columns=["replay_tag", "payload_json"])
        for tag, pj in zip(df["replay_tag"], df["payload_json"]):
            stats["replays"] += 1
            p = json.loads(pj)
            b = p["battle"]
            sides = {}
            for side in ("team", "opponent"):
                pls = b[side]["players"]
                if len(pls) != 1:
                    stats["skip_not_1v1"] += 1
                    sides = None
                    break
                sides[side] = pls[0]
            if not sides:
                continue
            decks = {s: [c["card_key"] for c in sides[s]["deck"]] for s in sides}
            ice = [s for s in sides if {base(c) for c in decks[s]} == ICEBOW]
            if not ice:
                continue
            stats["icebow_replays"] += 1
            stats["icebow_sides"] += len(ice)
            ev = [e for e in p["events"] if e["kind"] == "play_card"]
            if any(e["source_fields"].get("data_x") is None or e["source_fields"].get("data_y") is None for e in ev):
                stats["skip_unpositioned"] += 1
                continue
            if not ev:
                stats["skip_no_plays"] += 1
                continue
            seq = sorted((int(e["source_fields"]["data_t"]), e["card_key"]) for e in ev)
            key = (tuple(sorted(base(c) for c in decks["team"])), tuple(sorted(base(c) for c in decks["opponent"])),
                   len(seq), tuple(seq[:12]))
            if key in ours:
                stats["dup_of_our_crawl"] += 1
                continue
            # abilities are logged too (attr_ability 1, no position) so the play count matches the timeline, as in crawl2
            evs = sorted(p["events"], key=lambda e: (int(e["source_fields"]["data_t"]), e["source_index"]))
            rows = []
            for i, e in enumerate(evs):
                sf = e["source_fields"]
                ability = e["kind"] != "play_card"
                rows.append({"replay_tag": tag, "play_index": i, "tick": int(sf["data_t"]), "seconds": round(int(sf["data_t"]) / 20, 2),
                             "x_units": "" if ability else int(sf["data_x"]), "y_units": "" if ability else int(sf["data_y"]),
                             "tile_x": "", "tile_y": "", "attr_ability": int(ability),
                             "attr_card": "_invalid" if ability else e["card_key"], "attr_s": SIDE_S[e["side"]],
                             "attr_t": int(sf["data_t"]), "attr_i": int(sf.get("data_i") or 0)})
            modes[(b.get("battle_type"), b.get("game_mode"))] += 1
            t, o = sides["team"], sides["opponent"]
            battles.append({"replay_tag": tag, "deck": ",".join(decks["team"] if "team" in ice else decks["opponent"]),
                            "player_tag": "", "player_name": "", "clan_tag": "", "rating": "", "rank": "", "wins_7d": "",
                            "battle_time": "", "battle_timestamp": "", "battle_type": b.get("battle_type", ""),
                            "result": b.get("result", ""), "team_tags": "", "opponent_tags": "",
                            "team_crowns": b["team"]["crowns"], "opponent_crowns": b["opponent"]["crowns"],
                            "team_deck": ",".join(sorted(decks["team"])), "opponent_deck": ",".join(sorted(decks["opponent"])),
                            "team_elixir_total": "", "team_elixir_troop": "", "team_elixir_building": "", "team_elixir_spell": "",
                            "team_elixir_leaked": t.get("elixir_leaked", ""), "oppo_elixir_total": "", "oppo_elixir_troop": "",
                            "oppo_elixir_building": "", "oppo_elixir_spell": "", "oppo_elixir_leaked": o.get("elixir_leaked", ""),
                            "plays": len(rows)})
            plays_rows.extend(rows)
            tags.append(tag)
            stats["kept"] += 1
            stats["kept_sides"] += len(ice)
        print(part.name, dict(stats), flush=True)
    with (a.out / "battles.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=BATTLE_COLS); w.writeheader(); w.writerows(battles)
    with (a.out / "plays_ext.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=PLAY_COLS); w.writeheader(); w.writerows(plays_rows)
    (a.out / "tags.json").write_text(json.dumps(tags), encoding="utf-8")
    rep = {"stats": dict(stats), "modes": {f"{k[0]}/{k[1]}": v for k, v in modes.most_common()}, "our_keys": len(ours)}
    (a.out / "dedupe_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
