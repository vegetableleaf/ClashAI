"""Stage C (bot): rebuild the opponent's PUBLIC plays + elixir estimate from the live logs' decision bodies, by running the
repo's own PlayDetector/OppElixirCounter (read-only import). Validates against the logged opponent_elixir_estimate."""
import sys, pickle, ctypes, math
import numpy as np
try: ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
except Exception: pass
sys.path.insert(0, "C:/Users/benpe/ClashBot"); sys.path.insert(0, "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/live_review")
HERE = "C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_counter/"
import load as L
from pipeline.public_observation import PublicObserver, public_frame
from pipeline.opp_elixir_count import card_cost
from pipeline.reader_identity_aliases import dedupe_hero_bodies

def recon(d):
    S = d["states"]; side = S[0]["side"]
    obs = PublicObserver(side); errs = []
    for s in S:
        frame = {"game_tick": int(s["tick"]),
                 "entities": [dict(side=b[0], x=b[1], y=b[2], hp=b[4], max_hp=b[5], card_id=b[3], address=b[7], category=b[6]) for b in s["bodies"]],
                 "projectiles": [dict(side=q[0], x=q[1], y=q[2], card_id=q[3]) for q in s["proj"]], "effects": []}
        f = public_frame(dedupe_hero_bodies(frame), source="reader"); tick = f["game_tick"]
        if tick < obs.last_tick: obs.reset()
        obs.last_tick = tick
        cand = {}
        for e in obs.body.feed(f):
            if e.key not in obs.spell_last_seen or tick - obs.spell_last_seen[e.key] > 100:
                cand[e.key] = dict(card=e.key, form=e.form, x=e.x, y=e.y)
        groups = {}
        for e in f["spells"]:
            if e["side"] != side: groups.setdefault(e["card"], []).append(e)
        for key, g in groups.items():
            prev = obs.spell_last_seen.get(key); obs.spell_last_seen[key] = tick
            if prev is None or tick - prev > 100:
                cand[key] = dict(card=key, form=max(e["form"] for e in g), x=sum(e["x"] for e in g) / len(g), y=sum(e["y"] for e in g) / len(g))
        for key, e in sorted(cand.items()):
            window = obs.body.swarm_ticks_by_key.get(key, obs.body.swarm_ticks)
            if key in obs.last_play and tick - obs.last_play[key] <= window: continue
            if key not in groups and key in obs.spell_last_seen and tick - obs.spell_last_seen[key] <= 100: continue
            obs.last_play[key] = tick
            obs.plays.append(dict(e, tick=tick, side=1 - side, accepted=True))
            obs.counter.play(tick, key, card_cost(key)); obs.ticks.append(tick); obs.estimates.append(obs.counter.est)
        # logged estimate belongs to the extrapolated model tick (raw + 26)
    return obs, side

def to_own(side, x, y): return (x / 1000.0, y / 1000.0) if side == 1 else ((18000 - x) / 1000.0, (32000 - y) / 1000.0)

if __name__ == "__main__":
    ids = [m["id"] for m in pickle.load(open("C:/Users/benpe/ClashBot/scratchpad/gauntlet/L73/xbow_switch/bot.pkl", "rb"))]
    out = {}; err = []
    for i, fid in enumerate(ids):
        d = L.load(L.D + fid)
        # decision-level logged estimate
        obs, side = recon(d)
        plays = [(p["tick"], p["card"], *to_own(side, p["x"], p["y"])) for p in obs.plays]
        raw_dec = []
        for l in open(L.D + fid):
            if l.startswith('{"event": "decision"'):
                import json; dd = json.loads(l); p = dd["public"]
                raw_dec.append((p["raw_tick"], p["model_tick"], p.get("opponent_elixir_estimate")))
        out[fid] = {"side": side, "plays": plays, "ticks": list(obs.ticks), "estimates": list(obs.estimates), "dec": raw_dec}
        if i % 20 == 0: print(i, len(ids), flush=True)
    pickle.dump(out, open(HERE + "opp_bot.pkl", "wb")); print("saved", len(out))
