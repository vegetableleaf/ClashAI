"""Offline replay of a live_play_*.jsonl through a PublicObserver, the way live_gen.GenPilot.observe/record_play do.

The log's compact 'frame' events carry entities only ([side,x,y,card_id,hp,max_hp,kind,address]); no players block, no
projectiles/effects. So body plays are detected exactly as live, spells that need projectile evidence are not (declared).
"""
import json, sys
from types import SimpleNamespace
ROOT = "C:/Users/benpe/ClashBot"
sys.path.insert(0, ROOT)
from pipeline.public_observation import PublicObserver      # noqa: E402
from pipeline.reader_identity_aliases import dedupe_hero_bodies  # noqa: E402
from pipeline.dataset_gen import card_key                   # noqa: E402


def frame_from_event(r):
    return {"game_tick": int(r["tick"]),
            "entities": [dict(side=e[0], x=e[1], y=e[2], card_id=e[3], hp=e[4], max_hp=e[5], kind=e[6], address=e[7],
                              category=None) for e in r["ents"]],
            "players": [], "projectiles": [], "effects": []}


def replay(path, upto=None):
    """Yield (event, pilot) for every event; pilot.public is the PublicObserver fed so far. frame events also carry
    r['_frame'] (the reader-like frame with own elixir under r['_frame']['own_elixir'])."""
    pilot = SimpleNamespace(public=None, my_side=None)
    for line in open(path, encoding="utf-8"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        ev = r.get("event")
        if ev == "frame":
            side = int(r["my_side"])
            if pilot.public is None or pilot.public.side != side:
                pilot.public = PublicObserver(side)
            f = dedupe_hero_bodies(frame_from_event(r))
            f["own_elixir"] = float(r["elixir"])
            pilot.public.update(f, source="reader")
            r["_frame"] = f
        elif ev == "confirmed" and pilot.public is not None:
            pilot.public.own_events.append(dict(card=card_key(r["name"]), tick=int(r["tick"]), side=pilot.public.side,
                                                accepted=True, ability=False))
        elif ev == "ability_confirmed" and pilot.public is not None:
            pilot.public.own_events.append(dict(card="ice-wizard", tick=int(r["tick"]), side=pilot.public.side,
                                                accepted=True, ability=True))
        yield r, pilot


if __name__ == "__main__":
    import collections
    kinds = collections.Counter()
    from pipeline.opp_elixir_count import card_db
    for r, p in replay(sys.argv[1]):
        pass
    for pl in p.public.plays:
        kinds[(pl["card"], card_db().kind(pl["card"]))] += 1
    print(kinds)
