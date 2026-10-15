"""Bait witness session (owner 10-15: classic challenge with Hero Valkyrie / evo Skeleton Army / evo Goblin Barrel, played by
hand, recorded by live_play --dry-run --log-frames). Reports, per side: every reader card_id seen on the board, its catalog name
(pipeline.obs_contract._catalog_names + body_identity.EXT_CARD_IDS + reader_identity_aliases), max_hp / kind / count / first
tick; ids with NO name (the model never sees those bodies); own hand forms seen; hero-button transitions; elixir drops not
explained by a card leaving the hand (= ability presses or unexplained spend).
    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L74/bait_witness/witness.py LOG.jsonl
"""
import collections
import json
import sys

sys.path.insert(0, "C:/Users/benpe/ClashBot")
from pipeline.obs_contract import _catalog_names  # noqa: E402
from pipeline import body_identity as BI  # noqa: E402
from pipeline import reader_identity_aliases as RA  # noqa: E402


def main(path):
    names = RA.extend_names(dict(_catalog_names()))
    ext = {int(k): v for k, v in BI.EXT_CARD_IDS.items()}
    ev = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    frames = [e for e in ev if e["event"] == "frame"]
    me = frames[0]["my_side"]
    ids = collections.defaultdict(lambda: {"n": 0, "first": None, "max_hp": set(), "kind": set()})
    for f in frames:
        for s, x, y, cid, hp, mx, kind, addr in f["ents"]:
            if cid == -1:
                continue
            d = ids[(s == me, cid)]
            d["n"] += 1
            d["first"] = f["tick"] if d["first"] is None else d["first"]
            d["max_hp"].add(mx)
            d["kind"].add(kind)
    print(f"{path}\n{len(frames)} frames, my side {me}, ticks {frames[0]['tick']}..{frames[-1]['tick']}")
    for own in (True, False):
        print(f"\n== {'OWN' if own else 'ENEMY'} board ids")
        for (o, cid), d in sorted(ids.items(), key=lambda kv: kv[1]["first"]):
            if o != own:
                continue
            nm = names.get(cid) or (f"EXT:{ext[cid]}" if cid in ext else "*** UNKNOWN ***")
            print(f"  {cid:>10} {nm:28} frames {d['n']:5d} first tick {d['first']:5d} max_hp {sorted(d['max_hp'])} kind {sorted(d['kind'])}")
    hands = collections.Counter()
    elix, prev_hand = [], None
    for e in ev:
        if e["event"] == "decision":
            p = e["public"]
            hand = {h["deck_index"]: (h["name"], h["form"], h["cost"]) for h in p["own_hand"]}
            for h in p["own_hand"]:
                hands[(h["name"], h["form"])] += 1
            if prev_hand is not None:
                left = [prev_hand[i] for i in prev_hand if i not in hand]
                if left:
                    elix.append((p["raw_tick"], "card", left))
            prev_hand = hand
    print("\n== own hand (name, form 0 base / 1 evo / 2 hero): decisions seen ->", dict(hands))
    print("\n== hero button transitions")
    last = None
    for e in ev:
        if e["event"] == "button" and e["state"] != last:
            print(f"  tick {e['tick']:5d} {e['state']:6s} blue {e['blue']:.3f} grey {e['grey']:.3f}")
            last = e["state"]
    print("\n== own elixir drops >= 0.8 between frames (card plays from the hand log alongside)")
    cards = {t: c for t, _, c in elix}
    for a, b in zip(frames, frames[1:]):
        drop = a["elixir"] - b["elixir"]
        if drop >= 0.8:
            near = [f"{c} @{t}" for t, c in cards.items() if abs(t - b["tick"]) <= 40]
            print(f"  tick {a['tick']:5d}->{b['tick']:5d} drop {drop:4.2f}  cards near: {near}")


if __name__ == "__main__":
    main(sys.argv[1])
