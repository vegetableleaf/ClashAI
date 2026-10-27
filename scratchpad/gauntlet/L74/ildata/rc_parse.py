"""RoyaleAPI replay crawl (ticket D2b): pure parsing + the IL_Replay-compatible parquet schema. No network, no state.

Parsing helpers are copied from C:/Users/benpe/clash-replay-scraper/royale/parse.py (battles, next_history_page,
replay_ext) so this folder is self-contained. The output rows reproduce royaleapi-replay-parquet.v1 (replays + actions
tables, payload_json / event_json shapes) as read from icebow/data/ildata_samples/hf_il_replay; the coordinate rule
was derived from the 57,432 positioned events of the sample and test_rc.py reproduces 28,394 of them exactly.

Not in the replay payload (measured on 614 saved payloads): card levels, tower hitpoints, game version. The raw
history-row HTML is kept by the crawler so levels can be re-parsed later if the row carries them.
"""
from __future__ import annotations

import json
import re

import pyarrow as pa
from bs4 import BeautifulSoup

SCHEMA_VERSION = "royaleapi-replay-parquet.v1"
PAYLOAD_SCHEMA = "royaleapi-battle-actions.v1"
COLLECTION_SCHEMA = "royaleapi-replay-collection.v1"
TPS = 20

REPLAYS_SCHEMA = pa.schema([
    ("schema_version", pa.string()), ("replay_tag", pa.string()), ("battle_type", pa.string()),
    ("game_mode", pa.string()), ("result", pa.string()), ("team_crowns", pa.int16()),
    ("opponent_crowns", pa.int16()), ("event_count", pa.int32()), ("warning_count", pa.int32()),
    ("payload_json", pa.large_string()), ("requested_player_tag", pa.string())])
ACTIONS_SCHEMA = pa.schema([
    ("schema_version", pa.string()), ("replay_tag", pa.string()), ("event_index", pa.int32()),
    ("source_index", pa.int32()), ("kind", pa.string()), ("side", pa.string()), ("card_key", pa.string()),
    ("card_play_number", pa.int32()), ("replay_tick_20hz", pa.int32()), ("time_seconds", pa.float64()),
    ("form_at_play", pa.string()), ("ability_source_authoritative", pa.bool_()), ("native_x", pa.int32()),
    ("native_y", pa.int32()), ("grid_x", pa.int32()), ("grid_y", pa.int32()), ("arena_column", pa.string()),
    ("arena_row", pa.int32()), ("deck_card_key_candidates", pa.list_(pa.field("element", pa.string()))),
    ("ability_source_candidates", pa.list_(pa.field("element", pa.string()))), ("event_json", pa.large_string())])

# battle_type (history row class) -> game_mode string as the HF set labels it. Only pathOfLegend/friendly are
# seen in the sample; anything else keeps its raw battle_type as the mode (untested labels).
GAME_MODE = {"pathOfLegend": "Ranked", "friendly": "1v1 Battle"}
RESULT = {"win": "victory", "loss": "defeat", "draw": "draw"}
# Cards that can activate an ability: every *-hero plus the champions seen in the 852-replay sample (a new champion is
# missed until added here; only the informational ability_source_candidates column is affected).
CHAMPIONS = {"archer-queen", "boss-bandit", "goblinstein", "golden-knight", "little-prince", "mighty-miner", "monk",
             "skeleton-king"}
TAG = re.compile(r"^/player/([0-9A-Z]+)/?$")


def base_key(k: str) -> str:
    return re.sub(r"-(?:ev\d+|hero)$", "", k)


# ------------------------------------------------------------------ listing / history pages
def leaderboard_tags(html: str) -> list[str]:
    """Every /player/<TAG> link on a leaderboard / clan / deck page, page order, deduped."""
    out: dict[str, None] = {}
    for a in BeautifulSoup(html, "lxml").select("a[href^='/player/']"):
        m = TAG.match(a["href"])
        if m:
            out.setdefault(m.group(1))
    return list(out)


def _epoch(raw: str) -> int:
    try:
        return int(float(raw))
    except ValueError:
        return 0


def history_rows(html: str) -> list[dict]:
    """One dict per battle row that has a replay button (same fields as the old parse.battles) + row_html."""
    out = []
    for row in BeautifulSoup(html, "lxml").select("div.battle_list_battle"):
        rb = row.select_one("button.replay_button")
        if not rb:
            continue
        mb = row.select_one("button.matchup_button")
        ts = row.select_one(".battle-timestamp-popup")
        classes = set(row.get("class", []))
        out.append({
            "replay_tag": rb["data-replay"],
            "battle_time": ts.get("data-content", "") if ts else "",
            "battle_timestamp": _epoch(row.get("data-timestamp", "")),
            "battle_type": next((c[len("battletype-"):] for c in classes if c.startswith("battletype-")), ""),
            "result": "win" if "blue" in classes else "loss" if "red" in classes else "draw",
            "team_tags": rb.get("data-team-tags", ""),
            "opponent_tags": rb.get("data-opponent-tags", ""),
            "team_crowns": rb.get("data-team-crowns", ""),
            "opponent_crowns": rb.get("data-opponent-crowns", ""),
            "team_deck": mb.get("data-team-deck", "") if mb else "",
            "opponent_deck": mb.get("data-opponent-deck", "") if mb else "",
            "row_html": str(row),
        })
    return out


def next_history_page(html: str) -> str | None:
    """The 'older battles' link (right chevron, ?before=<oldest battle ms>); None on the last page."""
    for a in BeautifulSoup(html, "lxml").select("a[href*='battles/history?before=']"):
        icon = a.select_one("i.icon")
        if icon and "right" in icon.get("class", []):
            return a["href"]
    return None


def history_page(html: str) -> tuple[list[dict], int, str | None]:
    """(rows with a replay button, total battle rows on the page, next-page path)."""
    return history_rows(html), len(BeautifulSoup(html, "lxml").select("div.battle_list_battle")), next_history_page(html)


def pair_key(row: dict) -> str:
    """Same battle seen from either player's history -> same key (sorted tags + timestamp). (b) untested that both
    perspectives' replays are the same recording; the crawler's --no-pair-dedupe turns this off."""
    return "|".join(sorted([row["team_tags"], row["opponent_tags"]])) + f"@{row['battle_timestamp']}"


# ------------------------------------------------------------------ replay payload
def _tables(d) -> dict:
    """side -> {total/troop/building/spell/ability: [count, elixir], leaked: float} from the two elixir tables."""
    out = {}
    for side, table in zip(("team", "opponent"), d.select("table.replay_elixir_table")):
        v = {}
        for tr in table.select("tr"):
            cells = [td.get_text(strip=True) for td in tr.select("td, th")]
            if len(cells) < 2:
                continue
            key = cells[0].lower()
            try:
                if key == "leaked":
                    v["leaked"] = float(cells[1])
                elif len(cells) >= 3:
                    v[key] = [int(cells[1]), int(cells[2])]
            except ValueError:
                pass
        out[side] = v
    return out


def parse_replay(html: str) -> dict:
    """/data/replay html -> {tag, plays (old replay_ext rows), stats, seat_i}. plays carry x_units/y_units/attr_*."""
    d = BeautifulSoup(html, "lxml")
    root = d.select_one(".battle_replay")
    side_of = {"t": "blue", "o": "red"}
    markers: dict = {}
    for m in d.select(".marker"):
        if not m.get("data-t"):
            continue
        key = (m.get("data-t", ""), m.get("data-c", ""), side_of.get(m.get("data-s", ""), ""))
        markers.setdefault(key, []).append((m.get("data-x", ""), m.get("data-y", ""), m.get("data-i", "")))
    cards = sorted(d.select(".replay_timeline .replay_card"), key=lambda c: int(c.get("data-t", 0)))
    plays, seats = [], {}
    for i, c in enumerate(cards):
        row = {("attr_" + k[5:]): v for k, v in c.attrs.items() if k.startswith("data-")}
        lst = markers.get((c.get("data-t", ""), c.get("data-card", ""), c.get("data-s", "")))
        mx = lst.pop(0) if lst else None
        if mx:
            row["x_units"], row["y_units"], row["attr_i"] = mx[0], mx[1], mx[2]
            seats[mx[2]] = seats.get(mx[2], 0) + 1
        row.update({"play_index": i, "tick": int(c.get("data-t", 0))})
        plays.append(row)
    seat = max(seats, key=seats.get) if seats else "0"      # markers of one replay share a seat flag (HANDOFF L64h)
    return {"tag": root.get("data-tag", "") if root else "", "plays": plays, "stats": _tables(d), "seat_i": int(seat or 0)}


# ------------------------------------------------------------------ events (HF actions shape)
def coordinates(raw_x: int, raw_y: int, seat_i: int) -> dict:
    """Derived from the sample (all 57,432 positioned events): seat 0 -> native (x, 32000-y), seat 1 ->
    (18000-x, y); display y = 32000 - native y; grid = native // 1000; arena label column A.., row = grid_y + 1."""
    nx, ny = (18000 - raw_x, raw_y) if seat_i else (raw_x, 32000 - raw_y)
    gx, gy = nx // 1000, ny // 1000
    return {
        "arena_label_from_blue": {"column": chr(65 + gx), "row": gy + 1},
        "display_royaleapi_units": {"x": nx, "y": 32000 - ny},
        "grid_cell_floor": {"x": gx, "y": gy},
        "inside_18x32_arena": 0 <= nx < 18000 and 0 <= ny < 32000,
        "inversion_applied": bool(seat_i),
        "native_world_units": {"x": nx, "y": ny},
        "raw_royaleapi_units": {"x": raw_x, "y": raw_y},
        "subcell_offset_from_floor_center": {"x": round((nx % 1000 - 500) / 1000, 3),
                                              "y": round((ny % 1000 - 500) / 1000, 3)},
    }


def build_events(plays: list[dict], decks: dict, seat_i: int) -> tuple[list[dict], int]:
    """plays (parse_replay rows) + decks {'team': [keys], 'opponent': [keys]} -> (events, warnings)."""
    events, warnings, counts = [], 0, {}
    for n, p in enumerate(sorted(plays, key=lambda p: (p["tick"], p["play_index"]))):
        side = "team" if p.get("attr_s") == "blue" else "opponent"
        ability = str(p.get("attr_ability", "0")) == "1"
        tick = p["tick"]
        card = None if ability else p.get("attr_card")
        counts[(side, card)] = counts.get((side, card), 0) + 1
        has_xy = not ability and p.get("x_units") not in (None, "")
        raw_x = int(p["x_units"]) if has_xy else None
        raw_y = int(p["y_units"]) if has_xy else None
        if not ability and not has_xy:
            warnings += 1                                   # timeline card with no map marker
        deck = decks.get(side, [])
        events.append({
            "ability_source_authoritative": False if ability else None,
            "ability_source_candidates": sorted(k for k in deck if k.endswith("-hero") or k in CHAMPIONS) if ability else [],
            "card_key": card,
            "card_play_number": counts[(side, card)],
            "coordinates": coordinates(raw_x, raw_y, seat_i) if has_xy else None,
            "deck_card_key_candidates": [] if ability else [k for k in deck if base_key(k) == card],
            "form_at_play": None if ability else "unknown",
            "kind": "activate_ability" if ability else "play_card",
            "replay_tick_20hz": tick,
            "side": side,
            "source_fields": {
                "data_c": "_invalid" if ability else card, "data_i": seat_i,
                "data_s": "t" if side == "team" else "o", "data_t": tick,
                "data_x": raw_x, "data_y": raw_y, "timeline_card_key": "_invalid" if ability else card},
            "source_index": n,
            "time_seconds": round(tick / TPS, 2),
        })
    return events, warnings


def _dump(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"))


def build_record(row: dict, replay_html: str, requested_player_tag: str) -> tuple[dict, list[dict]]:
    """history row + /data/replay html -> (one replays-table row, action rows). Raises ValueError on an empty replay."""
    rep = parse_replay(replay_html)
    if not rep["plays"]:
        raise ValueError("replay has no timeline cards")
    decks = {"team": [k for k in row["team_deck"].split(",") if k],
             "opponent": [k for k in row["opponent_deck"].split(",") if k]}
    events, warnings = build_events(rep["plays"], decks, rep["seat_i"])
    crowns = {"team": int(row["team_crowns"] or 0), "opponent": int(row["opponent_crowns"] or 0)}
    bt = row["battle_type"]

    def side_block(s):
        st = rep["stats"].get(s, {})
        return {"crowns": crowns[s], "players": [{
            "deck": [{"card_key": k, "level": None} for k in decks[s]], "elixir_leaked": st.get("leaked")}]}

    card_counts = {"team": {}, "opponent": {}}
    for e in events:
        if e["kind"] == "play_card":
            card_counts[e["side"]][e["card_key"]] = card_counts[e["side"]].get(e["card_key"], 0) + 1
    payload = {
        "battle": {"battle_type": bt, "game_mode": GAME_MODE.get(bt, bt), "result": RESULT[row["result"]],
                   "team": side_block("team"), "opponent": side_block("opponent")},
        "collection_schema_version": COLLECTION_SCHEMA,
        "events": events,
        "replay": {"aggregate_stats": rep["stats"], "card_counts": card_counts},
        "schema_version": PAYLOAD_SCHEMA,
        # our crawl keeps the tags and the battle time (the HF set stripped them)
        "source": {"anonymized": False, "replay_tag": row["replay_tag"], "site": "RoyaleAPI",
                   "battle_time": row["battle_time"], "battle_timestamp": row["battle_timestamp"],
                   "team_tags": row["team_tags"], "opponent_tags": row["opponent_tags"]},
        "validation": {"ability_event_count": sum(e["kind"] != "play_card" for e in events),
                       "coordinate_event_count": sum(e["coordinates"] is not None for e in events),
                       "normalized_event_count": len(events), "timeline_event_count": len(rep["plays"]),
                       "unmatched_timeline_event_count": warnings},
    }
    rrow = {"schema_version": SCHEMA_VERSION, "replay_tag": row["replay_tag"], "battle_type": bt,
            "game_mode": GAME_MODE.get(bt, bt), "result": RESULT[row["result"]],
            "team_crowns": crowns["team"], "opponent_crowns": crowns["opponent"], "event_count": len(events),
            "warning_count": warnings, "payload_json": _dump(payload), "requested_player_tag": requested_player_tag}
    return rrow, [action_row(row["replay_tag"], i, e) for i, e in enumerate(events)]


def action_row(tag: str, index: int, e: dict) -> dict:
    co = e["coordinates"]
    nat = co["native_world_units"] if co else {}
    grid = co["grid_cell_floor"] if co else {}
    lab = co["arena_label_from_blue"] if co else {}
    return {"schema_version": SCHEMA_VERSION, "replay_tag": tag, "event_index": index, "source_index": e["source_index"],
            "kind": e["kind"], "side": e["side"], "card_key": e["card_key"], "card_play_number": e["card_play_number"],
            "replay_tick_20hz": e["replay_tick_20hz"], "time_seconds": e["time_seconds"],
            "form_at_play": e["form_at_play"], "ability_source_authoritative": e["ability_source_authoritative"],
            "native_x": nat.get("x"), "native_y": nat.get("y"), "grid_x": grid.get("x"), "grid_y": grid.get("y"),
            "arena_column": lab.get("column"), "arena_row": lab.get("row"),
            "deck_card_key_candidates": e["deck_card_key_candidates"],
            "ability_source_candidates": e["ability_source_candidates"], "event_json": _dump(e)}


def to_tables(replay_rows: list[dict], action_rows: list[dict]) -> tuple[pa.Table, pa.Table]:
    return (pa.Table.from_pylist(replay_rows, schema=REPLAYS_SCHEMA),
            pa.Table.from_pylist(action_rows, schema=ACTIONS_SCHEMA))
