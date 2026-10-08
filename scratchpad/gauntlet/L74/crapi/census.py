"""Meta census over data/battles.jsonl + card-list diff vs the ClashBot references (refs.json, built by make_refs.py).

  python3 census.py [--cutoff 2026-10-07T00:00:00Z]   -> data/census/census_latest.{json,md} (+ a timestamped json)

Tier 1 = battles at/after the cutoff (post balance update), tier 2 = everything (earlier battles included).
Balance update: Supercell "October Balance Changes 2026", posted 2026-10-06 (one third-party says live 10-05 with the
season start). The default cutoff 10-07 00:00 UTC is the first instant certainly after it; 10-05..10-06 is 'boundary'.
"""
import argparse, collections, datetime as dt, json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CUTOFF = "2026-10-07T00:00:00Z"
BOUNDARY = "2026-10-05T00:00:00Z"
ICEBOW = ["Tornado", "Tesla", "Ice Wizard", "X-Bow", "Rocket", "Knight", "The Log", "Skeletons"]   # Tesla, Knight evo
# ponytail: first-match win-condition precedence = coarse archetype; replace with deck clustering if it misleads
ARCH = ["X-Bow", "Mortar", "Lava Hound", "Golem", "Electro Giant", "Elixir Golem", "Goblin Giant", "Three Musketeers",
        "Royal Giant", "Rune Giant", "Giant", "Hog Rider", "Ram Rider", "Battle Ram", "Royal Hogs", "Balloon",
        "Graveyard", "Goblin Barrel", "Goblin Drill", "Miner", "Wall Breakers", "Skeleton Barrel", "Goblin Machine",
        "Goblinstein", "Sparky", "P.E.K.K.A", "Mega Knight", "Royal Recruits"]
# ponytail: hand-made API-name -> RoyaleSim display-name aliases (RoyaleSim uses some internal names)
SIM_ALIAS = {"royal-ghost": "ghost", "wall-breakers": "wallbreakers", "barbarian-barrel": "barb-log",
             "giant-snowball": "snowball", "mother-witch": "witch-mother", "ice-spirit": "ice-spirits",
             "fire-spirit": "fire-spirits", "zappies": "mini-sparkys", "archers": "archers", "heal-spirit": "heal"}


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace(".", "")).strip("-")


def ts(bt):
    """'20261007T123456.000Z' -> '2026-10-07T12:34:56Z' (sortable against the cutoffs)."""
    return f"{bt[0:4]}-{bt[4:6]}-{bt[6:8]}T{bt[9:11]}:{bt[11:13]}:{bt[13:15]}Z" if len(bt) >= 15 else ""


def form(c):
    """Card label with its form: evolutionLevel as the API reports it (0/absent = base)."""
    lv = c.get("evolutionLevel") or 0
    return f"{c['name']}*evo{lv}" if lv else c["name"]


def archetype(names):
    for a in ARCH:
        if a in names:
            return a
    return "Other"


def sides(rows):
    """One record per player side of a 1v1, 8-card battle."""
    for r in rows:
        b = r["battle"]
        t, o = b.get("team", []), b.get("opponent", [])
        if len(t) != 1 or len(o) != 1 or len(t[0].get("cards", [])) != 8 or len(o[0].get("cards", [])) != 8:
            continue
        for me, op in ((t[0], o[0]), (o[0], t[0])):
            names = {c["name"] for c in me["cards"]}
            onames = {c["name"] for c in op["cards"]}
            res = "W" if me.get("crowns", 0) > op.get("crowns", 0) else "L" if me.get("crowns", 0) < op.get("crowns", 0) else "D"
            yield {"time": ts(b.get("battleTime", "")), "type": b.get("type"), "res": res, "cards": me["cards"],
                   "names": names, "deck": " | ".join(sorted(form(c) for c in me["cards"])),
                   "arch": archetype(names), "opp_arch": archetype(onames),
                   "support": [s.get("name") for s in me.get("supportCards", [])],
                   "icebow_n": len(names & set(ICEBOW))}


def wr(c):
    n = c["W"] + c["L"] + c["D"]
    return {"n": n, "W": c["W"], "L": c["L"], "D": c["D"], "win_rate": round(c["W"] / n, 4) if n else None,
            "se": round(math.sqrt(c["W"] / n * (1 - c["W"] / n) / n), 4) if n else None}


def summarize(S, top=40):
    n = len(S)
    if not n:
        return {"sides": 0}
    decks, archs, cards, forms, support = (collections.defaultdict(collections.Counter) for _ in range(5))
    evo_vals = collections.defaultdict(collections.Counter)
    ice = collections.defaultdict(collections.Counter)
    ice_exact = collections.Counter()
    for s in S:
        decks[s["deck"]][s["res"]] += 1
        archs[s["arch"]][s["res"]] += 1
        for c in s["cards"]:
            cards[c["name"]][s["res"]] += 1
            evo_vals[c["name"]][c.get("evolutionLevel") or 0] += 1
        for x in s["support"]:
            support[x][s["res"]] += 1
        if "X-Bow" in s["names"] and s["icebow_n"] >= 6:
            ice[s["opp_arch"]][s["res"]] += 1
            ice["ALL"][s["res"]] += 1
            if s["icebow_n"] == 8:
                ice_exact[s["res"]] += 1
    rank = lambda d: sorted(d.items(), key=lambda kv: -sum(kv[1].values()))
    return {
        "sides": n, "battles": n // 2, "by_type": dict(collections.Counter(s["type"] for s in S)),
        "top_decks": [{"deck": k, "share": round(sum(v.values()) / n, 4), **wr(v)} for k, v in rank(decks)[:top]],
        "distinct_decks": len(decks),
        "archetypes": [{"arch": k, "share": round(sum(v.values()) / n, 4), **wr(v)} for k, v in rank(archs)],
        "card_usage": [{"card": k, "use_rate": round(sum(v.values()) / n, 4), **wr(v),
                        "forms": {str(lv): m for lv, m in sorted(evo_vals[k].items())}} for k, v in rank(cards)],
        "support_cards": [{"card": k, "share": round(sum(v.values()) / n, 4), **wr(v)} for k, v in rank(support)],
        "icebow_family": {"rule": "X-Bow + >=6 of " + ", ".join(ICEBOW), "exact_8": wr(ice_exact),
                          "by_opp_arch": {k: wr(v) for k, v in rank(ice)}},
    }


def card_diff(cards, refs):
    """API card list vs ClashBot's three references. Evo/hero support from the API's maxEvolutionLevel / iconUrls."""
    items = cards.get("items", [])
    api_slug = {slug(c["name"]): c for c in items}
    api_ids = {c["id"]: c for c in items}
    evo = sorted(c["name"] for c in items if (c.get("maxEvolutionLevel") or 0) >= 1)
    out = {"api_cards": len(items), "api_support_items": [s.get("name") for s in cards.get("supportItems", [])],
           "api_card_fields": sorted({k for c in items for k in c}),
           "api_icon_kinds": dict(collections.Counter(k for c in items for k in (c.get("iconUrls") or {}))),
           "api_maxEvolutionLevel_hist": dict(collections.Counter(str(c.get("maxEvolutionLevel") or 0) for c in items)),
           "api_evo_capable": evo,
           "api_maxEvolutionLevel_ge2": sorted(c["name"] for c in items if (c.get("maxEvolutionLevel") or 0) >= 2),
           "api_hero_icon": sorted(c["name"] for c in items if any("hero" in k.lower() for k in (c.get("iconUrls") or {})))}
    if not refs:
        return out
    vocab = set(refs["vocab"]) - {"<pad>"}
    out["vs_ckpt_vocab"] = {"api_not_in_vocab": sorted(api_slug[s]["name"] for s in api_slug if s not in vocab),
                            "vocab_not_in_api": sorted(vocab - set(api_slug))}
    cat = {c["card_id"]: c for c in refs["catalog"]["cards"]}
    cat_ids = set(refs["catalog"]["ids"])
    out["vs_reader_catalog"] = {
        "api_ids_not_in_catalog": sorted(f"{api_ids[i]['name']} ({i})" for i in api_ids if i not in cat_ids),
        "catalog_base_not_in_api": sorted(f"{c['display_name']} ({i})" for i, c in cat.items() if i not in api_ids),
        "api_evo_but_catalog_no_evo_form": sorted(api_ids[i]["name"] for i in api_ids
                                                  if (api_ids[i].get("maxEvolutionLevel") or 0) >= 1
                                                  and i in cat and not cat[i]["evo"]),
        "catalog_evo_but_api_not": sorted(cat[i]["display_name"] for i in cat
                                          if cat[i]["evo"] and i in api_ids
                                          and not (api_ids[i].get("maxEvolutionLevel") or 0) >= 1),
        "catalog_heroes": sorted(c["display_name"] for c in cat.values() if c["hero"]),
    }
    sim = {slug(x) for x in refs["royalesim"]["cards"]}
    sim_evo = {slug(x.split("_EV")[0]) for x in refs["royalesim"]["evolutions"]}
    sim_hero = {slug(x[5:]) for x in refs["royalesim"]["hero_forms"]}
    al = lambda s: SIM_ALIAS.get(s, s)
    out["vs_royalesim"] = {
        "api_not_in_sim": sorted(api_slug[s]["name"] for s in api_slug if al(s) not in sim),
        "api_evo_not_in_sim_evos": sorted(n for n in evo if al(slug(n)) not in sim_evo),
        "sim_heroes": sorted(refs["royalesim"]["hero_forms"]),
        "sim_hero_not_in_api": sorted(h for h in sim_hero if not any(al(s) == h for s in api_slug)),
    }
    return out


def md(rep):
    L = [f"# CR API census {rep['generated']}", "", f"cutoff (tier 1) {rep['cutoff']}; battles in file {rep['rows']}; "
         f"by tier {rep['tiers']}", ""]
    for name in ("tier1_ranked", "tier1_all", "tier2_all"):
        s = rep[name]
        L += [f"## {name}: {s.get('sides', 0)} sides", ""]
        if not s.get("sides"):
            continue
        L += [f"types {s['by_type']}; distinct decks {s['distinct_decks']}", "", "| archetype | share | n | win rate |",
              "|---|---|---|---|"]
        L += [f"| {a['arch']} | {a['share']:.3f} | {a['n']} | {a['win_rate']} |" for a in s["archetypes"]]
        L += ["", "| card | use | win rate | forms (evolutionLevel: count) |", "|---|---|---|---|"]
        L += [f"| {c['card']} | {c['use_rate']:.3f} | {c['win_rate']} | {c['forms']} |" for c in s["card_usage"][:60]]
        L += ["", "Top decks:", ""] + [f"- {d['share']:.3f} n={d['n']} wr={d['win_rate']}: {d['deck']}" for d in s["top_decks"][:15]]
        L += ["", f"Icebow family ({s['icebow_family']['rule']}): exact-8 {s['icebow_family']['exact_8']}", ""]
        L += [f"- vs {k}: {v}" for k, v in s["icebow_family"]["by_opp_arch"].items()]
        L += [""]
    L += ["## Card list diff", "", "```", json.dumps(rep["card_diff"], indent=1), "```"]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cutoff", default=CUTOFF)
    ap.add_argument("--data", default=str(HERE / "data"))
    a = ap.parse_args(argv)
    data = Path(a.data)
    rows = []
    bp = data / "battles.jsonl"
    if bp.is_file():
        for line in bp.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    tier = lambda r: ("post" if ts(r["battle"].get("battleTime", "")) >= a.cutoff
                      else "boundary" if ts(r["battle"].get("battleTime", "")) >= BOUNDARY else "pre")
    t1 = [r for r in rows if tier(r) == "post"]
    S1 = list(sides(t1))
    cards = json.loads((data / "cards_latest.json").read_text(encoding="utf-8")) if (data / "cards_latest.json").is_file() else {}
    refs = json.loads((HERE / "refs.json").read_text(encoding="utf-8")) if (HERE / "refs.json").is_file() else None
    rep = {"generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "cutoff": a.cutoff,
           "rows": len(rows), "tiers": dict(collections.Counter(tier(r) for r in rows)),
           "tier1_ranked": summarize([s for s in S1 if s["type"] == "pathOfLegend"]),
           "tier1_all": summarize(S1), "tier2_all": summarize(list(sides(rows))),
           "card_diff": card_diff(cards, refs) if cards else "no cards_latest.json yet"}
    out = data / "census"
    out.mkdir(parents=True, exist_ok=True)
    js = json.dumps(rep, indent=1)
    (out / "census_latest.json").write_text(js, encoding="utf-8")
    (out / f"census_{rep['generated'].replace(':', '')}.json").write_text(js, encoding="utf-8")
    (out / "census_latest.md").write_text(md(rep), encoding="utf-8")
    print(f"census: {len(rows)} battles, tiers {rep['tiers']}, tier1 ranked sides {rep['tier1_ranked'].get('sides', 0)}"
          f" -> {out / 'census_latest.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
