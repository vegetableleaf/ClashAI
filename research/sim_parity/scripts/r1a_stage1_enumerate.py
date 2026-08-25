# -*- coding: utf-8 -*-
"""r1a stage 1: enumerate card categories, probe <Card>/Evolution existence,
and fetch the wiki's Evolution master page. Writes intermediate JSON to ledger/."""
import json, time, urllib.request, urllib.parse, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
BASE = "https://clashroyale.fandom.com/api.php"
HDRS = {"User-Agent": "icebow-monitor/1.0 (+local)"}
WEBCACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache/"
LEDGER = "C:/Users/benpe/ClashBot/research/sim_parity/ledger/"

def api(params):
    qs = urllib.parse.urlencode(params)
    req = urllib.request.Request(BASE + "?" + qs, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    time.sleep(0.2)
    return data

failures = []

def category_members(cat):
    members, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat,
             "cmlimit": "500", "format": "json"}
        if cont: p["cmcontinue"] = cont
        try:
            d = api(p)
        except Exception as e:
            failures.append(f"categorymembers {cat}: {e!r}")
            return members
        members += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        cont = d.get("continue", {}).get("cmcontinue")
        if not cont: break
    return members

cats = ["Troop Cards", "Building Cards", "Spell Cards", "Champion Cards"]
cards = {}
for c in cats:
    ms = category_members(c)
    cards[c] = ms
    print(f"{c}: {len(ms)} members")

# flat unique card list, skip Category:/File:/Template: entries and existing subpages
flat = []
seen = set()
for c in cats:
    for t in cards[c]:
        if ":" in t.split("/")[0] and not t.startswith("Category talk"):
            # skip namespaced entries like Category:X, File:X
            if t.split(":")[0] in ("Category", "File", "Template", "User"): continue
        if t in seen: continue
        seen.add(t); flat.append(t)
print(f"unique titles: {len(flat)}")

# probe existence of <Card>/Evolution in batches of 50
# only for base card pages (no existing slash)
bases = [t for t in flat if "/" not in t]
probe_titles = [t + "/Evolution" for t in bases]
# mandatory probes even if not in categories
for extra in ["Berserker/Evolution", "Giant/Evolution", "Arrows/Evolution", "Elite Barbarians/Evolution"]:
    if extra not in probe_titles: probe_titles.append(extra)

existing, missing = [], []
for i in range(0, len(probe_titles), 50):
    batch = probe_titles[i:i+50]
    try:
        d = api({"action": "query", "titles": "|".join(batch), "format": "json"})
    except Exception as e:
        failures.append(f"existence batch {i}: {e!r}")
        continue
    pages = d.get("query", {}).get("pages", {})
    # map normalized titles back
    norm = {n["from"]: n["to"] for n in d.get("query", {}).get("normalized", [])}
    got = {}
    for pid, pg in pages.items():
        got[pg["title"]] = ("missing" not in pg)
    for t in batch:
        nt = norm.get(t, t)
        if got.get(nt): existing.append(nt)
        else: missing.append(nt)
print(f"existing evo subpages: {len(existing)}; missing: {len(missing)}")

# fetch the Evolution master page candidates
master_candidates = ["Card Evolution", "Evolution", "Evolutions", "Card Evolutions"]
master_found = {}
for mc in master_candidates:
    try:
        d = api({"action": "parse", "page": mc, "prop": "wikitext|revid", "format": "json"})
    except Exception as e:
        failures.append(f"master {mc}: {e!r}")
        continue
    if "error" in d:
        master_found[mc] = None
        continue
    wt = d["parse"]["wikitext"]["*"]
    revid = d["parse"]["revid"]
    master_found[mc] = {"revid": revid, "len": len(wt), "redirect": wt.lower().startswith("#redirect")}
    fn = WEBCACHE + mc.replace("/", "_").replace(" ", "_") + ".wikitext"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(wt)
    print(f"master page {mc}: revid={revid} len={len(wt)} redirect={master_found[mc]['redirect']}")

out = {"fetched": "2026-08-25", "categories": {c: cards[c] for c in cats},
       "unique_base_cards": bases, "evo_existing": existing, "evo_missing": missing,
       "master_pages": master_found, "failures": failures}
with open(LEDGER + "r1a_stage1.json", "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1, ensure_ascii=False)
print("FAILURES:", failures)
print("EXISTING:", existing)
