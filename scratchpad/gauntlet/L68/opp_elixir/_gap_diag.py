"""Exploratory: context around NEW-rule extra charges at gap 0 (count-conserving tracker), per card."""
import collections, glob, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[3]))
import gap_sim as G
want = set(sys.argv[1:]) or {"skeletons", "goblin_barrel", "skeleton_barrel"}
shown = collections.Counter()
for deck in ("icebow", "hogeq"):
    for f in sorted(glob.glob(str(G.REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json")))[:60]:
        d = json.load(open(f))
        by_t = {fr["tick"]: fr["entities"] for fr in d["frames"]}
        by_t.update({pf["tick"]: pf["entities"] for pf in d.get("play_frames", [])})
        tracked = G.track(sorted(by_t.items()))
        log = [e for e in d["log"] if e.get("accepted")]
        for opp in (0, 1):
            truth = [(e["tick"], e["card"].replace("-", "_")) for e in log if e["side"] == opp and G.visible(e["card"].replace("-", "_"))]
            det, charged, tb = G.new_mod.PlayDetector(), [], {}
            for tick, bodies in tracked:
                ents = [{"address": a, "side": s, "card_id": G.NAME_ID[n], "kind": 15, "x": x, "y": y, "hp": hp, "max_hp": m}
                        for a, s, n, hp, m, x, y, b in bodies]
                tb[tick] = [(a, G.vocab.engine_key(n), m, x, y) for a, s, n, hp, m, x, y, b in bodies if s == opp]
                fr = {"game_tick": tick, "entities": ents, "players": [{"side": s, "hand_deck_indices": [0] * 4 if s != opp else [-1] * 4} for s in (0, 1)]}
                charged += [(ev.tick, ev.key) for ev in det.feed(fr)]
            used = set()
            for t, k in truth:
                h = next((i for i, (ct, ck) in enumerate(charged) if i not in used and ck == k and t <= ct <= t + 60), None)
                if h is not None: used.add(h)
            for i, (ct, ck) in enumerate(charged):
                if i in used or ck not in want or shown[ck] >= 3: continue
                shown[ck] += 1
                print(f"EXTRA {ck} @{ct} {f[-20:]} opp{opp} truth-near:", [(t, k) for t, k in truth if k == ck and ct - 300 <= t <= ct + 20],
                      "charges-near:", [c for c in charged if c[1] == ck and ct - 300 <= c[0] <= ct])
                for tt in sorted(t2 for t2 in tb if ct - 60 <= t2 <= ct):
                    print("    ", tt, [(a, m, int(x), int(y)) for a, kk, m, x, y in tb[tt] if kk == ck])
