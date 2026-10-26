"""Plan 10-26 device check G-R2: the same match read live (live_play --log-frames) vs read again from the battle-log
replay viewer (replay_rec/recorder.py). Does the replay reproduce the live reader's board, tick for tick?

    icebow/.venv/Scripts/python.exe -B scratchpad/gauntlet/L74/plan1026/devcheck/cmp_live_replay.py LIVE.jsonl REC.jsonl

Per common game tick: bodies keyed by (side, card_id, kind) and paired greedily by distance; reports exact-board ticks,
tower-HP agreement, unpaired bodies, position / HP differences, and the replay's extra fields (opponent hand / elixir).
"""
import json
import sys
from collections import Counter, defaultdict


def live_frames(path):
    out = {}
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        if e.get("event") == "frame":
            out[e["tick"]] = [tuple(b[:7]) for b in e["ents"]]          # side, x, y, card, hp, max_hp, kind
    return out


def rec_frames(path):
    out, extra = {}, {}
    for line in open(path, encoding="utf-8"):
        e = json.loads(line)
        f = e.get("f") if e.get("event") == "frame" else None
        if not f or not f.get("battle_active") or not f.get("coherent") or f.get("game_tick", -1) < 0:
            continue
        out[f["game_tick"]] = [(b["side"], b["x"], b["y"], b.get("card_id", -1), b["hp"], b["max_hp"], b["kind"])
                               for b in f["entities"]]
        extra[f["game_tick"]] = [(p.get("side"), p.get("elixir_raw"), p.get("hand_deck_indices")) for p in f["players"]]
    return out, extra


def pair(a, b):
    ga, gb = defaultdict(list), defaultdict(list)
    for x in a:
        ga[(x[0], x[3], x[6])].append(x)
    for x in b:
        gb[(x[0], x[3], x[6])].append(x)
    pairs, una, unb = [], 0, 0
    for k in set(ga) | set(gb):
        la, lb = list(ga[k]), list(gb[k])
        while la and lb:
            i, j = min(((i, j) for i in range(len(la)) for j in range(len(lb))),
                       key=lambda ij: abs(la[ij[0]][1] - lb[ij[1]][1]) + abs(la[ij[0]][2] - lb[ij[1]][2]))
            pairs.append((la.pop(i), lb.pop(j)))
        una += len(la)
        unb += len(lb)
    return pairs, una, unb


def main(lp, rp):
    L = live_frames(lp)
    R, extra = rec_frames(rp)
    common = sorted(set(L) & set(R))
    print(f"live frames {len(L)} (ticks {min(L)}-{max(L)}), replay frames {len(R)} (ticks {min(R)}-{max(R)}), common {len(common)}")
    exact = tower_eq = 0
    una = unb = 0
    dpos, dhp = Counter(), Counter()
    first_diff = None
    for t in common:
        a, b = L[t], R[t]
        if sorted(a) == sorted(b):
            exact += 1
        elif first_diff is None:
            first_diff = t
        ta = sorted(x for x in a if x[6] in (12, 13))
        tb = sorted(x for x in b if x[6] in (12, 13))
        tower_eq += ta == tb
        p, ua, ub = pair(a, b)
        una += ua
        unb += ub
        for x, y in p:
            dpos[min(max(abs(x[1] - y[1]), abs(x[2] - y[2])) // 100, 50)] += 1     # 1/10 tile buckets
            dhp[min(abs(x[4] - y[4]), 1000) // 10] += 1
    n = sum(dpos.values())
    print(f"exact board ticks {exact}/{len(common)} = {exact / max(1, len(common)):.4f}; first non-exact tick {first_diff}")
    print(f"tower rows equal {tower_eq}/{len(common)} = {tower_eq / max(1, len(common)):.4f}")
    print(f"paired bodies {n}; live-only {una}, replay-only {unb}")
    print("position diff (max |dx|,|dy| in 0.1-tile buckets):", sorted(dpos.items())[:12])
    print("hp diff (10-HP buckets):", sorted(dhp.items())[:12])
    hands = sum(1 for t in extra for s, el, h in extra[t] if h and all(i >= 0 for i in h))
    print(f"replay player rows with a full visible hand: {hands} over {len(extra)} frames x 2 sides")


if __name__ == "__main__":
    main(*sys.argv[1:3])
