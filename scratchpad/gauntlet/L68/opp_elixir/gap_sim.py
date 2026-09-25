"""Reader-gap simulation: OLD (v1, kind-gated + stored-hp) vs NEW (board-parent) play detection, on engine frames.

No reader recording with opponent plays exists, so reader frames are SYNTHESISED from corpus_v6 engine frames:
  * stream = `frames` (every 20 ticks) + `play_frames` (at play ticks), merged by tick -- ~1 s cadence, coarser
    than the 100 ms reader;
  * addresses: engine frames carry none, so a greedy tracker assigns them on the FULL stream (per side, name,
    max_hp; nearest body within 1000 + 150/tick engine units, then -- default -- leftover old/new bodies are
    paired regardless of distance so a new address appears only when the group's count grows). Identity
    breaks are tracker artifacts a real reader (stable addresses) does not have; count-conserving removes
    them but also hides a play whose body appears in the same frame another same-card body vanishes (both
    rules equally). ``--distance-only`` keeps the breaks, as an upper bound on artifact charges;
  * gaps: every 10 s one window of G s is dropped (random phase per replay); addresses persist across a gap,
    as reader addresses do;
  * kind at first sight (only the OLD rule reads it): a play body (first seen <= 120 ticks after a same-card
    play; Graveyard 220) is deploying (14 troop / 12 building) iff the 100 ms reader would have seen it within
    20 ticks of its birth (kind_survey: 14/12 at age 0-19, 15/13 from ~20), birth = its first full-stream tick
    (up to 20 ticks LATE -> favourable to the old rule). Spawn bodies get 15/13 -- also FAVOURABLE to the old
    rule, which then never charges a spawn by kind (engine: Hut/Furnace/Golem spawns do show 14).
Truth = the opponent's accepted log plays of cards with bodies (bodiless spells and Mirror excluded). A charge
matches a truth play of the same card within [t, t + 120 + 20 x G] ticks. missed = unmatched truth plays,
extra = unmatched charges (double charges, spawns charged, tracker artifacts).

    icebow/.venv/Scripts/python.exe scratchpad/gauntlet/L68/opp_elixir/gap_sim.py [replays_per_deck]
"""
from __future__ import annotations

import collections
import glob
import importlib.util
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
from pipeline import opp_elixir_count as new_mod                      # noqa: E402
from pipeline import vocab                                            # noqa: E402
from pipeline.obs_contract import _catalog_names                      # noqa: E402

_spec = importlib.util.spec_from_file_location("pipeline._oc_v1", HERE / "_opp_elixir_count_v1.py")
old_mod = importlib.util.module_from_spec(_spec)
sys.modules["pipeline._oc_v1"] = old_mod
_spec.loader.exec_module(old_mod)

BODY_SPELLS = {"graveyard", "goblin_barrel", "barbarian_barrel", "royal_delivery", "clone"}
NAME_ID = {}
for _cid, _n in sorted(_catalog_names().items(), reverse=True):
    NAME_ID[_n] = _cid
GAPS = (0, 1, 2, 3)
WIN = 120          # ticks: Goblin Barrel goblins land 60-80 ticks after the cast
CONSERVE = True   # --distance-only: identities break on > 1000 + 150/tick jumps (miner, fast swarms)


def visible(key: str) -> bool:
    db = new_mod.card_db()
    return key != "mirror" and (db.kind(key) != "spell" or key in BODY_SPELLS)


def track(stream):
    """[(tick, [ent])] -> [(tick, [(addr, side, name, hp, max_hp, x, y, born)])], greedy nearest tracking per
    (side, name); pairs with equal (or unreadable, <= 0) max_hp first, so a body whose max_hp flickers to -1
    keeps its address, and a spawn never inherits its parent's."""
    out, prev, nxt, prev_t = [], {}, 0, None
    for tick, ents in stream:
        cur = collections.defaultdict(list)
        for e in ents:
            if str(e[3]) == "-1" or (e[5] is not None and e[5] > 0 and e[4] is not None and e[4] <= 0):
                continue
            cur[(e[0], e[3])].append(e)
        lim = 1000 + 150 * (tick - prev_t if prev_t is not None else 0)
        frame, now = [], {}
        for grp, es in cur.items():
            old = prev.get(grp, [])
            pairs = sorted((int(e[5] != o[3] and e[5] > 0 and o[3] > 0), (e[1] - o[0]) ** 2 + (e[2] - o[1]) ** 2, i, j)
                           for i, e in enumerate(es) for j, o in enumerate(old))
            pairs = [(mm, d2, i, j) for mm, d2, i, j in pairs]
            ai, aj, born = {}, set(), {}
            for mm, d2, i, j in pairs:
                if i not in ai and j not in aj and d2 <= lim * lim and not mm:
                    ai[i], born[i] = old[j][2], old[j][4]
                    aj.add(j)
            if CONSERVE:                  # a new address only when the count of that max_hp grows (no breaks)
                for mm, d2, i, j in pairs:
                    if i not in ai and j not in aj and not mm:
                        ai[i], born[i] = old[j][2], old[j][4]
                        aj.add(j)
            for i, e in enumerate(es):
                if i not in ai:
                    nxt += 1
                    ai[i], born[i] = nxt, tick
                mhp = e[5] if e[5] is not None else -1
                now.setdefault(grp, []).append((e[1], e[2], ai[i], mhp, born[i]))
                frame.append((ai[i], e[0], e[3], e[4], mhp, e[1], e[2], born[i]))
        prev, prev_t = now, tick
        out.append((tick, frame))
    return out


def run(per_deck: int) -> dict:
    rng = random.Random(0)
    res = {(r, g): collections.Counter() for r in ("old", "new") for g in GAPS}
    for deck in ("icebow", "hogeq"):
        for f in sorted(glob.glob(str(REPO / f"scratchpad/gauntlet/ext/corpus_v6/{deck}/replay_*.json")))[:per_deck]:
            d = json.load(open(f))
            by_t = {fr["tick"]: fr["entities"] for fr in d["frames"]}
            by_t.update({pf["tick"]: pf["entities"] for pf in d.get("play_frames", [])})
            tracked = track(sorted(by_t.items()))
            log = [e for e in d["log"] if e.get("accepted")]
            phase = rng.randrange(200)
            for opp in (0, 1):
                truth = [(e["tick"], e["card"].replace("-", "_")) for e in log if e["side"] == opp]
                truth = [(t, k) for t, k in truth if visible(k)]
                for g in GAPS:
                    def in_gap(t):
                        return g > 0 and (t - phase) % 200 < 20 * g
                    def gap_end(t):
                        return t - (t - phase) % 200 + 20 * g
                    for rule, mod in (("old", old_mod), ("new", new_mod)):
                        det, charged, seen_addr = mod.PlayDetector(), [], set()
                        firsts = collections.defaultdict(list)    # key -> kept-frame ticks a new opp body showed
                        for tick, bodies in tracked:
                            if in_gap(tick):
                                continue
                            ents = []
                            for addr, side, name, hp, mhp, x, y, born in bodies:
                                cid = NAME_ID.get(name)
                                if cid is None:
                                    continue
                                key = vocab.engine_key(name)
                                bldg = new_mod.card_db().kind(key) == "building"
                                kind = 13 if bldg else 15
                                if addr not in seen_addr and side == opp:
                                    seen_addr.add(addr)
                                    firsts[key].append(tick)
                                    win = 220 if key == "graveyard" else 120
                                    if any(k == key and born - win <= t < born for t, k in truth):
                                        # play body, born ~ its first full-stream tick: deploying iff the 100 ms
                                        # reader would see it < 20 ticks after birth
                                        if not in_gap(born) or gap_end(born) - born < 20:
                                            kind = 12 if bldg else 14
                                ents.append({"address": addr, "side": side, "card_id": cid, "kind": kind,
                                             "x": x, "y": y, "hp": hp, "max_hp": mhp})
                            fr = {"game_tick": tick, "entities": ents,
                                  "players": [{"side": s, "hand_deck_indices": [0, 1, 2, 3] if s != opp else [-1] * 4}
                                              for s in (0, 1)]}
                            charged += [(ev.tick, ev.key, ev.cost) for ev in det.feed(fr)]
                        used, c = set(), res[(rule, g)]
                        for t, k in truth:
                            hit = next((i for i, (ct, ck, _) in enumerate(charged)
                                        if i not in used and ck == k and t <= ct <= t + WIN + 20 * g), None)
                            if hit is None:
                                c["missed"] += 1
                                # no new body of that card ever reached a kept frame: no rule could charge it
                                c["missed_unseen"] += not any(t < ft <= t + WIN + 20 * g for ft in firsts[k])
                                c["missed_elixir"] += new_mod.card_cost(k) or 0
                            else:
                                used.add(hit)
                        c["truth"] += len(truth)
                        c["charged"] += len(charged)
                        for i, (ct, ck, cc) in enumerate(charged):
                            if i not in used:
                                c["extra"] += 1
                                c["extra_elixir"] += cc or 0
                                c["extra:" + ck] += 1
    return res


if __name__ == "__main__":
    if "--distance-only" in sys.argv:
        CONSERVE = False
        sys.argv.remove("--distance-only")
    per_deck = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    res = run(per_deck)
    rows = {f"{r}|gap{g}s": dict(c) for (r, g), c in res.items()}
    (HERE / ("gap_sim.json" if CONSERVE else "gap_sim_distance_only.json")).write_text(json.dumps({"replays_per_deck": per_deck, "conserve": CONSERVE, "rows": rows}, indent=1))
    print(f"replays per deck {per_deck} (both sides graded as the opponent); count-conserving tracker {CONSERVE}")
    print("rule gap  truth  missed (of which never seen)  miss%  missed_elixir  extra  extra_elixir  top extra cards")
    for (r, g), c in sorted(res.items(), key=lambda x: (x[0][1], x[0][0])):
        top = sorted(((v, k[6:]) for k, v in c.items() if k.startswith("extra:")), reverse=True)[:5]
        print(f"{r:4s} {g}s  {c['truth']:6d} {c['missed']:6d} ({c['missed_unseen']:5d}) {100 * c['missed'] / max(1, c['truth']):6.2f} "
              f"{c['missed_elixir']:13.0f} {c['extra']:6d} {c['extra_elixir']:12.0f}  {top}")
