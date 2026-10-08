"""L74 crawl: which cards / evolutions / heroes in the CURRENT game are missing from
(a) the live checkpoint's card_vocab, (b) the live reader catalog (pipeline.obs_contract._catalog_names),
(c) RoyaleSim's catalog (research/ext/Royale/RoyaleSim/data/derived/cards.json).

Current-game roster = Clash Royale Fandom wiki via api.php (type categories minus Category:Removed Cards,
the Heroes / Card Evolution pages, the 2026 Version History "Add" lines) + the official Supercell posts the
wiki has not caught up with yet (OFFICIAL below). Wiki responses are cached in wiki_cache.json; --fetch
refreshes them at 1 request/s. No login, no RoyaleAPI.

    .venv/Scripts/python.exe scratchpad/gauntlet/L74/crawl/card_gap.py [--fetch]

Writes card_gap.json next to this file and prints the markdown table.
"""
import argparse
import ast
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIVE = Path("C:/Users/benpe/ClashBot")              # data (checkpoint, ext catalogs) lives in the main checkout
CACHE = HERE / "wiki_cache.json"
API = "https://clashroyale.fandom.com/api.php"
CATS = ["Troop Cards", "Spell Cards", "Building Cards", "Removed Cards",
        "1-Cycles Evolutions", "2-Cycles Evolutions", "3-Cycles Evolutions"]
PAGES = ["Heroes", "Card Evolution", "Version History"]
# Official posts newer than the wiki (fetched 2026-10-08):
#  https://supercell.com/en/games/clashroyale/blog/release-notes/new-season-shocktober/  (2026-10-05)
#  https://supercell.com/en/games/clashroyale/blog/release-notes/new-season-minion-academy/ (2026-09-07; wiki has it)
OFFICIAL = [("electro-wizard", "hero", "official 2026-10-05 Shocktober post"),
            ("electro-giant", "evo", "official 2026-10-05 Shocktober post (Album Event 10-06..11-02)")]


def _call(**p):
    p["format"] = "json"
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(p),
                                 headers={"User-Agent": "ClashBot-research/1.0 (1 req/s)"})
    time.sleep(1.0)                                  # polite: at most 1 request per second
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def fetch() -> dict:
    out = {"fetched_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "cats": {}, "pages": {}}
    for cat in CATS:
        titles, cont = [], {}
        while True:
            r = _call(action="query", list="categorymembers", cmtitle="Category:" + cat, cmlimit=500, **cont)
            titles += [m["title"] for m in r["query"]["categorymembers"] if m["ns"] == 0]
            if "continue" not in r:
                break
            cont = {"cmcontinue": r["continue"]["cmcontinue"]}
        out["cats"][cat] = titles
    for page in PAGES:
        out["pages"][page] = _call(action="parse", page=page, prop="wikitext")["parse"]["wikitext"]["*"]
    return out


def slug(title: str) -> str:
    """Wiki title -> RoyaleAPI slug: 'Mini P.E.K.K.A.' -> 'mini-pekka', 'The Log' -> 'the-log'."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower().replace(".", "").replace("'", "")).strip("-")


def roster(w: dict) -> dict:
    """{(base_slug, kind): source} for kind in card / evo / hero."""
    removed = {slug(t) for t in w["cats"]["Removed Cards"]}
    items = {}

    def add(title, src):
        base, _, form = title.partition("/")
        kind = {"": "card", "Evolution": "evo", "Hero": "hero"}.get(form)
        if kind and slug(base) not in removed:
            items.setdefault((slug(base), kind), src)

    for cat in CATS:
        if cat != "Removed Cards":
            for t in w["cats"][cat]:
                add(t, "wiki category " + cat)
    for page in ("Heroes", "Card Evolution"):
        for t in re.findall(r"\[\[([^]|#]+/(?:Hero|Evolution))", w["pages"][page]):
            add(t, "wiki page " + page)
    vh = w["pages"]["Version History"]
    for line in vh.splitlines():
        if "Balance|Add" in line and ("New [[Heroes" in line or "New [[Card Evolution" in line or "New [[Cards" in line):
            for t in re.findall(r"\[\[([^]|#:]+)(?:\|[^]]*)?\]\]", line):
                if t not in ("Heroes", "Cards", "Card Evolution", "Heroes|Hero"):
                    add(t, "wiki Version History")
    for s, kind, src in OFFICIAL:
        items.setdefault((s, kind), src)
    return items


def vocab_a() -> set:
    import torch
    p = (LIVE / "scratchpad/gauntlet/L70/live/CKPT_OVERRIDE").read_text().strip()
    return set(torch.load(p, map_location="cpu", weights_only=False)["card_vocab"])


def aliases() -> dict:
    """replay_drive.SLUG_ALIASES (RoyaleAPI slug -> catalog internal name), read without importing native_core."""
    src = (LIVE / "research/sandbox_tools/replay_drive.py").read_text(encoding="utf-8")
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "SLUG_ALIASES":
            return ast.literal_eval(node.value)
    raise SystemExit("SLUG_ALIASES not found")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="refresh wiki_cache.json (1 request/s)")
    a = ap.parse_args()
    if a.fetch or not CACHE.exists():
        CACHE.write_text(json.dumps(fetch(), indent=1), encoding="utf-8")
    w = json.loads(CACHE.read_text(encoding="utf-8"))
    items = roster(w)

    va = vocab_a()
    sys.path.insert(0, str(LIVE))
    from pipeline.obs_contract import _catalog_names
    names_b = _catalog_names()
    live_cat = json.loads((LIVE / "research/ext/cr-native-sandbox/native_core/data/live_card_catalog.json")
                          .read_text(encoding="utf-8"))["cards"]
    sim = json.loads((LIVE / "research/ext/Royale/RoyaleSim/data/derived/cards.json").read_text(encoding="utf-8"))
    al = aliases()
    by_norm = {}
    for c in live_cat:
        by_norm.setdefault(norm(c["internal_name"]), c)
        by_norm.setdefault(norm(c["display_name"]), c)
    sim_base = {norm(c["name"]) for c in sim["cards"]} | {norm(c["display_name"]) for c in sim["cards"]}
    sim_evo = {norm(c["form_of"]) for c in sim["evolutions"]}
    sim_hero = {norm(c["form_of"]) for c in sim["hero_forms"]}

    rows = []
    for (s, kind), src in sorted(items.items()):
        c = by_norm.get(norm(al.get(s, s)))
        internal = c["internal_name"] if c else None
        in_a = s in va                                   # card_vocab holds base slugs only (0 -ev1/-hero keys)
        if kind == "card":
            in_b = bool(c) and int(c["card_id"]) in names_b
            in_c = norm(s) in sim_base or (c is not None and norm(internal) in sim_base)
        else:
            fid = c and c.get("evolution_form_id" if kind == "evo" else "hero_form_id")
            if kind == "hero" and internal == "IceWizard":
                fid = fid or 203000023                   # pipeline/reader_identity_aliases.HERO_ICE_WIZARD_ID
            in_b = bool(fid) and int(fid) in names_b
            in_c = bool(c) and norm(internal) in (sim_evo if kind == "evo" else sim_hero)
            in_a = None                                  # no form tokens exist in (a): see note
        rows.append({"slug": s, "kind": kind, "catalog_internal": internal, "source": src,
                     "in_a_vocab": in_a, "in_b_reader": in_b, "in_c_royalesim": in_c})

    missing = [r for r in rows if r["in_a_vocab"] is False or not r["in_b_reader"] or not r["in_c_royalesim"]]
    out = {"roster_counts": {k: sum(r["kind"] == k for r in rows) for k in ("card", "evo", "hero")},
           "a_vocab_size": len(va), "a_form_keys": sorted(k for k in va if re.search(r"-(ev\d+|hero)$", k)),
           "a_not_in_roster": sorted(k for k in va if k != "<pad>" and (k, "card") not in items),
           "b_ids": len(names_b), "c_counts": {"cards": len(sim["cards"]), "evolutions": len(sim["evolutions"]),
                                                 "hero_forms": len(sim["hero_forms"])},
           "wiki_fetched_utc": w["fetched_utc"], "rows": rows}
    (HERE / "card_gap.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

    yn = lambda v: "n/a" if v is None else ("yes" if v else "**MISSING**")
    print("roster:", out["roster_counts"], "| (a) vocab", len(va), "form keys", out["a_form_keys"],
          "| (b) ids", len(names_b), "| (c)", out["c_counts"])
    print("(a) keys not in the current roster:", out["a_not_in_roster"])
    print("\n| card | kind | (a) vocab | (b) reader | (c) RoyaleSim | source |\n|---|---|---|---|---|---|")
    for r in missing:
        print("| %s | %s | %s | %s | %s | %s |" % (r["slug"], r["kind"], yn(r["in_a_vocab"]),
                                                  yn(r["in_b_reader"]), yn(r["in_c_royalesim"]), r["source"]))


if __name__ == "__main__":
    main()
