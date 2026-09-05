#!/usr/bin/env python
"""L61 COPY of research/sandbox_tools/replay_drive.py with per-play recording (record_plays=True): a FULL
observation (entities with kind, projectiles, effects, both players' hand/cycle/elixir, towers) is stored
immediately BEFORE every driven play of BOTH sides, at the play's tick, before the command is applied;
--record-every N adds a compact frame every N ticks (drift check).  Everything else is the original driver.

Replay one RoyaleAPI battle (crawl2) inside the real CR engine (cr-native-sandbox) and grade it.

What "convert a replay into a real match" means here: take the 20 Hz command timeline the crawler
recorded for one battle (icebow/data/royaleapi/crawl2/plays_ext.csv: tick, side, card, x, y in the
engine's own 1000-units-per-cell coordinates), feed every play into libg tick by tick through the
sandbox's JSON API, and let the engine's own verdicts grade the reconstruction:

  * every real play was legal, so a rejection (card not in hand, not enough elixir, bad placement)
    is a measured divergence between our reconstruction and the real match;
  * the final crowns / winner must equal what battles.csv recorded for that replay;
  * two runs of the same replay must end on the same state hash (engine determinism).

Deal order: libg deals the opening hand from rndSeed, the crawl does not record it, so the driver
(1) infers the set of (opening hand, draw-queue order) assignments consistent with each side's play
sequence (8C4 x 4! = 1680 candidates), (2) reads the engine's dealt positions at tick 0 for the seed,
(3) checks whether the deal is position-based (same positions after permuting the deck) and, if so,
permutes the deck so the dealt positions carry the inferred cards.  Anything it cannot establish is
reported as such -- nothing is assumed.

Run with the sandbox venv (native_core importable), service already up (scripts/smoke.ps1 -KeepRunning):
  research/ext/cr-native-sandbox/.venv/Scripts/python.exe research/sandbox_tools/replay_drive.py \
      --tag 08CPVRRR8PYC --port 37031 --runs 2
Offline check only (no engine):  ... --tag 08CPVRRR8PYC --offline
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SANDBOX = REPO / "research" / "ext" / "cr-native-sandbox"
CRAWL = REPO / "icebow" / "data" / "royaleapi" / "crawl2"
OUT_DIR = REPO / "scratchpad" / "gauntlet" / "ext"
if str(SANDBOX) not in sys.path:
    sys.path.insert(0, str(SANDBOX))

from native_core.card_catalog import catalog, card_cost, observed_card  # noqa: E402
from native_core.env import CARD_NAMES  # noqa: E402


def card_name(card_id: int) -> str:
    """Same naming as NativeRoyaleEnv._enrich_state uses for entities (base card name, else the form's internal name)."""
    card_id = int(card_id)
    if card_id < 0:
        return str(card_id)
    identity = observed_card(card_id)
    return CARD_NAMES.get(int(identity["base_card_id"]), str(identity["form_name"]))
from native_core.decks import build_replay, resolve_card  # noqa: E402
from native_core.env import NativeRoyaleEnv  # noqa: E402

# RoyaleAPI slug -> live_card_catalog internal_name where the alnum-normalised slug does not match.
# Each entry was checked against the catalog's card_id + elixir on 2026-09-01 (see HANDOFF 5aw); the
# two marked UNVERIFIED have an elixir that disagrees with the live game and must be confirmed against
# csv_logic before a replay containing them is trusted.
SLUG_ALIASES = {
    "archers": "Archer",
    "bandit": "Assassin",
    "barbarian-barrel": "BarbLog",
    "cannon-cart": "MovingCannon",
    "dart-goblin": "BlowdartGoblin",
    "elite-barbarians": "AngryBarbarians",
    "executioner": "AxeMan",
    "fire-spirit": "FireSpirits",
    "flying-machine": "DartBarrell",
    "furnace": "FirespiritHut",
    "giant-snowball": "Snowball",
    "guards": "SkeletonWarriors",
    "heal-spirit": "Heal",
    "ice-golem": "IceGolemite",
    "ice-spirit": "IceSpirits",
    "lumberjack": "RageBarbarian",
    "magic-archer": "EliteArcher",
    "mother-witch": "WitchMother",
    "night-witch": "DarkWitch",
    "royal-ghost": "Ghost",
    "rune-giant": "GiantBuffer",
    "skeleton-barrel": "SkeletonBalloon",
    "sparky": "ZapMachine",
    "spirit-empress": "MergeMaiden",
    "the-log": "Log",
    "void": "DarkMagic",        # UNVERIFIED: catalog elixir 5, live Void is 3
    "zappies": "MiniSparkys",
}
UNVERIFIED = {"void"}

# RoyaleAPI side -> engine side.  Measured on the crawl: "red" plays sit at y 500..14500 (rows 0..14 =
# engine side 0), "blue" plays at y 16500..31500 (rows 17..31 = engine side 1).  battles.csv's
# team_deck is the "blue" player.  Re-checked at runtime against the engine's own tower rows.
SIDE_OF = {"red": 0, "blue": 1}
DECK_COL_OF_SIDE = {0: "opponent_deck", 1: "team_deck"}
CROWN_COL_OF_SIDE = {0: "opponent_crowns", 1: "team_crowns"}
RESULT_CODE_NAMES = {0: "accepted", 9: "card_not_in_hand", 1014: "ability_exhausted", 1050: "not_enough_elixir"}


def split_slug(token: str) -> tuple[str, str]:
    """'knight-ev1' -> ('knight', 'evolution'); 'archer-queen-hero' -> (.., 'hero')."""
    if token.endswith("-ev1"):
        return token[:-4], "evolution"
    if token.endswith("-hero"):
        return token[:-5], "hero"
    return token, "base"


def card_for_slug(slug: str) -> int:
    name = SLUG_ALIASES.get(slug, slug)
    try:
        return resolve_card(name)
    except KeyError as exc:
        raise KeyError(f"RoyaleAPI slug {slug!r} has no catalog card (tried {name!r})") from exc


def load_battle(tag: str) -> tuple[dict, list[dict]]:
    with (CRAWL / "battles.csv").open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row["replay_tag"] == tag]
    if len(rows) != 1:
        raise SystemExit(f"battles.csv has {len(rows)} rows for {tag}")
    with (CRAWL / "plays_ext.csv").open(encoding="utf-8", newline="") as handle:
        plays = [row for row in csv.DictReader(handle) if row["replay_tag"] == tag]
    for row in plays:
        for key in ("tick", "play_index", "attr_ability"):
            if row[key] in ("", "None"):
                raise SystemExit(f"play {row['play_index']} of {tag} has no {key}")
        row["play_index"] = int(row["play_index"]); row["ability"] = int(row["attr_ability"])
        row["tick"] = int(row["tick"]); row["side"] = SIDE_OF[row["attr_s"]]
        if row["ability"]:
            # hero/evolution ability presses carry no card and no position in the crawl (attr_card "_invalid");
            # they are logged as skipped by drive(), not driven
            row["x"] = row["y"] = None
            continue
        for key in ("x_units", "y_units"):
            if row[key] in ("", "None"):
                raise SystemExit(f"play {row['play_index']} of {tag} has no {key}; replay is not fully positioned")
        row["x"] = int(row["x_units"]); row["y"] = int(row["y_units"])
    plays.sort(key=lambda row: (row["tick"], row["play_index"]))
    if int(rows[0]["plays"]) != len(plays):
        raise SystemExit(f"battles.csv says {rows[0]['plays']} plays, plays_ext.csv has {len(plays)}")
    return rows[0], plays


def deck_for_side(battle: dict, side: int) -> list[dict]:
    """[{slug, card_id, form, cost}] in the deck string's order."""
    deck = []
    for token in battle[DECK_COL_OF_SIDE[side]].split(","):
        slug, form = split_slug(token.strip())
        card_id = card_for_slug(slug)
        deck.append({"slug": slug, "card_id": card_id, "form": form, "cost": card_cost(card_id),
                     "name": catalog()[card_id]["internal_name"]})
    if len(deck) != 8 or len({item["card_id"] for item in deck}) != 8:
        raise SystemExit(f"side {side} deck is not 8 distinct cards: {battle[DECK_COL_OF_SIDE[side]]}")
    return deck


def infer_deals(play_cards: list[int], deck_ids: list[int]) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
    """All (opening hand, draw queue front-first) assignments under which every play is in hand.

    Cycle model (Clash Royale): 4 cards in hand, 4 in a queue; a played card goes to the back of the
    queue and the queue's front card enters the hand.  Verified on the data: the earliest repeat of a
    card in this replay's sequences is exactly 4 plays after its previous play.
    """
    found = []
    for hand in itertools.combinations(deck_ids, 4):
        rest = [card for card in deck_ids if card not in hand]
        for queue in itertools.permutations(rest):
            in_hand = set(hand); pending = list(queue); ok = True
            for card in play_cards:
                if card not in in_hand:
                    ok = False; break
                in_hand.remove(card); in_hand.add(pending.pop(0)); pending.append(card)
            if ok:
                found.append((tuple(hand), tuple(queue)))
    return found


def offline_report(tag: str) -> dict:
    battle, plays = load_battle(tag)
    report = {"tag": tag, "result": battle["result"], "team_crowns": int(battle["team_crowns"]),
              "opponent_crowns": int(battle["opponent_crowns"]), "plays": len(plays),
              "last_play_tick": plays[-1]["tick"], "abilities": sum(row["ability"] for row in plays), "sides": {}}
    for side in (0, 1):
        deck = deck_for_side(battle, side)
        by_slug = {item["slug"]: item for item in deck}
        side_plays = [row for row in plays if row["side"] == side and not row["ability"]]
        unknown = [row["attr_card"] for row in side_plays if row["attr_card"] not in by_slug]
        if unknown:
            raise SystemExit(f"side {side} plays cards outside its deck: {sorted(set(unknown))}")
        seq = [by_slug[row["attr_card"]]["card_id"] for row in side_plays]
        deals = infer_deals(seq, [item["card_id"] for item in deck])
        ys = sorted(row["y"] for row in side_plays)
        report["sides"][side] = {
            "deck": [f"{item['name']}@{item['form']}" if item["form"] != "base" else item["name"] for item in deck],
            "plays": len(side_plays), "elixir_spent": sum(by_slug[row["attr_card"]]["cost"] for row in side_plays),
            "y_min": ys[0], "y_max": ys[-1], "consistent_deals": len(deals),
            "unverified_slugs": sorted({item["slug"] for item in deck} & UNVERIFIED),
        }
        if deals:
            names = {item["card_id"]: item["name"] for item in deck}
            hand, queue = deals[0]
            report["sides"][side]["deal_example"] = {"hand": [names[c] for c in hand], "queue": [names[c] for c in queue]}
    return report


# ----------------------------------------------------------------------------------------------- engine

def player(state: dict, side: int) -> dict:
    return next(item for item in state["players"] if int(item["side"]) == side)


def tower_rows(state: dict) -> dict[int, list[float]]:
    rows: dict[int, list[float]] = {0: [], 1: []}
    for tower in state["episode"].get("crown_towers", []):
        rows[int(tower["side"])].append(int(tower["y"]) / 1000.0)
    return rows


def sp_order_for(deck: list[dict], hand_positions: list[int], cycle_positions: list[int],
                 deal: tuple[tuple[int, ...], tuple[int, ...]]) -> list[dict]:
    """Place the inferred opening hand on the engine's dealt hand positions and the inferred queue on
    the engine's cycle positions (front-first), so deck_index = position in the returned list."""
    hand_cards, queue_cards = deal
    by_id = {item["card_id"]: item for item in deck}
    order: list[dict | None] = [None] * 8
    for pos, card in zip(hand_positions, hand_cards):
        order[pos] = by_id[card]
    for pos, card in zip(cycle_positions, queue_cards):
        order[pos] = by_id[card]
    if any(item is None for item in order):
        raise RuntimeError(f"hand {hand_positions} + cycle {cycle_positions} do not cover 8 positions")
    return order  # type: ignore[return-value]


def deck_spec(order: list[dict], level: int) -> list[dict]:
    return [{"card_id": item["card_id"], "form": item["form"], "level": level} for item in order]


def drive(tag: str, *, port: int, seed: int, level: int, elixir_slack: int, tail_cap: int,
          run_label: str, verbose: bool, record_every: int = 0, record_full: bool = False,
          record_plays: bool = False) -> dict:
    """Drive one replay.  record_every=N (>0) additionally stores an observation every N ticks in
    out["frames"] (each: tick, players' elixir, every entity's side/x/y/name/hp) for a viewer;
    record_full=True uses the full observation (adds entity kind, projectiles and spell effects)."""
    battle, plays = load_battle(tag)
    decks = {side: deck_for_side(battle, side) for side in (0, 1)}
    template = json.loads((SANDBOX / "examples" / "full-card-bootstrap.json").read_text(encoding="utf-8-sig"))
    deals = {}
    for side in (0, 1):
        by_slug = {item["slug"]: item for item in decks[side]}
        seq = [by_slug[row["attr_card"]]["card_id"] for row in plays if row["side"] == side and not row["ability"]]
        found = infer_deals(seq, [item["card_id"] for item in decks[side]])
        if not found:
            raise SystemExit(f"side {side}: no (hand, queue) assignment reproduces the play sequence")
        deals[side] = {"n": len(found), "chosen": found[0]}

    env = NativeRoyaleEnv(port=port, timeout=120.0)
    out: dict = {"tag": tag, "run": run_label, "port": port, "seed": seed, "level": level,
                 "expected": {"result": battle["result"], "crowns_by_side": {0: int(battle["opponent_crowns"]),
                              1: int(battle["team_crowns"])}, "last_play_tick": plays[-1]["tick"]},
                 "deal_inference": {side: {"consistent": deals[side]["n"]} for side in (0, 1)}}

    # --- 1. dealt positions for this seed, canonical order --------------------------------------------
    t0 = time.perf_counter()
    order_a = {side: list(decks[side]) for side in (0, 1)}
    state = env.reset(build_replay(template, deck_spec(order_a[0], level), deck_spec(order_a[1], level), seed=seed),
                      warmup_steps=0)
    out["reset_seconds"] = round(time.perf_counter() - t0, 2)
    out["tick_after_reset"] = int(state["tick"])
    rows = tower_rows(state)
    out["tower_rows_by_side"] = rows
    orientation_ok = rows[0] and rows[1] and max(rows[0]) < 15.0 < min(rows[1])
    out["orientation"] = "side0 low rows / side1 high rows (matches RoyaleAPI red/blue)" if orientation_ok else "UNEXPECTED"
    if not orientation_ok:
        raise SystemExit(f"tower rows do not match the assumed orientation: {rows}")
    dealt_a = {side: (list(player(state, side)["hand_deck_indices"]), list(player(state, side)["cycle_deck_indices"]),
                      int(player(state, side)["next_deck_index"])) for side in (0, 1)}
    out["deal_probe"] = {"canonical": {side: {"hand_pos": dealt_a[side][0], "cycle_pos": dealt_a[side][1],
                                              "next": dealt_a[side][2]} for side in (0, 1)}}

    # --- 2. is the deal position-based?  reverse the deck, same seed --------------------------------
    order_b = {side: list(reversed(decks[side])) for side in (0, 1)}
    state = env.reset(build_replay(template, deck_spec(order_b[0], level), deck_spec(order_b[1], level), seed=seed),
                      warmup_steps=0)
    dealt_b = {side: (list(player(state, side)["hand_deck_indices"]), list(player(state, side)["cycle_deck_indices"]))
               for side in (0, 1)}
    out["deal_probe"]["reversed"] = {side: {"hand_pos": dealt_b[side][0], "cycle_pos": dealt_b[side][1]} for side in (0, 1)}
    position_based = all(sorted(dealt_a[s][0]) == sorted(dealt_b[s][0]) and dealt_a[s][1] == dealt_b[s][1] for s in (0, 1))
    same_cards = all(sorted(order_a[s][i]["card_id"] for i in dealt_a[s][0]) == sorted(order_b[s][i]["card_id"] for i in dealt_b[s][0])
                     for s in (0, 1))
    out["deal_probe"]["position_based"] = bool(position_based)
    out["deal_probe"]["same_cards_after_permute"] = bool(same_cards)

    # --- 3. final deck order ------------------------------------------------------------------------
    if position_based:
        final = {side: sp_order_for(decks[side], dealt_a[side][0], dealt_a[side][1], deals[side]["chosen"]) for side in (0, 1)}
        out["deal_strategy"] = "permuted deck so dealt positions carry the inferred hand/queue"
    else:
        final = order_a
        out["deal_strategy"] = "NOT position-based: playing canonical order, expect card_not_in_hand rejections"
    out["final_decks"] = {side: [f"{item['name']}@{item['form']}" if item["form"] != "base" else item["name"]
                                for item in final[side]] for side in (0, 1)}
    index_of = {side: {item["slug"]: idx for idx, item in enumerate(final[side])} for side in (0, 1)}
    cost_of = {side: {item["slug"]: item["cost"] for item in final[side]} for side in (0, 1)}
    replay = build_replay(template, deck_spec(final[0], level), deck_spec(final[1], level), seed=seed)
    state = env.reset(replay, warmup_steps=0)
    out["opening_hand"] = {side: [item["name"] for item in player(state, side)["hand"]] for side in (0, 1)}
    out["opening_state_hash"] = state.get("state_hash")
    tick = int(state["tick"])

    # --- 4. drive the timeline ----------------------------------------------------------------------
    log: list[dict] = []
    frames: list[dict] = []

    play_frames: list[dict] = []

    def snapshot(state: dict, full: bool = False, extra: dict | None = None, into: list | None = None) -> None:
        record_full_ = record_full or full
        frame = {"tick": int(state["tick"]),
                 "elixir": [player(state, s).get("elixir_exact", player(state, s).get("elixir")) for s in (0, 1)],
                 "entities": [[int(e["side"]), int(e["x"]), int(e["y"]), e.get("name", str(e.get("card_id"))),
                               int(e["hp"]), int(e["max_hp"])] + ([int(e.get("kind", -1))] if record_full_ else [])
                              for e in state.get("entities", [])],
                 "towers": [[int(t["side"]), t.get("type"), t.get("lane"), int(t["x"]), int(t["y"]), int(t["hp"]),
                             int(t["max_hp"])] for t in state["episode"].get("crown_towers", [])]}
        if record_full_:
            frame["projectiles"] = [[int(q["side"]), int(q["x"]), int(q["y"]), int(q["target_x"]), int(q["target_y"]),
                                     card_name(q["card_id"])] for q in state.get("projectiles", [])]
            frame["effects"] = [[int(q["side"]), int(q["x"]), int(q["y"]), card_name(q["card_id"])]
                                for q in state.get("effects", [])]
        if extra:
            frame.update(extra)
            frame["players"] = [{"side": int(pl["side"]), "elixir": pl.get("elixir_exact", pl.get("elixir")),
                                 "hand": [item["name"] for item in pl["hand"]],
                                 "hand_pos": list(pl["hand_deck_indices"]), "cycle_pos": list(pl.get("cycle_deck_indices", [])),
                                 "next": pl.get("next_deck_index")} for pl in state["players"]]
        (frames if into is None else into).append(frame)

    def observe_for_record() -> dict:
        return env.observe() if record_full else env.observe_compact()

    def advance(n: int) -> dict:
        """env.step(n), split into record_every-sized chunks with a compact observation after each when recording."""
        if record_every <= 0:
            return env.step(n)
        step = None
        while n > 0:
            chunk = min(record_every, n)
            step = env.step(chunk); n -= chunk
            snapshot(observe_for_record())
            if step["episode"].get("terminated") or int(step.get("stepped", 1)) == 0:
                break
        return step

    if record_every > 0:
        snapshot(observe_for_record())
    terminated = False
    t_drive = time.perf_counter()
    for row in plays:
        side = row["side"]; slug = row["attr_card"]
        if row["tick"] > tick:
            step = advance(row["tick"] - tick)
            tick = int(step["tick_after"])
            if step["episode"].get("terminated"):
                terminated = True
                log.append({"play_index": row["play_index"], "tick": row["tick"], "side": side, "card": slug,
                            "skipped": "episode already terminal at tick %d" % tick})
                break
        if row["ability"]:
            log.append({"play_index": row["play_index"], "tick": row["tick"], "side": side, "card": slug,
                        "skipped": "ability plays not driven by this version"})
            continue
        if record_plays:
            obs_before = env.observe()
            snapshot(obs_before, full=True, extra={"play_index": row["play_index"], "side": side, "card": slug,
                                                   "x": row["x"], "y": row["y"]}, into=play_frames)
            before = player(obs_before, side)
        else:
            before = player(env.observe_compact(), side)
        entry = {"play_index": row["play_index"], "tick": row["tick"], "side": side, "card": slug,
                 "x": row["x"], "y": row["y"], "cost": cost_of[side][slug],
                 "elixir_before": before.get("elixir_exact", before.get("elixir")),
                 "hand_before": [item["name"] for item in before["hand"]], "delay_ticks": 0}
        result = env.act(side=side, deck_index=index_of[side][slug], x=row["x"], y=row["y"])
        while (not result["accepted"] and int(result["result_code"]) == 1050
               and entry["delay_ticks"] < elixir_slack):
            step = env.step(1); tick = int(step["tick_after"]); entry["delay_ticks"] += 1
            if step["episode"].get("terminated"):
                terminated = True; break
            result = env.act(side=side, deck_index=index_of[side][slug], x=row["x"], y=row["y"])
        entry.update({"accepted": bool(result["accepted"]), "result_code": int(result["result_code"]),
                      "result_name": RESULT_CODE_NAMES.get(int(result["result_code"]), "native_rejected"),
                      "hand_index": result.get("hand_index"), "placement_valid": result.get("placement_valid"),
                      "placement_reason": result.get("placement_reason"), "engine_tick": result.get("tick")})
        log.append(entry)
        if verbose:
            print(f"  t={row['tick']:5d} s{side} {slug:12s} ({row['x']:5d},{row['y']:5d}) el={entry['elixir_before']} "
                  f"-> {'OK' if entry['accepted'] else entry['result_name']} delay={entry['delay_ticks']} "
                  f"{'' if entry['placement_valid'] else entry['placement_reason']}", flush=True)
        if terminated:
            break

    # --- 5. run out the clock -----------------------------------------------------------------------
    episode = env.last_episode or {}
    while not episode.get("terminated") and tick < tail_cap:
        step = advance(min(200, tail_cap - tick)); tick = int(step["tick_after"]); episode = step["episode"]
        if int(step.get("stepped", 1)) == 0:
            break
    final_state = env.observe()
    out["drive_seconds"] = round(time.perf_counter() - t_drive, 2)
    out["final"] = {"tick": int(final_state["tick"]), "terminated": bool(episode.get("terminated")),
                    "outcome": episode.get("outcome"), "winner": episode.get("winner"), "crowns": episode.get("crowns"),
                    "termination_reason": episode.get("termination_reason"), "terminal_tick": episode.get("terminal_tick"),
                    "state_hash": final_state.get("state_hash"),
                    "towers": [{"side": t["side"], "type": t.get("type"), "lane": t.get("lane"), "hp": t["hp"],
                                "destroyed": t.get("destroyed")} for t in final_state["episode"].get("crown_towers", [])],
                    "elixir": {side: player(final_state, side).get("elixir_exact") for side in (0, 1)}}

    # --- 6. grade -----------------------------------------------------------------------------------
    driven = [e for e in log if "accepted" in e]
    out["grade"] = {
        "plays_total": len(plays), "plays_driven": len(driven),
        "accepted": sum(e["accepted"] for e in driven),
        "rejected_by_reason": dict(Counter(e["result_name"] for e in driven if not e["accepted"])),
        "invalid_placement": sum(1 for e in driven if e["placement_valid"] is False),
        "elixir_delays": {"n": sum(1 for e in driven if e["delay_ticks"]), "max_ticks": max([e["delay_ticks"] for e in driven] or [0]),
                          "sum_ticks": sum(e["delay_ticks"] for e in driven)},
        "skipped": [e for e in log if "skipped" in e],
        "crowns_match": (out["final"]["crowns"] is not None and
                         [int(c) for c in out["final"]["crowns"]] == [out["expected"]["crowns_by_side"][0], out["expected"]["crowns_by_side"][1]]),
        "terminal_vs_last_play_ticks": (int(out["final"]["terminal_tick"]) - plays[-1]["tick"]) if out["final"].get("terminal_tick") else None,
    }
    out["log"] = log
    if record_every > 0:
        out["frames"] = frames
        out["record_every"] = record_every
        out["record_full"] = record_full
    if record_plays:
        out["play_frames"] = play_frames
    env.close()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--port", type=int, default=37031)
    parser.add_argument("--seed", type=int, default=424242)
    parser.add_argument("--level", type=int, default=11, help="card level for both sides (crawl has none; 11 = tournament)")
    parser.add_argument("--elixir-slack", type=int, default=40, help="max ticks to wait when libg says not enough elixir")
    parser.add_argument("--tail-cap", type=int, default=7200, help="stop stepping at this tick if no terminal")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--offline", action="store_true", help="no engine: decks, deal inference, sanity only")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--record-every", type=int, default=0,
                        help="store an observation every N ticks in the result JSON (for replay_view.py)")
    parser.add_argument("--record-full", action="store_true",
                        help="record the full observation (entity kind, projectiles, spell effects) instead of the compact one")
    parser.add_argument("--record-plays", action="store_true", help="full observation before every driven play (both sides)")
    args = parser.parse_args()

    if args.offline:
        print(json.dumps(offline_report(args.tag), indent=1))
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hashes = []
    for run in range(1, args.runs + 1):
        print(f"=== {args.tag} run {run}/{args.runs} port {args.port} seed {args.seed} level {args.level}", flush=True)
        result = drive(args.tag, port=args.port, seed=args.seed, level=args.level, elixir_slack=args.elixir_slack,
                       tail_cap=args.tail_cap, run_label=f"run{run}", verbose=not args.quiet,
                       record_every=args.record_every, record_full=args.record_full, record_plays=args.record_plays)
        path = OUT_DIR / f"replay_{args.tag}_run{run}.json"
        path.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
        hashes.append(result["final"]["state_hash"])
        grade = result["grade"]; final = result["final"]
        print(f"deal: {result['deal_strategy']} | probe {result['deal_probe']['canonical']} position_based={result['deal_probe']['position_based']}")
        print(f"opening hands: {result['opening_hand']}")
        print(f"accepted {grade['accepted']}/{grade['plays_driven']} (of {grade['plays_total']}), rejected {grade['rejected_by_reason']}, "
              f"invalid placement {grade['invalid_placement']}, elixir delays {grade['elixir_delays']}")
        print(f"final: tick {final['tick']} terminated={final['terminated']} outcome={final['outcome']} crowns={final['crowns']} "
              f"reason={final['termination_reason']} expected crowns {result['expected']['crowns_by_side']} -> match={grade['crowns_match']}; "
              f"terminal - last play = {grade['terminal_vs_last_play_ticks']} ticks; hash {final['state_hash']}")
        print(f"timing: reset {result['reset_seconds']} s, drive+tail {result['drive_seconds']} s -> {path}")
    if len(hashes) > 1:
        print(f"determinism across runs: {'SAME' if len(set(hashes)) == 1 else 'DIFFERENT'} {hashes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
