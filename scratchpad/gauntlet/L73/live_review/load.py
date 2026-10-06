"""Load in-scope live_play logs (decision-level public state) into a compact pickle.
Only the 'decision' events carry state in all logs (frame events exist in only ~20% of logs)."""
import json, glob, os, pickle
D = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L68/live_reader/"
OUT = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review/cache.pkl"
FIRST = "20261004_205129"  # first R1e31 live log (2026-10-04 evening)

def load(f):
    r = {"file": os.path.basename(f), "states": [], "plays": [], "conf": [], "unconf": [], "abil": [], "abil_conf": [], "start": None, "end": None, "stop": None, "nframes": 0}
    with open(f) as fh:
        for l in fh:
            if not l.startswith('{"event": "'):
                continue
            ev = l[11:l.index('"', 11)]
            if ev == "decision":
                d = json.loads(l); p = d["public"]
                dec = d["decision"]
                r["states"].append({
                    "tick": d["tick"], "side": p["observer_side"], "el": p["own_elixir_raw"], "opp_el": p.get("opponent_elixir_estimate"),
                    "hand": [h["name"] for h in p["own_hand"]],
                    "bodies": [(b["side"], b["x"], b["y"], b["card_id"], b["hp"], b["max_hp"], b["kind"], b["address"]) for b in p["raw_bodies"]],
                    "proj": [(q["side"], q["x"], q["y"], q["card_id"], q.get("target_x"), q.get("target_y")) for q in p["raw_projectiles"]],
                    "dec": (dec.get("play"), dec.get("name"), round(dec.get("p_play", 0), 3))})
            elif ev == "frame":
                r["nframes"] += 1
                e = json.loads(l)
                r.setdefault("fstates", []).append({"tick": e["tick"], "side": e.get("my_side"), "el": e["elixir"], "opp_el": e.get("opp_elixir_est"), "hand": None,
                    "bodies": [tuple(b) for b in e["ents"]], "proj": [], "dec": None})
            elif ev == "play": r["plays"].append(json.loads(l))
            elif ev == "confirmed": r["conf"].append(json.loads(l))
            elif ev == "unconfirmed": r["unconf"].append(json.loads(l))
            elif ev == "ability": r["abil"].append(json.loads(l))
            elif ev == "ability_confirmed": r["abil_conf"].append(json.loads(l))
            elif ev == "start": r["start"] = json.loads(l)
            elif ev == "end": r["end"] = json.loads(l)
            elif ev == "stop": r["stop"] = json.loads(l)
    if not r["states"] and r.get("fstates"):
        r["states"] = r["fstates"]; r["state_src"] = "frame"
    elif r["states"]: r["state_src"] = "decision"
    else: r["state_src"] = "none"
    r.pop("fstates", None)
    return r

if __name__ == "__main__":
    fs = [f for f in sorted(glob.glob(D + "live_play_2026*.jsonl")) if os.path.basename(f)[10:25] >= FIRST]
    data = [load(f) for f in fs]
    pickle.dump(data, open(OUT, "wb"))
    print(len(data), "logs", sum(len(d["states"]) for d in data), "states")
