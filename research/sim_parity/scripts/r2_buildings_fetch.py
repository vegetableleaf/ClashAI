# -*- coding: utf-8 -*-
"""r2 buildings group: fetch the 12 building card pages, archive wikitext, record revids."""
import json, time, re, urllib.request, urllib.parse, sys, io

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
    time.sleep(0.25)
    return data

PAGES = {
    "barbarian_hut": "Barbarian Hut",
    "bomb_tower": "Bomb Tower",
    "cannon": "Cannon",
    "elixir_collector": "Elixir Collector",
    "goblin_cage": "Goblin Cage",
    "goblin_drill": "Goblin Drill",
    "goblin_hut": "Goblin Hut",
    "inferno_tower": "Inferno Tower",
    "mortar": "Mortar",
    "tesla": "Tesla",
    "tombstone": "Tombstone",
    "x_bow": "X-Bow",
}

meta = {}
for key, title in PAGES.items():
    try:
        d = api({"action": "parse", "page": title, "prop": "wikitext|revid", "format": "json"})
        wt = d["parse"]["wikitext"]["*"]
        revid = d["parse"]["revid"]
        realtitle = d["parse"]["title"]
    except Exception as e:
        meta[key] = {"title": title, "error": repr(e)}
        print(f"FAIL {key}: {e!r}")
        continue
    fn = WEBCACHE + title.replace("/", "_").replace(" ", "_") + ".wikitext"
    with open(fn, "w", encoding="utf-8") as f:
        f.write(wt)
    meta[key] = {"title": title, "parsed_title": realtitle, "revid": revid,
                 "fetched": "2026-08-26", "bytes": len(wt), "file": fn}
    print(f"OK {key}: title={realtitle!r} revid={revid} bytes={len(wt)}")

with open(LEDGER + "r2_buildings_fetchmeta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, indent=1)
