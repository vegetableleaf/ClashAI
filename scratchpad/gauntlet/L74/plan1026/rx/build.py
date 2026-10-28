"""P3-RX build: stripped live logs -> per-match R_exchange running losses (public information only).

    python build.py LOGDIR OUT.npz [--workers N] [--limit N]
LOGDIR holds live_play_*.jsonl.gz (strip.sh: frame/start/end/stop lines, frame cut after ents) and, for logs without
frames, live_play_*.dec.gz (strip2.sh: decision lines cut after public.raw_bodies).
Only these fields are read: frame tick, my_side, elixir (own), opp_elixir_est (public counter), ents; decision
public.raw_tick, observer_side, own_elixir_raw, opponent_elixir_estimate (public counter), raw_bodies. The hidden
opp_elixir_true_EVAL_ONLY field (pre 10-16 logs) is never read. Result label: end event (towers.won / crowns), else the
final frame's towers (crowns, then the lowest-tower-HP tiebreak).
Card values: research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json (elixir, ids incl. evo/hero forms),
icebow/config/cards_stats.json (bodies per card), research/ext/Royale/RoyaleSim/data/derived/cards.json (building
lifetime -> decay). Paths overridable with RX_CATALOG / RX_STATS / RX_SIMCARDS (pod copies).
"""
import gzip
import json
import multiprocessing as mp
import os
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))
from pipeline import r_exchange as RX  # noqa: E402

CATALOG = os.environ.get("RX_CATALOG", ROOT / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json")
STATS = os.environ.get("RX_STATS", ROOT / "icebow/config/cards_stats.json")
SIMCARDS = os.environ.get("RX_SIMCARDS", ROOT / "research/ext/Royale/RoyaleSim/data/derived/cards.json")
# ponytail: kamikaze = bodies that always vanish when they connect; their vanish is not a kill. Battle Ram / Skeleton
# Barrel are left out (often shot down); a per-card "connected" flag from the engine would replace this list.
KAMIKAZE = {"FireSpirits", "IceSpirits", "ElectroSpirit", "Heal", "Wallbreakers", "SuspiciousBush"}
ALIASES = {"Archer": "archers", "Goblin": "goblins", "SpearGoblin": "speargoblins", "Minion": "minions",
           "Barbarian": "barbarians", "Bat": "bats", "FireSpirits": "firespirit", "BarbLog": "barbarianbarrel",
           "Log": "thelog",                                 # phase_stats.load_catalog's aliases, plus:
           "SkeletonWarriors": "guards", "AngryBarbarians": "elitebarbarians", "MiniSparkys": "zappies"}
HERO_IW = 203000023
SPAWN_SPELLS = {"GoblinBarrel": 3, "Graveyard": 13, "BarbLog": 1, "RoyalDelivery": 1}   # spells whose bodies are units
SAMPLE = 20                                                 # keep one row per second


def norm(s):
    return re.sub("[^a-z0-9]", "", s.lower())


def load_values():
    """{card_id: (elixir per body, decay fraction per tick, kamikaze)} from the live catalog."""
    stats = json.load(open(STATS, encoding="utf8"))["cards"]
    counts = {norm(k): v.get("count", 1) for k, v in stats.items()}
    counts.update({norm(v["display"]): v.get("count", 1) for v in stats.values()})
    life = {norm(c["name"]): c["lifetime_ms"] for c in json.load(open(SIMCARDS, encoding="utf8"))["cards"]
            if c.get("lifetime_ms")}
    out, iw = {}, None
    for c in json.load(open(CATALOG, encoding="utf8"))["cards"]:
        n = c["display_name"]
        if not c.get("elixir") or (c["type"] == "spell" and n not in SPAWN_SPELLS):
            continue
        per = c["elixir"] / (SPAWN_SPELLS.get(n) or max(1, counts.get(norm(ALIASES.get(n, n)), 1)))
        lt = life.get(norm(c["internal_name"])) or life.get(norm(n))
        v = (per, 50.0 / lt if lt else 0.0, n in KAMIKAZE)
        iw = v if n == "IceWizard" else iw
        for f in ("card_id", "evolution_form_id", "hero_form_id"):
            if c.get(f) is not None:
                out[c[f]] = v
    out[HERO_IW] = iw                                       # witnessed Hero IW alias (phase_stats.load_catalog)
    return out


def ents_of(fr):
    """frame ents [side, x, y, cid, hp, max_hp, kind, address] -> r_exchange ents (side, cid, hp, max_hp, key).
    The Hero IW shows as two bodies at one spot (the real one + a FloatingCube copy that stays at full HP and vanishes
    with it, 2026-10-21 logs): each such pair is merged into one body with the lower HP and the lower address as key."""
    E = fr["ents"]
    out, iw = [], []
    for e in E:
        side, x, y, cid, hp, mhp, kind, addr = e[:8]
        (iw if cid == HERO_IW else out).append((side, cid, hp, mhp, str(addr)) if cid != HERO_IW else e)
    used = set()
    for i, a in enumerate(iw):
        if i in used:
            continue
        grp = [a] + [b for j, b in enumerate(iw) if j > i and j not in used and b[0] == a[0]
                     and abs(b[1] - a[1]) <= 500 and abs(b[2] - a[2]) <= 500]
        used.update(j for j, b in enumerate(iw) if any(b is g for g in grp))
        out.append((a[0], HERO_IW, min(g[4] for g in grp), a[5], min(str(g[7]) for g in grp)))
    return out


def read(path):
    op = gzip.open if path.suffix == ".gz" else open
    head, end, frames = {}, None, []
    with op(path, "rt", encoding="utf8") as f:
        for line in f:
            if line.startswith('{"event": "frame"'):
                j = json.loads(line)
                frames.append({"tick": j["tick"], "side": j["my_side"], "elixir": j.get("elixir"),
                               "opp_elixir": j.get("opp_elixir_est"), "ents": ents_of(j)})
            elif line.startswith('{"event": "start"'):
                j = json.loads(line)
                head = {"dry_run": bool(j.get("dry_run")), "ckpt": str(j.get("ckpt"))}
            elif line.startswith('{"event": "end"'):
                end = json.loads(line)
    dec = path.with_name(path.name.replace(".jsonl.gz", ".dec.gz"))
    if len(frames) < 100 and dec.exists():
        frames = []
        with gzip.open(dec, "rt", encoding="utf8") as f:
            for line in f:
                try:
                    p = json.loads(line)["public"]
                except (ValueError, KeyError):
                    continue
                E = [[b["side"], b["x"], b["y"], b["card_id"], b["hp"], b["max_hp"], b.get("kind"), b.get("address")]
                     for b in p["raw_bodies"]]
                frames.append({"tick": p["raw_tick"], "side": p["observer_side"], "elixir": p.get("own_elixir_raw"),
                               "opp_elixir": p.get("opponent_elixir_estimate"), "ents": ents_of({"ents": E}),
                               "src": "decision"})
        frames.sort(key=lambda f: f["tick"])
    return head, end, frames


def label(end, frames):
    tw = (end or {}).get("towers") or {}
    if tw.get("won") is not None and tw.get("crowns_me") is not None and (tw["won"] or tw["crowns_me"] != tw["crowns_opp"]):
        return int(bool(tw["won"])), "end_event", tw["crowns_me"], tw["crowns_opp"]
    last = frames[-1]
    t = {0: [], 1: []}
    for side, cid, hp, mhp, _ in last["ents"]:
        if cid == -1:
            t[0 if side == last["side"] else 1].append(hp)
    cm, co = 3 - len([h for h in t[1] if h > 0]), 3 - len([h for h in t[0] if h > 0])
    if cm != co:
        return int(cm > co), "final_frame_crowns", cm, co
    if t[0] and t[1] and min(t[0]) != min(t[1]):
        return int(min(t[1]) < min(t[0])), "final_frame_tiebreak", cm, co
    return -1, "draw_or_unknown", cm, co


def one(path):
    path = Path(path)
    try:
        head, end, frames = read(path)
    except Exception as e:  # noqa: BLE001 -- a corrupt log is reported, not fatal
        return {"file": path.name, "skip": f"read_error {type(e).__name__}"}
    if head.get("dry_run"):
        return {"file": path.name, "skip": "dry_run"}
    if end is None:
        return {"file": path.name, "skip": "no_end_event"}
    if len(frames) < 50:
        return {"file": path.name, "skip": "few_frames"}
    if any(b["tick"] < a["tick"] for a, b in zip(frames, frames[1:])):
        return {"file": path.name, "skip": "clock_reset"}
    y, src, cm, co = label(end, frames)
    ticks, L = RX.running_losses(frames, VALUES)
    known = sum(1 for f in frames for e in f["ents"] if e[1] != -1 and e[1] in VALUES)
    allb = sum(1 for f in frames for e in f["ents"] if e[1] != -1)
    keep = np.r_[np.nonzero(np.diff(ticks // SAMPLE, prepend=-1))[0], len(ticks) - 1]
    own_pr = max((e[3] for e in frames[0]["ents"] if e[1] == -1 and e[0] == frames[0]["side"]), default=0)
    return {"file": path.name, "skip": None, "date": path.name[10:18], "y": y, "label_src": src, "crowns": (cm, co),
            "ticks": ticks[keep], "L": L[keep].astype(np.float32), "end_tick": int(ticks[-1]),
            "body_known_frac": known / max(1, allb), "own_king_max": own_pr, "ckpt": head.get("ckpt", ""),
            "trace": frames[0].get("src", "frame"), "n_obs": len(frames)}


def init():
    global VALUES
    VALUES = load_values()


def main():
    a = sys.argv[1:]
    workers = int(a[a.index("--workers") + 1]) if "--workers" in a else 8
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else None
    files = sorted(Path(a[0]).glob("live_play_202610*.jsonl.gz"))[:limit]
    with mp.Pool(workers, initializer=init) as pool:
        res = pool.map(one, files, chunksize=4)
    ok = [r for r in res if r["skip"] is None]
    np.savez_compressed(a[1], meta=np.array(json.dumps([{k: v for k, v in r.items() if k not in ("ticks", "L")}
                                                         for r in ok])),
                        skipped=np.array(json.dumps([r for r in res if r["skip"]])),
                        **{f"t_{i}": r["ticks"] for i, r in enumerate(ok)}, **{f"L_{i}": r["L"] for i, r in enumerate(ok)})
    from collections import Counter
    print(len(files), "files;", len(ok), "kept;", Counter(r["skip"] for r in res if r["skip"]),
          Counter(r["label_src"] for r in ok), Counter(r["y"] for r in ok))


if __name__ == "__main__":
    main()
