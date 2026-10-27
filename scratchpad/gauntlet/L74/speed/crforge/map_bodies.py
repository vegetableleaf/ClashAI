"""S3b-1: join the two body probes into body_map.json (crforge body row -> what RoyaleSim fin15's production path shows).

Inputs (s3b/): cf_bodies_L11.tsv / cf_bodies_L16.tsv (BodyProbe.java), rs_bodies.tsv (rs_probe.py), both at level 11
for the join (RoyaleSim plays level 11; from_engine's tower factor normalises other levels to it).
Rule, per probed (card, flag): a crforge body matches the RoyaleSim body of the SAME card form with the same max_hp at
level 11 (exact; else within 3%, marked). Its id is what the production path computes, vocab.engine_unit_id(rs_name,
max_hp). No match, or a RoyaleSim body with no vocab id -> listed in "unmatched", stays dropped.

Output: {crforge_name: {"entries": [{rs_card, rs_name, form, vocab_id, vocab_key, max_hp_rule, max_hp_l11, max_hp_l16,
evidence}], "by_name_unique": bool}, "_unmatched": [...], "_meta": {...}}. One crforge row can come from several cards
(Skeleton: Skeletons, Witch, Graveyard...): RoyaleSim names a body by its PARENT card, so the facade must pick the entry
by the card that spawned the body; by_name_unique says when the name alone is enough.

usage: python -I map_bodies.py   (from this folder; writes body_map.json)
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[4]))
from pipeline import vocab  # noqa: E402



def rows(p):
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def form_of(cf_row_name: str, flag: str) -> int:
    """The body's form as obs_contract.entity_form would report it: evolved / hero rows carry it in the row name."""
    n = cf_row_name
    if "_EV1" in n or "Evo" in n:
        return 1
    if "Hero" in n or "_hero" in n:
        return 2
    return 0


def max_hp_rule(key: str | None) -> str | None:
    if key in vocab._SUBSPAWN:
        return {"golem": "golemite if max_hp/f < 2500 else golem",
                "lava_hound": "lava_pups if max_hp/f < 1000 else lava_hound",
                "elixir_golem": "elixir_golem if >= 1100, elixir_golemite if >= 500, else elixir_blob",
                "royal_recruits": "always royal_recruit",
                "mother_witch": "mother_witch_hog if < 400 else mother_witch (400 unmeasured)"}[key] + \
            " (f = the side's tower max_hp / L11 tower max_hp; from_engine fv<5 path)"
    if key in vocab._SPELL_BODY:
        return f"any max_hp -> {vocab._SPELL_BODY[key]} (spell body)"
    return None


def build():
    cf11, cf16, rs = rows(HERE / "s3b/cf_bodies_L11.tsv"), rows(HERE / "s3b/cf_bodies_L16.tsv"), rows(HERE / "s3b/rs_bodies.tsv")
    l16 = {(r["card"], r["flag"], r["body"]): r["max_hp"] for r in cf16}
    rs_by = defaultdict(list)
    for r in rs:
        if r["rs_name"] != "-":
            rs_by[(r["card"], r["flag"])].append(r)
    out, unmatched = defaultdict(list), []
    for r in cf11:
        if r["body"] == "-":
            continue
        card, flag, body, mhp = r["card"], r["flag"], r["body"], int(r["max_hp"])
        cands = rs_by.get((card, flag), [])
        exact = [c for c in cands if int(c["max_hp"]) == mhp]
        near = [c for c in cands if abs(int(c["max_hp"]) - mhp) <= 0.03 * max(mhp, 1)]
        hit = exact[0] if exact else (min(near, key=lambda c: abs(int(c["max_hp"]) - mhp)) if near else None)
        if hit is None or hit["vocab_id"] in ("None", "-"):
            unmatched.append(dict(crforge_name=body, card=card, flag=int(flag), max_hp_l11=mhp,
                                  why="no RoyaleSim body of this card form with this max_hp" if hit is None
                                  else f"RoyaleSim shows it as {hit['rs_name']} (max_hp {hit['max_hp']}), which has no vocab id",
                                  rs_bodies_of_card=sorted({(c["rs_name"], int(c["max_hp"])) for c in cands})))
            continue
        key = vocab.engine_key(hit["rs_name"])
        ev = (f"crforge {card} flag {flag} -> {body} max_hp {mhp} (L11, x{r['count']}, first tick {r['first_tick']}); "
              f"RoyaleSim fin15 {card} flag {flag} -> {hit['rs_name']} max_hp {hit['max_hp']} "
              f"(x{hit['count']}, first tick {hit['first_tick']}){'' if exact else ' [max_hp within 3%]'}")
        out[body].append(dict(rs_card=card, rs_name=hit["rs_name"], form=form_of(body, flag), vocab_id=int(hit["vocab_id"]),
                              vocab_key=vocab.UNIT_VOCAB[int(hit["vocab_id"])], max_hp_rule=max_hp_rule(key),
                              max_hp_l11=mhp, max_hp_l16=int(l16.get((card, flag, body), -1)),
                              rs_status_flags=int(hit["status_flags"]), evidence=ev))
    res = {}
    for body, ents in sorted(out.items()):
        uniq = {}
        for e in ents:                                   # one entry per (parent card, vocab id, form)
            uniq.setdefault((e["rs_card"], e["vocab_id"], e["form"]), e)
        ents = list(uniq.values())
        res[body] = dict(entries=ents, by_name_unique=len({(e["vocab_id"], e["form"]) for e in ents}) == 1)
    um = {}
    for u in unmatched:
        um.setdefault((u["crforge_name"], u["card"], u["flag"]), u)
    res["_unmatched"] = [u for u in um.values() if u["crforge_name"] not in res]
    drop = HERE / "s3b/drop.json"          # cf_drop.py: names seen in the 223 census matches that no solo probe made
    if drop.is_file():
        done = {u["crforge_name"] for u in res["_unmatched"]}
        for name, n in json.loads(drop.read_text())["names_dropped_after"].items():
            if name not in done:
                res["_unmatched"].append(dict(crforge_name=name, card=None, flag=None, max_hp_l11=None,
                                              why=f"seen on {n} bodies in the 223 census matches, never in a solo "
                                                  "probe (made by kills, curses or other interactions): no "
                                                  "RoyaleSim evidence, left dropped", rs_bodies_of_card=[]))
    res["_meta"] = dict(crforge="ad8ef3a532ada8dea732bf1ecdeb01beef0fb4b0", tables="16.402.22", royalesim="fin15 0.1.36",
                        level_join=11, probe="BodyProbe.java / rs_probe.py, 2,400 ticks per card form, side 0 alone",
                        forms_note="RoyaleSim showed status_flags 0 on every probed body, evolved and hero slots "
                                   "included, so 'form' is read from the crforge row name (_EV1 / Hero), not checked "
                                   "against RoyaleSim")
    return res


def _check(res):
    assert res["Skeleton"]["by_name_unique"] is False                 # Skeletons card vs Witch spawn: parent decides
    assert any(e["rs_card"] == "Witch" and e["vocab_key"] == "witch" for e in res["Skeleton"]["entries"])
    assert {e["vocab_key"] for e in res["Golemite"]["entries"]} == {"golemite"}


if __name__ == "__main__":
    r = build()
    _check(r)
    (HERE / "body_map.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
    print(len(r) - 2, "crforge body names mapped,", len(r["_unmatched"]), "unmatched;",
          sum(not v["by_name_unique"] for k, v in r.items() if not k.startswith("_")), "need the parent card")
