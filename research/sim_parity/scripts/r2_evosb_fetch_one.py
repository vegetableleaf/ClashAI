import json, sys, time, urllib.request, urllib.parse, os
BASE = "https://clashroyale.fandom.com/api.php"
HDRS = {"User-Agent": "icebow-monitor/1.0 (+local)"}
CACHE = "C:/Users/benpe/ClashBot/research/sim_parity/webcache"
t = sys.argv[1]
q = urllib.parse.urlencode({"action":"parse","page":t,"prop":"wikitext|revid","format":"json"})
req = urllib.request.Request(BASE + "?" + q, headers=HDRS)
with urllib.request.urlopen(req, timeout=25) as r:
    d = json.loads(r.read().decode("utf-8"))
if "error" in d:
    print("ERROR:", d["error"]); sys.exit(1)
revid = d["parse"]["revid"]; wt = d["parse"]["wikitext"]["*"]
fn = t.replace("/", "_").replace(" ", "_") + ".wikitext"
path = os.path.join(CACHE, fn)
open(path, "w", encoding="utf-8").write(wt)
print("saved", path, "revid", revid, "bytes", len(wt))
time.sleep(0.25)
