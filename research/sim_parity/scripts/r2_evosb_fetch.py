"""r2 evos_b: live-fetch the 21 group pages, compare revid to the 08-25 cache, archive."""
import json, time, urllib.request, urllib.parse, os, hashlib

BASE = "https://clashroyale.fandom.com/api.php"
HDRS = {"User-Agent": "icebow-monitor/1.0 (+local)"}
CACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache"
OUT = "C:/Users/benpe/ClashBot/research/sim_parity/ledger/r2_evosb_fetchlog.json"

TITLES = ["Knight/Evolution","Lumberjack/Evolution","Mega Knight/Evolution",
 "Minion Horde/Evolution","Mortar/Evolution","Musketeer/Evolution","P.E.K.K.A./Evolution",
 "Princess/Evolution","Royal Ghost/Evolution","Royal Giant/Evolution","Royal Hogs/Evolution",
 "Royal Recruits/Evolution","Skeleton Army/Evolution","Skeleton Barrel/Evolution",
 "Skeletons/Evolution","Tesla/Evolution","Valkyrie/Evolution","Wall Breakers/Evolution",
 "Witch/Evolution","Wizard/Evolution","Zap/Evolution"]

cached_revids = json.load(open(
    "C:/Users/benpe/ClashBot/research/sim_parity/ledger/r1a_stage2.json"))["pages"]

def fname(title):
    return title.replace("/", "_").replace(" ", "_") + ".wikitext"

log = {}
for t in TITLES:
    q = urllib.parse.urlencode({"action":"parse","page":t,"prop":"wikitext|revid","format":"json"})
    req = urllib.request.Request(BASE + "?" + q, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    revid = d["parse"]["revid"]
    wt = d["parse"]["wikitext"]["*"]
    cr = cached_revids.get(t, {}).get("revid")
    fn = fname(t)
    path = os.path.join(CACHE, fn)
    changed = (cr is not None and revid != cr)
    if changed:
        livepath = os.path.join(CACHE, fn.replace(".wikitext", ".live20260826.wikitext"))
        open(livepath, "w", encoding="utf-8").write(wt)
    else:
        # same revid -> cache is current; still verify the cache file exists
        if not os.path.exists(path):
            open(path, "w", encoding="utf-8").write(wt)
    log[t] = {"live_revid": revid, "cached_revid": cr,
              "edit_war": "CHANGED" if changed else "pass",
              "sha1_live": hashlib.sha1(wt.encode()).hexdigest()[:10],
              "fetched": "2026-08-26"}
    print(t, "live", revid, "cached", cr, "CHANGED" if changed else "ok")
    time.sleep(0.25)

json.dump(log, open(OUT, "w"), indent=1)
print("wrote", OUT)
