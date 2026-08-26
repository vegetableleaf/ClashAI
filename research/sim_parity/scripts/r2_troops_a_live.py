import json, time, urllib.request, urllib.parse, os, hashlib

BASE = "https://clashroyale.fandom.com/api.php"
UA = {'User-Agent': 'icebow-monitor/1.0 (+local)'}
CACHE = r"C:/Users/benpe/ClashBot/research/sim_parity/webcache"
OUT   = r"C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_troops_a_livecheck.json"

# page title -> (cache_file, [keys])
PAGES = [
 ("Archers",                 "Archers.wikitext",                 ["archers"]),
 ("Baby Dragon",             "Baby_Dragon.wikitext",             ["baby_dragon"]),
 ("Balloon",                 "Balloon.wikitext",                 ["balloon"]),
 ("Bandit",                  "Bandit.wikitext",                  ["bandit"]),
 ("Barbarians",              "Barbarians.wikitext",              ["barbarians"]),
 ("Bats",                    "Bats.wikitext",                    ["bats"]),
 ("Battle Healer",           "Battle_Healer.wikitext",           ["battle_healer"]),
 ("Battle Ram",              "Battle_Ram.wikitext",              ["battle_ram"]),
 ("Berserker",               "Berserker.wikitext",               ["berserker"]),
 ("Bomber",                  "Bomber.wikitext",                  ["bomber"]),
 ("Bowler",                  "Bowler.wikitext",                  ["bowler"]),
 ("Suspicious Bush",         "Suspicious_Bush.wikitext",         ["bush_goblin"]),
 ("Cannon Cart",             "Cannon_Cart.wikitext",             ["cannon_cart"]),
 ("Dark Prince",             "Dark_Prince.wikitext",             ["dark_prince"]),
 ("Dart Goblin",             "Dart_Goblin.wikitext",             ["dart_goblin"]),
 ("Goblin Barrel/Evolution", "Goblin_Barrel_Evolution.wikitext", ["decoy_goblin"]),
 ("Electro Dragon",          "Electro_Dragon.wikitext",          ["electro_dragon"]),
 ("Electro Giant",           "Electro_Giant.wikitext",           ["electro_giant"]),
 ("Electro Spirit",          "Electro_Spirit.wikitext",          ["electro_spirit"]),
 ("Electro Wizard",          "Electro_Wizard.wikitext",          ["electro_wizard"]),
 ("Elite Barbarians",        "Elite_Barbarians.wikitext",        ["elite_barbarians"]),
 ("Elixir Golem",            "Elixir_Golem.wikitext",            ["elixir_golem","elixir_golemite","elixir_blob"]),
 ("Executioner",             "Executioner.wikitext",             ["executioner"]),
 ("Fire Spirit",             "Fire_Spirit.wikitext",             ["fire_spirit"]),
 ("Firecracker",             "Firecracker.wikitext",             ["firecracker"]),
 ("Fisherman",               "Fisherman.wikitext",               ["fisherman"]),
 ("Flying Machine",          "Flying_Machine.wikitext",          ["flying_machine"]),
 ("Furnace",                 "Furnace.wikitext",                 ["furnace"]),
 ("Royal Ghost/Evolution",   "Royal_Ghost_Evolution.wikitext",   ["ghost_souldier"]),
 ("Giant",                   "Giant.wikitext",                   ["giant"]),
]

def fetch(title):
    q = urllib.parse.urlencode({"action":"parse","page":title,"prop":"wikitext|revid","format":"json"})
    req = urllib.request.Request(BASE + "?" + q, headers=UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))

res = {}
for title, cf, keys in PAGES:
    path = os.path.join(CACHE, cf)
    try:
        d = fetch(title)
        p = d["parse"]
        live_txt = p["wikitext"]["*"]
        live_rev = p.get("revid")
        real_title = p.get("title")
    except Exception as e:
        res[title] = {"error": repr(e), "keys": keys}
        print("ERR", title, e); time.sleep(0.25); continue

    cached_txt = None
    if os.path.exists(path):
        cached_txt = open(path, encoding="utf-8").read()

    same = (cached_txt is not None and cached_txt == live_txt)
    # overwrite cache with the live copy (archive newest)
    open(path, "w", encoding="utf-8").write(live_txt)

    res[title] = {
        "page_title_returned": real_title,
        "cache_file": cf,
        "keys": keys,
        "live_revid": live_rev,
        "cached_text_identical": same,
        "edit_war": "pass" if same else "CHANGED",
        "fetched": "2026-08-26",
        "bytes": len(live_txt),
        "sha1": hashlib.sha1(live_txt.encode("utf-8")).hexdigest()[:12],
        "url": "https://clashroyale.fandom.com/wiki/" + title.replace(" ", "_"),
    }
    print(f"{title:28s} rev={live_rev} same={same} title_ok={real_title}")
    time.sleep(0.25)

json.dump(res, open(OUT,"w",encoding="utf-8"), indent=1)
print("\nWROTE", OUT)
