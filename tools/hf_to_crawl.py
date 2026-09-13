"""FirstLight IL_Replay parquet -> a crawl2-shaped directory for ANY pipeline deck, with CARD ALIASES.

Moved from scratchpad/gauntlet/L67/hf_to_crawl_deck.py (L67m), which generalised the icebow-only hf_to_crawl.py
(L67c). For `icebow` the deck filter is the same as the old script's: the deck yaml resolves to exactly
{tornado, tesla, ice-wizard, x-bow, rocket, knight, the-log, skeletons} and icebow has no aliases.

A side is kept when its deck is EXACTLY ours (forms free), or differs by ONE card that the deck's `aliases`
table declares equivalent to the card it replaces. Owner ruling 2026-09-10: substitutions are allowed only if
placements are not confounded -- a substituted card's plays must correspond to OUR slot. That was measured, not
assumed (hf_subs_placement.py, 504,476 sides): of the five candidate swaps for hogeq only tesla <- cannon passed
(own-half share 55.6% vs 53.7%, depth quartiles within 0.5 tile). ice-spirit <- electro-spirit, 71% of the
available volume, FAILED: electro spirit is played 9.3 pp more often on the enemy half, median 3 tiles further
forward, so aliasing it would teach our ice-spirit slot to be thrown offensively. The alias table therefore lives
in the deck yaml (pipeline/decks/<deck>.yaml), and this script only reads it.

The alias is applied downstream by obs_contract.Deck.slot_of (my side's plays, hand and deck-matching only); the
crawl output keeps the TRUE card names, so the opponent's cards and every unit on the board stay truthful.

Dedupe against our own crawl for the deck: key = (team deck base keys, opponent deck base keys, n plays, first 12
(tick, card) of the timeline) -- HF tags are anonymised, so the timeline is the only handle. By default the crawl is
the deck's own `<crawl_dir>/crawl2` from the deck yaml (e.g. icebow/data/royaleapi/crawl2); when its battles.csv +
plays_ext.csv are not both there, the script prints a note and keeps every matching replay (no dedupe).

Outputs in --out: battles.csv, plays_ext.csv, tags.json (+ tags_a.json / tags_b.json, one list per engine slot),
dedupe_report.json.

usage (from the repo root; defaults read data/hf/replays and write data/hf_crawl/<deck>, both gitignored):
  icebow\\.venv\\Scripts\\python.exe tools\\hf_to_crawl.py icebow
  icebow\\.venv\\Scripts\\python.exe tools\\hf_to_crawl.py hogeq --hf data\\hf\\replays --out data\\hf_crawl\\hogeq
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
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from pipeline import vocab  # noqa: E402

DEFAULT_HF = REPO / "data" / "hf" / "replays"
DEFAULT_OUT_ROOT = REPO / "data" / "hf_crawl"
SIDE_S = {"team": "blue", "opponent": "red"}
BATTLE_COLS = ("replay_tag,deck,player_tag,player_name,clan_tag,rating,rank,wins_7d,battle_time,battle_timestamp,battle_type,"
               "result,team_tags,opponent_tags,team_crowns,opponent_crowns,team_deck,opponent_deck,team_elixir_total,"
               "team_elixir_troop,team_elixir_building,team_elixir_spell,team_elixir_leaked,oppo_elixir_total,"
               "oppo_elixir_troop,oppo_elixir_building,oppo_elixir_spell,oppo_elixir_leaked,plays").split(",")
PLAY_COLS = "replay_tag,play_index,tick,seconds,x_units,y_units,tile_x,tile_y,attr_ability,attr_card,attr_s,attr_t,attr_i".split(",")
CRAWL_FILES = ("battles.csv", "plays_ext.csv")


def base(k: str) -> str:
    return re.sub(r"-ev\d+$", "", k)


def hyphen(cls: str) -> str:
    """Pipeline class name (tesla_evo) -> RoyaleAPI base key (tesla)."""
    return vocab.base_key(str(cls)).replace("_", "-")


def load_rule(deck_name: str) -> tuple[frozenset, dict, Path]:
    path = REPO / "pipeline" / "decks" / f"{deck_name}.yaml"
    if not path.is_file():
        known = sorted(p.stem for p in (REPO / "pipeline" / "decks").glob("*.yaml"))
        raise SystemExit(f"unknown deck {deck_name!r}: no {path} (known decks: {', '.join(known)})")
    d = yaml.safe_load(path.read_text(encoding="utf-8"))
    want = frozenset(hyphen(c) for c in d["cards"])
    if len(want) != 8:
        raise SystemExit(f"{deck_name}: deck resolves to {len(want)} base keys, expected 8")
    aliases = {hyphen(src): hyphen(dst) for src, dst in (d.get("aliases") or {}).items()}   # theirs -> ours
    for src, dst in aliases.items():
        if dst not in want:
            raise SystemExit(f"alias {src} -> {dst}: {dst} is not a card in {deck_name}")
        if src in want:
            raise SystemExit(f"alias {src} -> {dst}: {src} is already in {deck_name}")
    return want, aliases, REPO / str(d["crawl_dir"]) / "crawl2"


def has_crawl(d: Path | None) -> bool:
    return d is not None and all((d / f).is_file() for f in CRAWL_FILES)


def dedupe_dir(explicit: Path | None, deck_default: Path) -> Path | None:
    """The crawl2 folder to dedupe against, or None (skip dedupe) when the deck's default crawl is absent."""
    if explicit is not None:
        if not has_crawl(explicit):
            raise SystemExit(f"--dedupe-against {explicit}: needs both {' and '.join(CRAWL_FILES)} in that folder")
        return explicit
    if has_crawl(deck_default):
        return deck_default
    print(f"note: no {' + '.join(CRAWL_FILES)} in {deck_default} -- skipping dedupe, every matching replay is kept",
          flush=True)
    return None


def our_keys(ours: Path | None) -> set[tuple]:
    if ours is None:
        return set()
    plays: dict[str, list[tuple[int, str]]] = {}
    with (ours / "plays_ext.csv").open(encoding="utf-8", newline="") as h:
        for r in csv.DictReader(h):
            if r["attr_ability"] in ("1", "True"):
                continue
            plays.setdefault(r["replay_tag"], []).append((int(r["tick"]), r["attr_card"]))
    keys = set()
    with (ours / "battles.csv").open(encoding="utf-8", newline="") as h:
        for b in csv.DictReader(h):
            seq = sorted(plays.get(b["replay_tag"], []))
            keys.add((tuple(sorted(base(c) for c in b["team_deck"].split(","))),
                      tuple(sorted(base(c) for c in b["opponent_deck"].split(","))), len(seq), tuple(seq[:12])))
    return keys


def match(ks: set, want: frozenset, aliases: dict) -> str | None:
    """'exact', 'alias:<theirs>-><ours>', or None."""
    if len(ks) != 8:
        return None
    if ks == want:
        return "exact"
    missing, extra = want - ks, ks - want
    if len(missing) == 1 and len(extra) == 1:
        theirs, ours = next(iter(extra)), next(iter(missing))
        if aliases.get(theirs) == ours:
            return f"alias:{theirs}->{ours}"
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HF replay parquet -> crawl2-shaped folder for one pipeline deck.")
    ap.add_argument("deck", help="deck name, i.e. pipeline/decks/<deck>.yaml (icebow, hogeq)")
    ap.add_argument("--hf", type=Path, default=DEFAULT_HF, help="folder of part-*.parquet (default: <repo>/data/hf/replays)")
    ap.add_argument("--out", type=Path, default=None, help="output folder (default: <repo>/data/hf_crawl/<deck>, gitignored)")
    ap.add_argument("--dedupe-against", type=Path, default=None,
                    help="crawl2 folder with battles.csv + plays_ext.csv (default: the deck's own <crawl_dir>/crawl2; "
                         "skipped with a note if that is missing)")
    a = ap.parse_args(argv)
    want, aliases, deck_crawl = load_rule(a.deck)
    out = a.out if a.out is not None else DEFAULT_OUT_ROOT / a.deck
    parts = sorted(a.hf.glob("part-*.parquet"))
    if not parts:
        raise SystemExit(f"no part-*.parquet files in {a.hf} -- run tools/hf_download.py first, or pass --hf")
    ours_dir = dedupe_dir(a.dedupe_against, deck_crawl)
    print(f"deck {a.deck}: {sorted(want)}  aliases {aliases}  dedupe vs {ours_dir}", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    ours = our_keys(ours_dir)
    stats = Counter()
    battles: list[dict] = []
    plays_rows: list[dict] = []
    tags: list[str] = []
    modes = Counter()
    for part in parts:
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
            kinds = {s: match({base(c) for c in decks[s]}, want, aliases) for s in sides}
            hit = [s for s in sides if kinds[s]]
            if not hit:
                continue
            for s in hit:
                stats[f"side_{kinds[s].split(':')[0]}"] += 1
                if kinds[s].startswith("alias"):
                    stats[kinds[s]] += 1
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
            battles.append({"replay_tag": tag, "deck": ",".join(decks["team"] if "team" in hit else decks["opponent"]),
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
            stats["kept_alias_replays"] += int(any(kinds[s].startswith("alias") for s in hit))
        print(part.name, {k: v for k, v in stats.items() if k in ("replays", "kept", "kept_alias_replays",
                                                                  "side_exact", "side_alias")}, flush=True)
    with (out / "battles.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=BATTLE_COLS); w.writeheader(); w.writerows(battles)
    with (out / "plays_ext.csv").open("w", encoding="utf-8", newline="") as h:
        w = csv.DictWriter(h, fieldnames=PLAY_COLS); w.writeheader(); w.writerows(plays_rows)
    (out / "tags.json").write_text(json.dumps(tags), encoding="utf-8")
    (out / "tags_a.json").write_text(json.dumps(tags[0::2]), encoding="utf-8")   # one list per engine slot
    (out / "tags_b.json").write_text(json.dumps(tags[1::2]), encoding="utf-8")
    rep = {"deck": a.deck, "aliases": aliases, "stats": dict(stats),
           "modes": {f"{k[0]}/{k[1]}": v for k, v in modes.most_common()}, "our_keys": len(ours),
           "dedupe_against": None if ours_dir is None else str(ours_dir)}
    (out / "dedupe_report.json").write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps(rep))
    print(f"wrote {len(tags)} replays to {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
