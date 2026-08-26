import json, os, sys, time, urllib.request, urllib.parse

BASE = "https://clashroyale.fandom.com/api.php"
CACHE = os.path.join(os.path.dirname(__file__), "..", "webcache")
META  = os.path.join(CACHE, "_r2_spells_meta.json")

def fetch(title):
    q = urllib.parse.urlencode({"action":"parse","page":title,"prop":"wikitext|revid","format":"json"})
    req = urllib.request.Request(BASE + "?" + q, headers={"User-Agent":"icebow-monitor/1.0 (+local)"})
    with urllib.request.urlopen(req, timeout=25) as r:
        data = json.load(r)
    if "error" in data:
        return None, None, data["error"].get("code")
    p = data["parse"]
    return p["wikitext"]["*"], p["revid"], None

def cache_name(title):
    return title.replace("/", "_").replace(" ", "_") + ".wikitext"

def main(titles):
    meta = {}
    if os.path.exists(META):
        meta = json.load(open(META))
    for t in titles:
        fn = os.path.join(CACHE, cache_name(t))
        cached_exists = os.path.exists(fn)
        wt, revid, err = fetch(t)
        time.sleep(0.25)
        if err:
            print(f"{t}\tERROR\t{err}")
            meta[t] = {"error": err, "fetched": "2026-08-26"}
            continue
        cached_same = None
        if cached_exists:
            old = open(fn, encoding="utf-8").read()
            cached_same = (old == wt)
        with open(fn, "w", encoding="utf-8") as f:
            f.write(wt)
        meta[t] = {"revid": revid, "fetched": "2026-08-26", "bytes": len(wt),
                   "had_cache": cached_exists, "cache_content_same": cached_same}
        print(f"{t}\tOK\trevid={revid}\tbytes={len(wt)}\tcached={cached_exists}\tsame={cached_same}")
    json.dump(meta, open(META, "w"), indent=1)

if __name__ == "__main__":
    main(sys.argv[1:])
