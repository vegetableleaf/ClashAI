"""Recording of a spectated battle (recorder.py) -> crawl-format rows for BOTH sides (L74 replay_rec).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/convert.py REC.jsonl [--out DIR]

Writes DIR/battles.csv (1 row) + DIR/plays_ext_i1.csv, the crawl2 schema research/sandbox_tools/replay_drive.py and
the corpus builders read (columns as hogeq/data/royaleapi/crawl2/*.csv), plus extra columns form / detect / located.
Crawl conventions kept: attr_s red = engine side 0 (low y), blue = side 1; team_* = blue; attr_i 0 = native frame (no
rotation); attr_card is the BASE slug on every play row (L67 hero_ability_data.md Q2: a hero shows only in the deck
string, `-ev1` / `-hero`); an unpositioned row carries x/y None, which replay_drive refuses ("not fully positioned").

Play detection, in order of preference:
  hand  both hands visible (expected in a spectated replay; live_play.py: "both hands visible = the results / replay
        screen"): a hand slot whose deck index changes = that card was played, at that frame's tick -- the same receipt
        live_play.py uses to confirm OUR plays. Card and tick are exact up to the 100 ms sample. Position = the first
        public object of that card / side born within LOCATE_TICKS: troop / building bodies (cohort centroid), spell
        projectile TARGET (L70 reader: Rocket target == logged cast point), rolling spells (Log, Barbarian Barrel)
        and area effects at their first-seen position.
  body  no visible hands: pipeline.public_observation.PublicObserver (the training / live public play detector) run
        once per seat, so each side's plays come from the PUBLIC board only.
Labels: a row's card / x / y / tick are the ACTOR's own play. Whatever the builder later shows a row from player A's
perspective must still be A's own hand + the opponent's PUBLIC plays (dataset_gen.opponent_past); the opponent's
hand / next / elixir in the recording are never written here.
Not detected: hero / champion ability presses (crawl rows attr_ability 1) -- no reader field for a press yet.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline.dataset_gen import card_key  # noqa: E402
from pipeline.obs_contract import catalog_card_form  # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402

TICK_S = 0.05
LOCATE_TICKS = 60            # a play's first body / spell object is born within this many ticks of the rotation frame
EARLY_TICKS = 10             # ... or this many ticks BEFORE it (the body can be sampled one frame ahead of the hand)
ROLLING = {"the-log", "barbarian-barrel"}       # projectile born AT the cast point, then rolls away (target = end)
DIGGERS = {"goblin-drill", "miner"}             # body born at the king tower, tunnels to the deploy point
DIG_TICKS = 200
FORM_SUFFIX = {0: "", 1: "-ev1", 2: "-hero"}
SIDE_NAME = {0: "red", 1: "blue"}
BATTLE_COLS = ["replay_tag", "deck", "player_tag", "player_name", "clan_tag", "rating", "rank", "wins_7d",
               "battle_time", "battle_timestamp", "battle_type", "result", "team_tags", "opponent_tags",
               "team_crowns", "opponent_crowns", "team_deck", "opponent_deck", "team_elixir_total",
               "team_elixir_troop", "team_elixir_building", "team_elixir_spell", "team_elixir_leaked",
               "oppo_elixir_total", "oppo_elixir_troop", "oppo_elixir_building", "oppo_elixir_spell",
               "oppo_elixir_leaked", "plays"]
PLAY_COLS = ["replay_tag", "play_index", "tick", "seconds", "x_units", "y_units", "tile_x", "tile_y", "attr_ability",
             "attr_card", "attr_s", "attr_t", "attr_i", "form", "detect", "located"]


def visible_sides(frame) -> list[int]:
    return [int(p["side"]) for p in frame.get("players") or () if any(i >= 0 for i in p["hand_deck_indices"])]


def seat(frame) -> str:
    """player = exactly one hand visible (a live battle we play in); spectator = both; blind = none."""
    return {1: "player", 2: "spectator"}.get(len(visible_sides(frame)), "blind")


def slug_form(card_id: int) -> tuple[str | None, int]:
    name, form = catalog_card_form(int(card_id))
    return (card_key(name) if name else None), form


def battle_frames(path: Path) -> tuple[dict, list[dict]]:
    """(rec_start meta, active+coherent frames of the FIRST battle in the file, one per tick, tick order)."""
    meta, out, last = {}, [], -1
    with open(path, encoding="utf-8") as h:
        for line in h:
            r = json.loads(line)
            if r.get("event") == "rec_start":
                meta = r
            if r.get("event") != "frame":
                continue
            f = r["f"]
            if not (f.get("battle_active") and f.get("coherent")):
                continue
            t = int(f["game_tick"])
            if out and t < last - 20:            # the clock went back: a second battle -- convert the first only
                break
            if t <= last:
                continue
            out.append(dedupe_hero_bodies(f))
            last = t
    return meta, out


def decks(frames) -> dict[int, list[str]]:
    """side -> 8 slugs with -ev1 / -hero, from the first frame that shows that side's deck."""
    out = {}
    for f in frames:
        for p in f.get("players") or ():
            s = int(p["side"])
            if s not in out and len(p.get("deck_card_ids") or ()) == 8:
                flags = list(p.get("deck_form_flags") or [0] * 8)
                out[s] = [slug_form(c)[0] + FORM_SUFFIX[int(fl)] for c, fl in zip(p["deck_card_ids"], flags)]
    return out


def _key(kind: str, o: dict):
    # card_id too: the reader reuses a dead body's address (live 10-08 194541 t1584: a Hero Valkyrie on a dead
    # body's address), and frames without `category` would otherwise never see the new body
    return kind, o.get("address"), o.get("category", o.get("generation_key")), int(o.get("card_id", -1))


def births(frames) -> list[list[dict]]:
    """Per frame: the public objects first seen in it -- side, slug, form, kind (body / projectile / effect), xy."""
    seen, out = set(), []
    for f in frames:
        new = []
        for kind, rows in (("body", f.get("entities")), ("projectile", f.get("projectiles")),
                           ("effect", f.get("effects"))):
            for o in rows or ():
                cid = int(o.get("card_id", -1))
                k = _key(kind, o)
                if cid < 0 or int(o.get("side", -1)) not in (0, 1) or k in seen:
                    continue
                seen.add(k)
                slug, form = slug_form(cid)
                if slug is None:
                    continue
                xy = (float(o["x"]), float(o["y"]))
                if kind == "projectile" and o.get("target_x") is not None and slug not in ROLLING:
                    xy = (float(o["target_x"]), float(o["target_y"]))
                new.append(dict(side=int(o["side"]), slug=slug, form=form, kind=kind, x=xy[0], y=xy[1], key=k))
        out.append(new)
    return out


def locate(frames, born, i0: int, side: int, slug: str, spell: bool, claimed: set):
    """-> (x, y, form) of the first unclaimed cohort of this card / side near frame i0, or None."""
    t0 = int(frames[i0]["game_tick"])
    lo = i0
    while lo > 0 and int(frames[lo - 1]["game_tick"]) >= t0 - EARLY_TICKS:
        lo -= 1
    kinds = ("projectile", "effect", "body") if spell else ("body",)
    for kind in kinds:                           # spells: the projectile / effect is the cast; bodies come later
        for i in range(lo, len(frames)):
            if int(frames[i]["game_tick"]) > t0 + LOCATE_TICKS:
                break
            hit = [b for b in born[i] if b["side"] == side and b["slug"] == slug and b["kind"] == kind
                   and b["key"] not in claimed]
            if hit:
                claimed.update(b["key"] for b in hit)
                if slug in DIGGERS:
                    return (*follow(frames, i, hit[0]["key"]), hit[0]["form"])
                return (sum(b["x"] for b in hit) / len(hit), sum(b["y"] for b in hit) / len(hit),
                        max(b["form"] for b in hit))
    return None


def follow(frames, i: int, key) -> tuple[float, float]:
    """A digger is first seen at its king tower and tunnels to the deploy point (live 10-08 184937 t1174: a Goblin
    Drill moved ~0.3 tile/tick for > 70 ticks): its position once it stops moving (or at DIG_TICKS)."""
    t0, last = int(frames[i]["game_tick"]), None
    for f in frames[i:]:
        if int(f["game_tick"]) > t0 + DIG_TICKS:
            break
        o = next((o for o in f.get("entities") or () if _key("body", o) == key), None)
        if o is None:
            break
        xy = (float(o["x"]), float(o["y"]))
        if last is not None and abs(xy[0] - last[0]) + abs(xy[1] - last[1]) < 30:
            return xy
        last = xy
    return last


def hand_plays(frames) -> list[dict]:
    """Hand-slot rotations of every side with a visible hand; position located from the public board."""
    born, claimed, prev, plays = births(frames), set(), {}, []
    for i, f in enumerate(frames):
        for p in f.get("players") or ():
            s, h = int(p["side"]), list(p["hand_deck_indices"])
            if not all(d >= 0 for d in h):
                continue
            old = prev.get(s)
            prev[s] = h
            if old is None or len(p.get("deck_card_ids") or ()) != 8:
                continue
            flags = list(p.get("deck_form_flags") or [0] * 8)
            for a, b in zip(old, h):
                if a == b:
                    continue
                cid = int(p["deck_card_ids"][a])
                slug = slug_form(cid)[0]
                loc = locate(frames, born, i, s, slug, cid // 1_000_000 == 28, claimed)
                decked = int(flags[a])
                plays.append(dict(side=s, tick=int(f["game_tick"]), card=slug, detect="hand",
                                  x=None if loc is None else loc[0], y=None if loc is None else loc[1],
                                  # observed form when located; else hero (always its form) / base; an unlocated
                                  # decked evo stays 0 (its evo cycle is not counted here)
                                  form=loc[2] if loc else (2 if decked == 2 else 0)))
    return plays


def body_plays(frames, sides=(0, 1)) -> list[dict]:
    """PublicObserver per seat: observer seat s reports side 1-s's plays from public objects only."""
    from pipeline.public_observation import PublicObserver
    out = []
    for actor in sides:
        obs = PublicObserver(1 - actor)
        for f in frames:
            obs.update(f, source="reader")
        out += [dict(side=int(e["side"]), tick=int(e["tick"]), card=card_key(e["card"]), form=int(e["form"]),
                     x=float(e["x"]), y=float(e["y"]), detect="body") for e in obs.plays]
    born, ticks = None, [int(f["game_tick"]) for f in frames]
    for e in out:                                # a digger's first sighting is its king tower: follow it instead
        if e["card"] in DIGGERS:
            born = born or births(frames)
            loc = locate(frames, born, ticks.index(e["tick"]), e["side"], e["card"], False, set())
            if loc:
                e["x"], e["y"] = loc[0], loc[1]
    return sorted(out, key=lambda e: (e["tick"], e["side"]))


def crowns(frame) -> dict[int, int]:
    """Crowns EARNED by each side = the other side's towers missing from the final active frame."""
    alive = {0: {"king": 0, "princess": 0}, 1: {"king": 0, "princess": 0}}
    for e in frame.get("entities") or ():
        if int(e.get("card_id", 0)) != -1 or int(e.get("hp", 0)) <= 0 or int(e["side"]) not in (0, 1):
            continue
        x, y = float(e["x"]), float(e["y"])
        if abs(x - 9000) < 1500 and min(abs(y - 3000), abs(y - 29000)) < 1500:
            alive[int(e["side"])]["king"] += 1
        elif min(abs(x - 3500), abs(x - 14500)) < 1500 and min(abs(y - 6500), abs(y - 25500)) < 1500:
            alive[int(e["side"])]["princess"] += 1
    return {s: 3 if not alive[1 - s]["king"] else 2 - min(2, alive[1 - s]["princess"]) for s in (0, 1)}


def convert(path: Path, tag: str | None = None) -> dict:
    meta, frames = battle_frames(path)
    if not frames:
        raise SystemExit(f"{path}: no active+coherent battle frames")
    seats = [seat(f) for f in frames]
    if seats.count("player") > len(seats) // 2:
        raise SystemExit(f"{path}: most frames show exactly one hand -- a battle we PLAYED, not a spectated replay")
    spectator = seats.count("spectator") > len(seats) // 2
    plays = hand_plays(frames) if spectator else body_plays(frames)
    tag = tag or "REC" + Path(path).stem.split("_", 1)[-1].replace("_", "")
    plays.sort(key=lambda e: (e["tick"], e["side"]))
    cr, dk = crowns(frames[-1]), decks(frames)
    result = "win" if cr[1] > cr[0] else "loss" if cr[1] < cr[0] else "draw"
    ts = int(meta.get("t_host", time.time()))
    battle = dict.fromkeys(BATTLE_COLS, "")
    battle.update(replay_tag=tag, deck=",".join(dk.get(1, [])), battle_type="inGameReplay", result=result,
                  battle_time=time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts)), battle_timestamp=ts,
                  team_crowns=cr[1], opponent_crowns=cr[0], team_deck=",".join(dk.get(1, [])),
                  opponent_deck=",".join(dk.get(0, [])), plays=len(plays))
    rows = []
    for i, e in enumerate(plays):
        ok = e["x"] is not None
        rows.append(dict(replay_tag=tag, play_index=i, tick=e["tick"], seconds=round(e["tick"] * TICK_S, 2),
                         x_units=round(e["x"]) if ok else "None", y_units=round(e["y"]) if ok else "None",
                         tile_x=round(e["x"] / 500) / 2 if ok else "", tile_y=round(e["y"] / 500) / 2 if ok else "",
                         attr_ability=0, attr_card=e["card"], attr_s=SIDE_NAME[e["side"]], attr_t=e["tick"],
                         attr_i=0, form=e["form"], detect=e["detect"], located=int(ok)))
    return dict(battle=battle, plays=rows, frames=len(frames), mode="hand" if spectator else "body",
                seats={s: seats.count(s) for s in set(seats)}, first_tick=int(frames[0]["game_tick"]),
                last_tick=int(frames[-1]["game_tick"]))


def write(res: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for name, cols, rows in (("battles.csv", BATTLE_COLS, [res["battle"]]), ("plays_ext_i1.csv", PLAY_COLS, res["plays"])):
        with open(out / name, "w", encoding="utf-8", newline="") as h:
            w = csv.DictWriter(h, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recording")
    ap.add_argument("--out", help="output dir (default: next to the recording, <stem>_crawl/)")
    ap.add_argument("--tag")
    a = ap.parse_args()
    rec = Path(a.recording)
    res = convert(rec, a.tag)
    out = Path(a.out) if a.out else rec.with_name(rec.stem + "_crawl")
    write(res, out)
    by = {}
    for r in res["plays"]:
        by.setdefault(r["attr_s"], [0, 0])[0] += 1
        by[r["attr_s"]][1] += r["located"]
    print(json.dumps(dict(out=str(out), mode=res["mode"], frames=res["frames"], seats=res["seats"],
                          ticks=[res["first_tick"], res["last_tick"]], result=res["battle"]["result"],
                          crowns=[res["battle"]["team_crowns"], res["battle"]["opponent_crowns"]],
                          plays_located={k: f"{v[1]}/{v[0]}" for k, v in by.items()},
                          team_deck=res["battle"]["team_deck"], opponent_deck=res["battle"]["opponent_deck"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
