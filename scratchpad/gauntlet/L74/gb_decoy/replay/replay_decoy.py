"""GB-DECOY model replay: recorded live matches (merged reader frames) through the REAL live decision code
(pipeline.live_gen_v2.GenPilot set up from the log's own start event, as speed/live_profile.make_pilot = live_play
load_pilot), twice: --barrel-decoy off and on. Every logged 'decision' tick is decided on the latest frame; the logged
own plays ('confirmed' / 'late_landing') and IW presses are recorded into the pilot as live_play does, so both variants
share the live history and differ only in the observation. Pod only (not the live laptop).

    python replay_decoy.py --ckpt CLXIII.pt --windows windows.json --out out.jsonl LOG.jsonl [LOG ...]
Out: one row per logged decision tick: logged decision, off, on (play, name, xy, hand_pos, card, form, why)."""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(REPO), str(REPO / "scratchpad/gauntlet/L74/cues/live"), str(REPO / "scratchpad/gauntlet/L74/speed")]
TICK = re.compile(r'"tick": (\d+)')
KEYS = ("play", "name", "xy", "hand_pos", "card", "form", "why", "p_play")


def slim(d):
    out = {k: d.get(k) for k in KEYS}
    if out["xy"] is not None:
        out["xy"] = [round(float(v), 6) for v in out["xy"]]
    if out["p_play"] is not None:
        out["p_play"] = round(float(out["p_play"]), 6)
    for k in ("card", "form", "hand_pos"):
        if out[k] is not None:
            out[k] = int(out[k])
    return out


def run(log, ckpt, decoy):
    from live_profile import make_pilot
    from logframes import full_frames
    from pipeline.dataset_gen import card_key
    start = json.loads(open(log, encoding="utf-8").readline())
    pilot = make_pilot(ckpt, start, "cpu")
    pilot.barrel_decoy = bool(decoy)
    pilot.reset_match()
    frames = {f["game_tick"]: f for f in full_frames(log)}
    cur, forms, unconf, taps, got = None, {}, {}, [], {}
    for raw in open(log, encoding="utf-8"):
        head = raw[:40]
        if '"event": "frame"' in head:
            t = int(TICK.search(raw[:80]).group(1))
            f = frames.get(t)
            if f is not None:
                cur = f
                pilot.observe(copy.deepcopy(f))
        elif '"event": "decision"' in head:
            j = json.loads(raw)
            d = j.get("decision") or {}
            if d.get("play"):
                forms[d.get("name")] = int(d.get("form", 3))
            if cur is not None and j["tick"] not in got:
                got[j["tick"]] = slim(pilot.decide(copy.deepcopy(cur)))
        elif '"event": "unconfirmed"' in head:
            j = json.loads(raw)
            unconf[j["name"]] = j.get("intended")
        elif '"event": "confirmed"' in head or '"event": "late_landing"' in head:
            j = json.loads(raw)
            xy = j.get("intended") if j["event"] == "confirmed" else unconf.get(j["name"])
            if xy is not None and getattr(pilot, "public", None) is not None:
                pilot.record_play(pilot.gid[card_key(j["name"])], forms.get(j["name"], 3), tuple(xy), j["tick"] * 0.05)
        elif head.startswith('{"event": "ability"'):
            taps.append(json.loads(raw)["tick"])
        elif '"event": "ability_confirmed"' in head and taps:
            pilot.record_ability("IceWizard", taps[-1])
    return got


def logged(log):
    out = {}
    for raw in open(log, encoding="utf-8"):
        if '"event": "decision"' in raw[:40]:
            j = json.loads(raw)
            out.setdefault(j["tick"], slim(j.get("decision") or {}))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.out, "a") as out:
        for log in a.logs:
            off, on, lg = run(log, a.ckpt, False), run(log, a.ckpt, True), logged(log)
            for t in sorted(lg):
                out.write(json.dumps(dict(file=Path(log).name, tick=t, logged=lg[t], off=off.get(t), on=on.get(t))) + "\n")
            out.flush()
            print(Path(log).name, "decisions", len(lg), "off==on", sum(off.get(t) == on.get(t) for t in lg), flush=True)


if __name__ == "__main__":
    main()
