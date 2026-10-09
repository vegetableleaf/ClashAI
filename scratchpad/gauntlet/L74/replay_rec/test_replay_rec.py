"""Synthetic-frame tests for recorder.py / convert.py (L74 replay_rec). No device, no network.

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/replay_rec/test_replay_rec.py
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "research" / "sandbox_tools"))
import convert as cv  # noqa: E402
import recorder as rc  # noqa: E402

ID = dict(Knight=26000000, KnightEvo=13000000, Archer=26000001, Skeletons=26000010, IceSpirits=26000030,
          Tesla=27000006, Xbow=27000008, GoblinDrill=27000013, Fireball=28000000, Rocket=28000003, Log=28000011,
          Tornado=28000012)
DECK = {1: [ID[n] for n in ("Knight", "Xbow", "Rocket", "Log", "Tornado", "Skeletons", "Tesla", "IceSpirits")],
        0: [ID[n] for n in ("Archer", "Fireball", "GoblinDrill", "Knight", "Skeletons", "Tesla", "IceSpirits", "Xbow")]}
FLAGS = {1: [1, 0, 0, 0, 0, 0, 0, 0], 0: [0, 0, 0, 2, 0, 0, 0, 0]}
TOWERS = [(0, 9000, 3000, 12), (0, 3500, 6500, 13), (0, 14500, 6500, 13),
          (1, 9000, 29000, 12), (1, 3500, 25500, 13), (1, 14500, 25500, 13)]
DRILL_TARGET = (14500, 22500)
# (tick, side, hand slot, what appears): body / projectile / effect, xy, target
SCRIPT = [
    (200, 1, 0, [("body", ID["KnightEvo"], (3500, 20500), None)]),
    (260, 1, 2, [("projectile", ID["Rocket"], (9000, 29000), (14500, 6500))]),
    (300, 1, 3, [("projectile", ID["Log"], (4500, 17500), (4500, 7500))]),
    (340, 0, 0, [("body", ID["Archer"], (2900, 9000), None), ("body", ID["Archer"], (4100, 9000), None)]),
    (400, 0, 1, [("projectile", ID["Fireball"], (9000, 3000), (9000, 25000))]),
    (450, 0, 2, [("body", ID["GoblinDrill"], (9000, 3000), None)]),
    (500, 1, 0, [("effect", ID["Tornado"], (9000, 16000), None)]),   # slot 0 holds Tornado (cycled in at 200)
]
EXPECT = [(200, 1, "knight", 1, (3500, 20500)), (260, 1, "rocket", 0, (14500, 6500)),
          (300, 1, "the-log", 0, (4500, 17500)), (340, 0, "archers", 0, (3500, 9000)),
          (400, 0, "fireball", 0, (9000, 25000)), (450, 0, "goblin-drill", 0, DRILL_TARGET),
          (500, 1, "tornado", 0, (9000, 16000))]


def battle(visible=(0, 1), end_tick=600):
    """Reader-shaped frames every 2 ticks; hands cycle like the game (played card -> back of the queue)."""
    hand = {s: [0, 1, 2, 3] for s in (0, 1)}
    queue = {s: [4, 5, 6, 7] for s in (0, 1)}
    board, objs, frames, n = {}, {}, [], 0
    for tick in range(100, end_tick + 1, 2):
        for t, s, slot, born in SCRIPT:
            if t == tick:
                d = hand[s][slot]
                hand[s][slot] = queue[s].pop(0)
                queue[s].append(d)
                for kind, cid, xy, tgt in born:
                    n += 1
                    o = dict(address=hex(0x1000 + n), category=n, side=s, x=xy[0], y=xy[1], card_id=cid,
                             hp=500, max_hp=500, kind=14)
                    if tgt:
                        o.update(target_x=tgt[0], target_y=tgt[1], generation_key=n)
                    (board if kind == "body" else objs)[o["address"]] = (kind, o)
        for _, (kind, o) in board.items():          # the drill tunnels to its target, 300 units / tick
            if o["card_id"] == ID["GoblinDrill"]:
                for k, tgt in (("x", DRILL_TARGET[0]), ("y", DRILL_TARGET[1])):
                    o[k] += max(-600, min(600, tgt - o[k]))
        towers = [dict(address=hex(0x10 + i), category=5000000 + i, side=s, x=x, y=y, card_id=-1, hp=1000,
                       max_hp=1000, kind=k) for i, (s, x, y, k) in enumerate(TOWERS)
                  if not (tick >= 590 and (s, x) == (0, 3500))]            # blue takes red's left princess
        players = [dict(side=s, elixir_raw=50000, next_deck_index=queue[s][0] if s in visible else -1,
                        hand_deck_indices=list(hand[s]) if s in visible else [-1] * 4,
                        deck_card_ids=DECK[s] if s in visible else [], deck_form_flags=FLAGS[s] if s in visible else [])
                   for s in (0, 1)]
        frames.append(dict(battle_active=True, coherent=True, game_tick=tick, players=players,
                           entities=towers + [dict(o) for _, o in board.values()],
                           projectiles=[dict(o) for k, o in objs.values() if k == "projectile"],
                           effects=[dict(o) for k, o in objs.values() if k == "effect"]))
    return frames


def record(frames, tail_inactive=40) -> tuple[Path, str]:
    lines = [json.dumps(f) for f in frames] + [json.dumps(dict(battle_active=False, coherent=True, game_tick=0,
                                                                players=[], entities=[]))] * tail_inactive
    clock = iter(i * 0.1 for i in range(10 ** 6))
    out = Path(tempfile.mkdtemp()) / "rec_20261008_120000.jsonl"
    why = rc.run(lines, out, max_seconds=1e9, clock=lambda: next(clock))
    return out, why


def near(a, b, tol=1.0):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def test_recorder_spectator_records_and_ends():
    out, why = record(battle())
    assert why == "battle_inactive", why
    ev = [json.loads(line) for line in open(out, encoding="utf-8")]
    assert ev[0]["event"] == "rec_start" and ev[0]["observe_only"] is True
    assert sum(e["event"] == "frame" for e in ev) >= 251       # every reader line is saved, inactive ones too
    assert [e for e in ev if e["event"] == "battle_start"][0]["tick"] == 100
    assert ev[-1]["event"] == "battle_end" and ev[-1]["seats"].count("spectator") == rc.SEAT_FRAMES


def test_recorder_refuses_player_seat():
    out, why = record(battle(visible=(1,)))
    assert why == "refused_player_seat", why
    ev = [json.loads(line) for line in open(out, encoding="utf-8")]
    assert ev[-1]["event"] == "refused"
    try:                                                     # and the converter refuses such a recording too
        cv.convert(out)
        raise AssertionError("convert accepted a battle we played")
    except SystemExit as e:
        assert "PLAYED" in str(e)


def test_hand_path_both_sides():
    out, _ = record(battle())
    res = cv.convert(out)
    assert res["mode"] == "hand"
    got = [(int(r["tick"]), {"red": 0, "blue": 1}[r["attr_s"]], r["attr_card"], int(r["form"]),
            (float(r["x_units"]), float(r["y_units"]))) for r in res["plays"]]
    assert len(got) == len(EXPECT), got
    for g, e in zip(got, EXPECT):
        assert g[:4] == e[:4], (g, e)
        assert near(g[4], e[4], 1.0), (g, e)
    b = res["battle"]
    assert b["team_deck"].split(",")[0] == "knight-ev1" and "knight-hero" in b["opponent_deck"].split(",")
    assert (b["team_crowns"], b["opponent_crowns"], b["result"]) == (1, 0, "win")
    # public-only output: no elixir / next / hand field reaches the rows
    assert set(res["plays"][0]) == set(cv.PLAY_COLS)


def test_body_path_when_hands_hidden():
    out, _ = record(battle(visible=()))
    res = cv.convert(out)
    assert res["mode"] == "body"
    got = {(r["attr_card"], {"red": 0, "blue": 1}[r["attr_s"]]): r for r in res["plays"]}
    for card, side in (("knight", 1), ("archers", 0), ("goblin-drill", 0), ("rocket", 1), ("fireball", 0),
                       ("tornado", 1), ("the-log", 1)):
        assert (card, side) in got, (card, side, sorted(got))
    d = got[("goblin-drill", 0)]
    assert near((float(d["x_units"]), float(d["y_units"])), DRILL_TARGET, 1.0), d   # followed, not its king tower


def test_output_loads_in_replay_drive():
    import replay_drive as rd
    out, _ = record(battle())
    res = cv.convert(out, tag="SYNTH1")
    d = Path(tempfile.mkdtemp())
    cv.write(res, d)
    rd.set_crawl(str(d))
    rd.set_plays_file("plays_ext_i1.csv")
    row, plays = rd.load_battle("SYNTH1")
    assert len(plays) == len(EXPECT) and {p["side"] for p in plays} == {0, 1}
    for side in (0, 1):
        deck = rd.deck_for_side(row, side)
        seq = [rd.card_for_slug(p["attr_card"]) for p in plays if p["side"] == side]
        assert rd.infer_deals(seq, [c["card_id"] for c in deck]), side       # a legal 4-hand / 4-queue cycle
    with open(d / "plays_ext_i1.csv", encoding="utf-8", newline="") as h:
        assert list(csv.DictReader(h))[0]["attr_i"] == "0"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
