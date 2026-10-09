"""Recording -> a driven-corpus record (replay_<tag>.json) that pipeline.dataset_gen reads directly. L74.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/to_record.py REC.jsonl [--out DIR]
    icebow/.venv/Scripts/python.exe -m pipeline.dataset_gen --corpus DIR --out rows.npz --feature-version 4

Why: the crawl path (CSV -> sandbox engine re-drive on the VM -> replay_*.json) RE-SIMULATES each battle; a recording
already holds the REAL game states, so this writes them in the re-drive's own schema (L61/replay_drive_rec.py with
--record-full --record-native: frames / play_frames / log / final_decks) and skips the engine.

Public-only rule, kept exactly as the crawl corpora keep it:
  * play_frames carry ONLY the acting side's player block (hand / next / elixir); the re-drive stored both.
  * frames carry both sides' OWN elixir in `elixir` (each side's wait rows read their own); dataset_gen at
    feature_version >= 4 overwrites the opponent-elixir column with the PUBLIC estimate (replay_rows: sc[:, 5]) and
    takes opponent plays from recording_observers (public bodies / projectiles / effects), never from the log.
  * test_to_record.py proves it: scrambling one side's hand / next / elixir / log leaves the OTHER side's rows
    byte-identical.
Mapping: entity_id = the reader's `category` (the engine's entity id, 5000000+); entity rows [side, x, y, name, hp,
max_hp, kind, card_id, entity_id]; towers [side, type, lane, x, y, hp, max_hp]; projectiles [side, x, y, tx, ty, name];
reader effects -> `area_effects` [side, x, y, name] (the re-drive lacks them: recording_tokens counts that as
unavailable). An unpositioned play stays in the log as accepted=False (no row; counted by build_replay).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import convert as cv  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402

SUFFIX = {0: "", 1: "@evolution", 2: "@hero"}


def name_of(cid: int) -> str:
    return catalog_card_form(int(cid))[0] or str(cid)


def towers(frame) -> list:
    out = []
    for e in frame.get("entities") or ():
        if int(e.get("card_id", 0)) != -1 or int(e["side"]) not in (0, 1):
            continue
        x, y = float(e["x"]), float(e["y"])
        if abs(x - 9000) < 1500 and min(abs(y - 3000), abs(y - 29000)) < 1500:
            out.append([int(e["side"]), "king", None, e["x"], e["y"], e["hp"], e["max_hp"]])
        elif min(abs(x - 3500), abs(x - 14500)) < 1500 and min(abs(y - 6500), abs(y - 25500)) < 1500:
            out.append([int(e["side"]), "princess", "left" if x < 9000 else "right", e["x"], e["y"], e["hp"], e["max_hp"]])
    return out


def player(p, deck_names, hand) -> dict:
    """`hand` = the last FULL hand seen before the play (the pre-act frame can already show the emptied slot)."""
    return {"side": int(p["side"]), "elixir": p["elixir_raw"] / 1e4, "hand": [deck_names[i] for i in hand],
            "hand_pos": hand, "cycle_pos": list(p.get("cycle_deck_indices") or []), "next": p["next_deck_index"]}


def native_frame(f) -> dict:
    ents = [[e["side"], e["x"], e["y"], "-1" if int(e["card_id"]) < 0 else name_of(e["card_id"]), e["hp"], e["max_hp"],
             e.get("kind", -1), int(e["card_id"]), int(e["category"])] for e in f.get("entities") or ()]
    el = {int(p["side"]): p["elixir_raw"] / 1e4 for p in f.get("players") or ()}
    return {"tick": int(f["game_tick"]), "elixir": [el.get(0, 0.0), el.get(1, 0.0)], "entities": ents,
            "towers": towers(f),
            "projectiles": [[o["side"], o["x"], o["y"], o.get("target_x"), o.get("target_y"),
                             "-1" if int(o["card_id"]) < 0 else name_of(o["card_id"])] for o in f.get("projectiles") or ()],
            "area_effects": [[o["side"], o["x"], o["y"], "-1" if int(o["card_id"]) < 0 else name_of(o["card_id"])]
                             for o in f.get("effects") or ()]}


def to_record(path: Path, tag: str | None = None) -> dict:
    res = cv.convert(path, tag)
    if res["mode"] != "hand":
        raise SystemExit(f"{path}: hands not visible -- no own-hand rows can be built")
    _, frames = cv.battle_frames(path)
    plays = sorted(cv.hand_plays(frames), key=lambda e: (e["tick"], e["side"]))
    decks = {}
    for f in frames:
        for p in f["players"]:
            if int(p["side"]) not in decks and len(p.get("deck_card_ids") or ()) == 8:
                decks[int(p["side"])] = (p["deck_card_ids"], p["deck_form_flags"])
    base = {s: [name_of(c) for c in ids] for s, (ids, _) in decks.items()}
    final = {str(s): [name_of(c) + SUFFIX[int(fl)] for c, fl in zip(ids, flags)] for s, (ids, flags) in decks.items()}
    log, pframes = [], []
    for k, e in enumerate(plays):
        pre = frames[max(0, e["frame"] - 1)]                  # the last state before the hand rotated
        ok = e["x"] is not None
        log.append(dict(play_index=k, tick=e["tick"], side=e["side"], card=e["card"], x=round(e["x"]) if ok else None,
                        y=round(e["y"]) if ok else None, accepted=ok, hand_before=[base[e["side"]][i] for i in e["hand_before"]],
                        actual_form=e["form"], **({} if ok else {"skipped": "unpositioned"})))
        me = next(p for p in pre["players"] if int(p["side"]) == e["side"])
        pframes.append(dict(native_frame(pre), play_index=k, side=e["side"], card=e["card"], x=log[-1]["x"],
                            y=log[-1]["y"], players=[player(me, base[e["side"]], e["hand_before"])]))
    b = res["battle"]
    steps = sorted(int(b2["game_tick"]) - int(a2["game_tick"]) for a2, b2 in zip(frames, frames[1:]))
    return {"tag": b["replay_tag"], "source": "in_game_replay_reader", "recording": str(path),
            "final_decks": final, "expected": {"crowns_by_side": {"0": b["opponent_crowns"], "1": b["team_crowns"]},
                                               "result_team": b["result"]},
            "record_native": True, "record_full": True, "record_every": max(1, steps[len(steps) // 2]) if steps else 20,
            "log": log, "play_frames": pframes, "frames": [native_frame(f) for f in frames]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording")
    ap.add_argument("--out", help="corpus dir (default: <recording stem>_corpus/)")
    a = ap.parse_args()
    rec_path = Path(a.recording)
    rec = to_record(rec_path)
    out = Path(a.out) if a.out else rec_path.with_name(rec_path.stem + "_corpus")
    out.mkdir(parents=True, exist_ok=True)
    p = out / f"replay_{rec['tag']}.json"
    p.write_text(json.dumps(rec), encoding="utf-8")
    print(json.dumps(dict(out=str(p), plays=len(rec["log"]), accepted=sum(e["accepted"] for e in rec["log"]),
                          frames=len(rec["frames"]), record_every=rec["record_every"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
